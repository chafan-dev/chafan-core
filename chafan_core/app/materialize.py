import datetime
from typing import Any, Dict, Mapping, Optional, Tuple, Union
import logging
logger = logging.getLogger(__name__)

import sentry_sdk
from pydantic.tools import parse_obj_as
from sqlalchemy.orm import Session

from chafan_core.app import crud, models, schemas
from chafan_core.app.common import OperationType, report_msg
from chafan_core.app.config import settings
from chafan_core.app.data_broker import DataBroker
from chafan_core.app.model_utils import (
    get_live_answers_of_question,
    is_live_answer,
    is_live_article,
)
from chafan_core.app.schemas import event as event_module
from chafan_core.app.schemas.answer import AnswerInDBBase
from chafan_core.app.schemas.answer_archive import AnswerArchiveInDB
from chafan_core.app.schemas.article_archive import ArticleArchiveInDB
from chafan_core.app.schemas.event import (
    ClaimAnswerQuestionRewardInternal,
    CreateAnswerQuestionRewardInternal,
    Event,
    EventInternal,
)
from chafan_core.app.schemas.notification import Notification, NotificationInDBBase
from chafan_core.app.schemas.question import QuestionPreviewForSearch
from chafan_core.app.schemas.reward import AnsweredQuestionCondition, RewardCondition
from chafan_core.app.schemas.richtext import RichText
from chafan_core.app.schemas.security import IntlPhoneNumber
from chafan_core.utils.base import (
    ContentVisibility,
    HTTPException_,
    filter_not_none,
    map_,
    unwrap,
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


_VISIBLE_QUESTION_CONDITIONS = {
    "is_hidden": False,
}

_VISIBLE_SUBMISSION_CONDITIONS = {
    "is_hidden": False,
}


def keep_items(questions: Any, conditions: Mapping[str, Any]) -> Any:
    return questions.filter_by(**conditions)


def is_eligible_item(question: models.Question, conditions: Mapping[str, Any]) -> bool:
    return all(getattr(question, k) == v for k, v in conditions.items())


_KEYS = [
    "reward",
    "submission",
    "article",
    "article_column",
    "subject",
    "question",
    "answer",
    "comment",
    "reply",
    "parent_comment",
    "user",
    "site",
    "channel",
    "submission_suggestion",
    "answer_suggest_edit",
]


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
    if article.is_deleted:
        return False
    if principal_id == article.author_id:
        return True
    return is_live_article(article)


def visitor_can_read_article(*, article: models.Article) -> bool:
    if not is_live_article(article):
        return False
    return article.visibility == ContentVisibility.ANYONE


def get_answer_text_preview(answer: models.Answer) -> Tuple[str, bool]:
    text = answer.body_prerendered_text
    if len(text) > _MAX_ANSWER_BODY_CHARS:
        return text[:_MAX_ANSWER_BODY_CHARS] + "...", True
    return text, False


def user_schema_from_orm(user: models.User) -> schemas.User:
    base = schemas.UserInDBBase.from_orm(user)
    d = base.dict()
    if user.flags:
        d["flag_list"] = user.flags.split()
    else:
        d["flag_list"] = []

    enough_coins = user.remaining_coins >= settings.CREATE_SITE_COIN_DEDUCTION
    if settings.CREATE_SITE_FORCE_NEED_APPROVAL:
        d["can_create_public_site"] = False
        d["can_create_private_site"] = False
    else:
        d["can_create_public_site"] = (
            user.karma >= settings.MIN_KARMA_CREATE_PUBLIC_SITE and enough_coins
        )
        d["can_create_private_site"] = (
            user.karma >= settings.MIN_KARMA_CREATE_PRIVATE_SITE and enough_coins
        )
    if user.is_superuser:
        d["can_create_public_site"] = True
        d["can_create_private_site"] = True
    if user.phone_number_country_code and user.phone_number_subscriber_number:
        d["phone_number"] = IntlPhoneNumber(
            country_code=user.phone_number_country_code,
            subscriber_number=user.phone_number_subscriber_number,
        )
    return schemas.User(**d)


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
        """One question preview for any principal allowed to read the site."""
        if not user_in_site(
            self.broker.get_db(),
            site=question.site,
            user_id=self.principal_id,
            op_type=OperationType.ReadSite,
        ):
            return None
        if question.is_hidden and (
            self.principal_id is None or self.principal_id != question.author_id
        ):
            return None
        desc = None
        if question.description:
            desc = RichText(
                source=question.description,
                editor=question.description_editor,
                rendered_text=question.description_text,
            )
        return schemas.QuestionPreview(
            uuid=question.uuid,
            title=question.title,
            author=self.preview_of_user(question.author),
            is_placed_at_home=question.is_placed_at_home,
            created_at=question.created_at,
            desc=desc,
            answers_count=len(get_live_answers_of_question(question)),
            upvotes=self.get_question_upvotes(question),
            site=self.site_schema_from_orm(question.site),
            upvotes_count=question.upvotes_count,
            comments_count=len(question.comments),
        )

    # Back-compat alias during Step 1 migration of call sites.
    def preview_of_question_for_visitor(
        self,
        question: models.Question,
    ) -> Optional[schemas.QuestionPreview]:
        return self.preview_of_question(question)

    def get_answer_preview_base(
        self, answer: models.Answer
    ) -> schemas.answer.AnswerPreviewBase:
        preview_body, truncated = get_answer_text_preview(answer)
        return schemas.answer.AnswerPreviewBase(
            uuid=answer.uuid,
            body=preview_body,
            body_is_truncated=truncated,
            author=self.preview_of_user(answer.author),
            upvotes_count=answer.upvotes_count,
            is_hidden_by_moderator=answer.is_hidden_by_moderator,
            featured_at=answer.featured_at,
        )

    def preview_of_answer(
        self, answer: models.Answer
    ) -> Optional[schemas.AnswerPreview]:
        """One answer preview for any principal allowed to read the answer."""
        if not user_permission.answer_read_allowed(
            self.broker.get_db(), answer, self.principal_id
        ):
            return None
        question = self.preview_of_question(answer.question)
        if question is None:
            return None
        base = self.get_answer_preview_base(answer)
        return schemas.AnswerPreview(
            **base.dict(),
            question=question,
            full_answer=None,
        )

    # Back-compat alias during Step 1 migration of call sites.
    def preview_of_answer_for_visitor(
        self,
        answer: models.Answer,
    ) -> Optional[schemas.AnswerPreview]:
        return self.preview_of_answer(answer)

    def preview_of_article(
        self, article: models.Article
    ) -> Optional[schemas.ArticlePreview]:
        if self.principal_id:
            if not can_read_article(article=article, principal_id=self.principal_id):
                return None
        else:
            if not visitor_can_read_article(article=article):
                return None
        return schemas.ArticlePreview(
            uuid=article.uuid,
            author=self.preview_of_user(article.author),
            article_column=self.article_column_schema_from_orm(article.article_column),
            title=article.title,
            body_text=article.body_text,
            is_published=article.is_published,
            upvotes_count=article.upvotes_count,
        )

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
        try:
            event = EventInternal.parse_raw(event_internal_json)
        except Exception:
            import time

            if time.time() % 2 == 0:
                sentry_sdk.capture_message(
                    f"Failed to materialize event: {event_internal_json}",
                )
            return None
        db = self.broker.get_db()
        kwargs = {}
        for k, v in event.content.dict().items():
            if k == "verb":
                kwargs["verb"] = v
            else:
                if k in ("invited_email", "payment_amount", "message"):
                    kwargs[k] = v
                else:
                    assert k.endswith("_id"), k
                    k = k[:-3]
                    assert k in _KEYS, k
                    if k == "subject" or k == "user":
                        kwargs[k] = map_(crud.user.get(db, id=v), self.preview_of_user)
                    elif k == "question":
                        question = crud.question.get(db, id=v)
                        if question is None:
                            return None
                        question_data = self.preview_of_question(question)
                        if question_data is None:
                            return None
                        kwargs[k] = question_data
                    elif k == "submission":
                        submission = crud.submission.get(db, id=v)
                        if submission is None:
                            return None
                        submission_data = self.submission_schema_from_orm(submission)
                        if submission_data is None:
                            return None
                        kwargs[k] = submission_data
                    elif k == "submission_suggestion":
                        submission_suggestion = crud.submission_suggestion.get(db, id=v)
                        if submission_suggestion is None:
                            return None
                        submission_suggestion_data = (
                            self.submission_suggestion_schema_from_orm(
                                submission_suggestion
                            )
                        )
                        if submission_suggestion_data is None:
                            return None
                        kwargs[k] = submission_suggestion_data
                    elif k == "answer_suggest_edit":
                        answer_suggest_edit = crud.answer_suggest_edit.get(db, id=v)
                        if answer_suggest_edit is None:
                            return None
                        answer_suggest_edit_data = (
                            self.answer_suggest_edit_schema_from_orm(
                                answer_suggest_edit
                            )
                        )
                        if answer_suggest_edit_data is None:
                            return None
                        kwargs[k] = answer_suggest_edit_data
                    elif k == "reward":
                        reward = crud.reward.get(db, id=v)
                        if reward is None:
                            return None
                        kwargs["reward"] = self.reward_schema_from_orm(reward)
                        if isinstance(
                            event.content, CreateAnswerQuestionRewardInternal
                        ) or isinstance(
                            event.content, ClaimAnswerQuestionRewardInternal
                        ):
                            condition = RewardCondition.parse_obj(reward.condition)
                            assert isinstance(
                                condition.content, AnsweredQuestionCondition
                            )
                            question = crud.question.get_by_uuid(
                                db, uuid=condition.content.question_uuid
                            )
                            assert question is not None
                            question_data = self.preview_of_question(question)
                            if question_data is None:
                                return None
                            kwargs["question"] = question_data
                    elif k == "answer":
                        answer = crud.answer.get(db, id=v)
                        if answer is None:
                            return None
                        assert answer.body is not None
                        answer_preview = self.preview_of_answer(answer)
                        if answer_preview:
                            kwargs[k] = answer_preview
                        else:
                            return None
                    elif k == "article":
                        article = crud.article.get(db, id=v)
                        if article is None:
                            return None
                        data = self.preview_of_article(article)
                        if data is None:
                            return None
                        else:
                            kwargs[k] = data
                    elif k == "article_column":
                        article_column = crud.article_column.get(db, id=v)
                        if article_column is None:
                            return None
                        kwargs[k] = self.article_column_schema_from_orm(article_column)
                    elif k in ["comment", "parent_comment", "reply"]:
                        comment = crud.comment.get(db, id=v)
                        if comment:
                            comment_data = self.comment_schema_from_orm(comment)
                            if comment_data:
                                kwargs[k] = comment_data
                            else:
                                return None
                    elif k == "site":
                        kwargs[k] = map_(
                            crud.site.get(db, id=v), self.site_schema_from_orm
                        )
                    elif k == "channel":
                        kwargs[k] = map_(
                            crud.channel.get(db, id=v), self.channel_schema_from_orm
                        )
                    else:
                        raise Exception(k)
        event_content_class = event.content.__class__.__name__
        if event_content_class.endswith("Internal"):
            new_class = getattr(event_module, event_content_class[: -len("Internal")])
        else:
            new_class = getattr(event_module, event_content_class)
        try:
            return Event(created_at=event.created_at, content=new_class(**kwargs))
        except Exception as e:
            report_msg(
                f"Event construction exception: kwargs={kwargs}, exception={e}, event_internal_json={event_internal_json}"
            )
            return None

    def submission_schema_from_orm(
        self, submission: models.Submission
    ) -> Optional[schemas.Submission]:
        if not user_in_site(
            self.broker.get_db(),
            site=submission.site,
            user_id=self.principal_id,
            op_type=OperationType.ReadSite,
        ):
            return None
        if submission.is_hidden:
            return None
        base = schemas.SubmissionInDB.from_orm(submission)
        d = base.dict()
        d["site"] = self.site_schema_from_orm(submission.site)
        d["comments"] = filter_not_none(
            [self.comment_schema_from_orm(c) for c in submission.comments]
        )
        d["author"] = self.preview_of_user(submission.author)
        d["contributors"] = [self.preview_of_user(u) for u in submission.contributors]
        d["view_times"] = 0  # view_counters.get_views(submission.uuid, "submission")
        if submission.description is not None:
            d["desc"] = RichText(
                source=submission.description,
                rendered_text=submission.description_text,
                editor=submission.description_editor,
            )
        return schemas.Submission(**d)

    # Back-compat alias during Step 1 migration of call sites.
    def submission_for_visitor_schema_from_orm(
        self,
        submission: models.Submission,
    ) -> Optional[schemas.Submission]:
        return self.submission_schema_from_orm(submission)

    def notification_schema_from_orm(
        self, notification: models.Notification
    ) -> Optional[Notification]:
        base = NotificationInDBBase.from_orm(notification)
        if notification.event_json:
            event = self.materialize_event(notification.event_json)
            if event is None:
                return None
            d = base.dict()
            d["event"] = event
            return Notification(**d)
        return None

    def submission_suggestion_schema_from_orm(
        self,
        submission_suggestion: models.SubmissionSuggestion,
    ) -> Optional[schemas.SubmissionSuggestion]:
        base = schemas.SubmissionSuggestionInDB.from_orm(submission_suggestion)
        d = base.dict()
        d["author"] = self.preview_of_user(submission_suggestion.author)
        submission = self.submission_schema_from_orm(submission_suggestion.submission)
        if not submission:
            return None
        d["submission"] = submission
        if submission_suggestion.topic_uuids:
            d["topics"] = [
                schemas.Topic.from_orm(
                    unwrap(crud.topic.get_by_uuid(self.broker.get_db(), uuid=uuid))
                )
                for uuid in submission_suggestion.topic_uuids
            ]
        if submission_suggestion.description:
            d["desc"] = RichText(
                source=submission_suggestion.description,
                rendered_text=submission_suggestion.description_text,
                editor=submission_suggestion.description_editor,
            )
        else:
            d["desc"] = None
        return schemas.SubmissionSuggestion(**d)

    def answer_suggest_edit_schema_from_orm(
        self,
        answer_suggest_edit: models.AnswerSuggestEdit,
    ) -> Optional[schemas.AnswerSuggestEdit]:
        from chafan_core.app.services import answers as answers_service

        base = schemas.AnswerSuggestEditInDB.from_orm(answer_suggest_edit)
        d = base.dict()
        d["author"] = self.preview_of_user(answer_suggest_edit.author)
        # Full answer schema lives on services.answers / responders.
        # self.broker is RequestContext/DataBroker (has materializer + principal).
        answer = answers_service.answer_schema(
            self.broker, answer_suggest_edit.answer
        )
        if not answer:
            return None
        d["answer"] = answer
        if answer_suggest_edit.body:
            assert answer_suggest_edit.body_editor
            d["body_rich_text"] = RichText(
                source=answer_suggest_edit.body,
                rendered_text=answer_suggest_edit.body_text,
                editor=answer_suggest_edit.body_editor,
            )
        else:
            d["body_rich_text"] = None
        return schemas.AnswerSuggestEdit(**d)

    def comment_schema_from_orm(
        self, comment: models.Comment
    ) -> Optional[schemas.Comment]:
        from chafan_core.app.responders import comment as comment_responder

        return comment_responder.comment_schema_from_orm(self, comment)

    def get_question_upvotes(
        self, question: models.Question
    ) -> schemas.QuestionUpvotes:
        db = self.broker.get_db()
        valid_upvotes = (
            db.query(models.QuestionUpvotes)
            .filter_by(question_id=question.id, cancelled=False)
            .count()
        )
        if self.principal_id:
            upvoted = (
                db.query(models.QuestionUpvotes)
                .filter_by(
                    question_id=question.id,
                    voter_id=self.principal_id,
                    cancelled=False,
                )
                .first()
                is not None
            )
        else:
            upvoted = False
        return schemas.QuestionUpvotes(
            question_uuid=question.uuid, count=valid_upvotes, upvoted=upvoted
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
