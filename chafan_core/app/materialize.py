from typing import Any, Dict, Mapping, Optional, Tuple
import logging
logger = logging.getLogger(__name__)

from sqlalchemy.orm import Session

from chafan_core.app import crud, models, schemas
from chafan_core.app.common import OperationType
from chafan_core.app.data_broker import DataBroker
from chafan_core.app.model_utils import is_live_answer
from chafan_core.app.schemas.answer_archive import AnswerArchiveInDB
from chafan_core.app.schemas.article_archive import ArticleArchiveInDB
from chafan_core.app.schemas.event import Event
from chafan_core.app.schemas.notification import Notification
from chafan_core.app.schemas.question import QuestionPreviewForSearch
from chafan_core.app.schemas.richtext import RichText
from chafan_core.utils.base import (
    ContentVisibility,
    HTTPException_,
    map_,
)
from chafan_core.utils.constants import (
    unknown_user_full_name,
    unknown_user_handle,
    unknown_user_uuid,
)
from chafan_core.utils.validators import StrippedNonEmptyBasicStr

_ANONYMOUS_USER_PREVIEW = schemas.UserPreview(
    uuid=unknown_user_uuid,
    handle=StrippedNonEmptyBasicStr(unknown_user_handle),
    full_name=unknown_user_full_name,
)


import chafan_core.app.user_permission as user_permission
# Back-compat wrappers — prefer chafan_core.app.user_permission.
# Call through functions (not aliases) to avoid circular-import init issues.


def get_active_site_profile(
    db: Session, *, site: models.Site, user_id: int
) -> Optional[models.Profile]:
    return user_permission.get_active_site_profile(db, site, user_id)


def user_in_site(
    db: Session,
    *,
    site: models.Site,
    user_id: Optional[int],
    op_type: OperationType,
) -> bool:
    return user_permission.user_in_site(db, site, user_id, op_type)


def check_user_in_site(
    db: Session, *, site: models.Site, user_id: int, op_type: OperationType
) -> None:
    user_permission.check_user_in_site(
        db, site=site, user_id=user_id, op_type=op_type
    )


def check_user_in_channel(current_user: models.User, channel: models.Channel) -> None:
    user_permission.check_user_in_channel(current_user, channel)


def keep_items(questions: Any, conditions: Mapping[str, Any]) -> Any:
    return questions.filter_by(**conditions)


def is_eligible_item(question: models.Question, conditions: Mapping[str, Any]) -> bool:
    return all(getattr(question, k) == v for k, v in conditions.items())


def submission_archive_schema_from_orm(
    submission: models.SubmissionArchive,
) -> schemas.SubmissionArchive:
    d: Dict[str, Any] = {}
    d["id"] = submission.id
    d["created_at"] = submission.created_at
    d["title"] = submission.title
    d["topic_uuids"] = submission.topic_uuids
    d["url"] = submission.submission.url if submission.submission else None
    if submission.description is not None:
        d["desc"] = RichText(
            source=submission.description,
            rendered_text=submission.description_text,
            editor=submission.description_editor,
        )
    else:
        d["desc"] = None
    return schemas.SubmissionArchive(**d)


def article_archive_schema_from_orm(
    article_archive: models.ArticleArchive,
) -> schemas.ArticleArchive:
    base = ArticleArchiveInDB.from_orm(article_archive)
    d = base.dict()
    d["content"] = RichText(
        source=article_archive.body,
        editor=article_archive.editor,
    )
    return schemas.ArticleArchive(**d)


def answer_archive_schema_from_orm(
    answer_archive: models.Archive,
) -> schemas.AnswerArchive:
    base = AnswerArchiveInDB.from_orm(answer_archive)
    d = base.dict()
    d["content"] = RichText(
        source=answer_archive.body,
        editor=answer_archive.editor,
    )
    return schemas.AnswerArchive(**d)


def root_route(comment: models.Comment) -> Optional[str]:
    from chafan_core.app.responders.comment import root_route as _root_route

    return _root_route(comment)


_MAX_ANSWER_BODY_CHARS = 100


def visitor_can_read_answer(*, answer: models.Answer) -> bool:
    if not is_live_answer(answer):
        return False
    if answer.visibility != ContentVisibility.ANYONE:
        return False
    return answer.site.public_readable


def can_read_answer(db: Session, *, answer: models.Answer, principal_id: int) -> bool:
    if answer.is_deleted:
        return False
    if principal_id == answer.author_id:
        return True
    if not is_live_answer(answer):
        return False
    return user_in_site(
        db, site=answer.site, user_id=principal_id, op_type=OperationType.ReadSite
    )


def can_read_article(*, article: models.Article, principal_id: int) -> bool:
    from chafan_core.app.responders import article as article_responder

    return article_responder.can_read_article(
        article=article, principal_id=principal_id
    )


def visitor_can_read_article(*, article: models.Article) -> bool:
    from chafan_core.app.responders import article as article_responder

    return article_responder.visitor_can_read_article(article=article)


def get_answer_text_preview(answer: models.Answer) -> Tuple[str, bool]:
    from chafan_core.app.responders import answer as answer_responder

    return answer_responder.get_answer_text_preview(answer)


def user_schema_from_orm(user: models.User) -> schemas.User:
    from chafan_core.app.responders import user as user_responder

    return user_responder.user_schema_from_orm(user)


# Should I put it into a class?
def preview_of_question_as_search_hit(question: models.Question):
    if not question.site.public_readable:
        return None
    r = QuestionPreviewForSearch(
        uuid = question.uuid,
        title = question.title
    )
    return r



class Materializer(object):
    def __init__(self, broker: DataBroker, principal_id: Optional[int]):
        self.broker = broker
        self.principal_id = principal_id
        if principal_id:
            self.principal = crud.user.get(broker.get_db(), id=principal_id)
        else:
            self.principal = None

    def get_db(self) -> Session:
        """Duck-type with RequestContext so responders can take either."""
        return self.broker.get_db()

    def preview_of_user(self, user: models.User) -> schemas.UserPreview:
        if not user.is_active:
            return _ANONYMOUS_USER_PREVIEW
        return schemas.UserPreview(
            uuid=user.uuid,
            karma=user.karma,
            full_name=user.full_name,
            handle=user.handle,
            avatar_url=user.avatar_url,
            personal_introduction=user.personal_introduction,
        )

    def site_schema_from_orm(self, site: models.Site) -> schemas.Site:
        import chafan_core.app.responders as responders

        return responders.site.site_schema_from_orm(self, site)

    def get_user_article_column_subscription(
        self, article_column: models.ArticleColumn
    ) -> schemas.UserArticleColumnSubscription:
        if self.principal:
            subscribed = article_column in self.principal.subscribed_article_columns
        else:
            subscribed = False
        return schemas.UserArticleColumnSubscription(
            article_column_uuid=article_column.uuid,
            subscription_count=article_column.subscribers.count(),
            subscribed_by_me=subscribed,
        )

    def article_column_schema_from_orm(
        self,
        article_column: models.ArticleColumn,
    ) -> schemas.ArticleColumn:
        from chafan_core.app.responders import misc as misc_responder

        return misc_responder.article_column_schema_from_orm(self, article_column)

    def preview_of_question(
        self, question: models.Question
    ) -> Optional[schemas.QuestionPreview]:
        import chafan_core.app.responders as responders

        return responders.question.preview_of_question(self, question)

    # Back-compat alias during Step 1 migration of call sites.
    def preview_of_question_for_visitor(
        self,
        question: models.Question,
    ) -> Optional[schemas.QuestionPreview]:
        return self.preview_of_question(question)

    def get_answer_preview_base(
        self, answer: models.Answer
    ) -> schemas.answer.AnswerPreviewBase:
        from chafan_core.app.responders import answer as answer_responder

        return answer_responder.answer_preview_base(self, answer)

    def preview_of_answer(
        self, answer: models.Answer
    ) -> Optional[schemas.AnswerPreview]:
        from chafan_core.app.responders import answer as answer_responder

        return answer_responder.preview_of_answer(self, answer)

    # Back-compat alias during Step 1 migration of call sites.
    def preview_of_answer_for_visitor(
        self,
        answer: models.Answer,
    ) -> Optional[schemas.AnswerPreview]:
        return self.preview_of_answer(answer)

    def preview_of_article(
        self, article: models.Article
    ) -> Optional[schemas.ArticlePreview]:
        from chafan_core.app.responders import article as article_responder

        return article_responder.preview_of_article(self, article)

    def message_schema_from_orm(self, message: models.Message) -> schemas.Message:
        from chafan_core.app.responders import misc as misc_responder

        return misc_responder.message_schema_from_orm(self, message)

    def form_schema_from_orm(self, form: models.Form) -> schemas.Form:
        from chafan_core.app.responders import misc as misc_responder

        return misc_responder.form_schema_from_orm(self, form)

    def webhook_schema_from_orm(self, webhook: models.Webhook) -> schemas.Webhook:
        from chafan_core.app.responders import misc as misc_responder

        return misc_responder.webhook_schema_from_orm(self, webhook)

    def form_response_schema_from_orm(
        self,
        form_response: models.FormResponse,
    ) -> schemas.FormResponse:
        from chafan_core.app.responders import misc as misc_responder

        return misc_responder.form_response_schema_from_orm(self, form_response)

    def profile_schema_from_orm(self, profile: models.Profile) -> schemas.Profile:
        from chafan_core.app.responders import misc as misc_responder

        return misc_responder.profile_schema_from_orm(self, profile)

    def question_archive_schema_from_orm(
        self, archive: models.QuestionArchive
    ) -> schemas.QuestionArchive:
        base = schemas.QuestionArchiveInDB.from_orm(archive)
        d = base.dict()
        d["editor"] = map_(archive.editor, self.preview_of_user)
        if archive.description is not None:
            d["desc"] = RichText(
                source=archive.description,
                editor=archive.description_editor,
                rendered_text=archive.description_text,
            )
        return schemas.QuestionArchive(**d)

    def invitation_link_schema_from_orm(
        self,
        invitation_link: models.InvitationLink,
    ) -> schemas.InvitationLink:
        from chafan_core.app.responders import misc as misc_responder

        return misc_responder.invitation_link_schema_from_orm(self, invitation_link)

    def reward_schema_from_orm(self, reward: models.Reward) -> schemas.Reward:
        from chafan_core.app.responders import misc as misc_responder

        return misc_responder.reward_schema_from_orm(self, reward)

    def application_schema_from_orm(
        self, application: models.Application
    ) -> schemas.Application:
        from chafan_core.app.responders import misc as misc_responder

        return misc_responder.application_schema_from_orm(self, application)

    def audit_log_schema_from_orm(self, audit_log: models.AuditLog) -> schemas.AuditLog:
        from chafan_core.app.responders import misc as misc_responder

        return misc_responder.audit_log_schema_from_orm(self, audit_log)

    def task_schema_from_orm(self, task: models.Task) -> schemas.Task:
        base = schemas.TaskInDB.from_orm(task)
        d = base.dict()
        d["initiator"] = self.preview_of_user(task.initiator)
        return schemas.Task(**d)

    def materialize_event(self, event_internal_json: str) -> Optional[Event]:
        from chafan_core.app.responders import event as event_responder

        return event_responder.materialize_event(self, event_internal_json)

    def submission_schema_from_orm(
        self, submission: models.Submission
    ) -> Optional[schemas.Submission]:
        import chafan_core.app.responders as responders

        return responders.submission.submission_schema_from_orm(self, submission)

    # Back-compat alias during Step 1 migration of call sites.
    def submission_for_visitor_schema_from_orm(
        self,
        submission: models.Submission,
    ) -> Optional[schemas.Submission]:
        return self.submission_schema_from_orm(submission)

    def notification_schema_from_orm(
        self, notification: models.Notification
    ) -> Optional[Notification]:
        from chafan_core.app.responders import event as event_responder

        return event_responder.notification_schema_from_orm(self, notification)

    def submission_suggestion_schema_from_orm(
        self,
        submission_suggestion: models.SubmissionSuggestion,
    ) -> Optional[schemas.SubmissionSuggestion]:
        from chafan_core.app.responders import suggestions as suggestions_responder

        return suggestions_responder.submission_suggestion_schema_from_orm(
            self, submission_suggestion
        )

    def answer_suggest_edit_schema_from_orm(
        self,
        answer_suggest_edit: models.AnswerSuggestEdit,
    ) -> Optional[schemas.AnswerSuggestEdit]:
        from chafan_core.app.responders import suggestions as suggestions_responder

        return suggestions_responder.answer_suggest_edit_schema_from_orm(
            self, answer_suggest_edit
        )

    def comment_schema_from_orm(
        self, comment: models.Comment
    ) -> Optional[schemas.Comment]:
        from chafan_core.app.responders import comment as comment_responder

        return comment_responder.comment_schema_from_orm(self, comment)

    def get_question_upvotes(
        self, question: models.Question
    ) -> schemas.QuestionUpvotes:
        import chafan_core.app.responders as responders

        return responders.question.get_question_upvotes(
            self.get_db(), question, self.principal_id
        )

    def channel_schema_from_orm(self, channel: models.Channel) -> schemas.Channel:
        from chafan_core.app.responders import misc as misc_responder

        return misc_responder.channel_schema_from_orm(self, channel)

    def report_schema_from_orm(self, report: models.Report) -> schemas.Report:
        from chafan_core.app.responders import misc as misc_responder

        return misc_responder.report_schema_from_orm(self, report)

    def feedback_schema_from_orm(self, f: models.Feedback) -> schemas.Feedback:
        from chafan_core.app.responders import misc as misc_responder

        return misc_responder.feedback_schema_from_orm(self, f)
