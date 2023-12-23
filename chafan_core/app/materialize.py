import datetime
from typing import Any, Dict, Mapping, Optional, Tuple, Union

import sentry_sdk
from pydantic.tools import parse_obj_as
from sqlalchemy.orm import Session

from chafan_core.app import crud, models, schemas, view_counters
from chafan_core.app.common import OperationType, is_dev
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
from chafan_core.app.schemas.article import ArticleInDB
from chafan_core.app.schemas.article_archive import ArticleArchiveInDB
from chafan_core.app.schemas.event import (
    ClaimAnswerQuestionRewardInternal,
    CreateAnswerQuestionRewardInternal,
    Event,
    EventInternal,
)
from chafan_core.app.schemas.notification import Notification, NotificationInDBBase
from chafan_core.app.schemas.question import QuestionInDBBase
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


def get_active_site_profile(
    db: Session, *, site: models.Site, user_id: int
) -> Optional[models.Profile]:
    return crud.profile.get_by_user_and_site(db, owner_id=user_id, site_id=site.id)


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


def user_in_site(
    db: Session,
    *,
    site: models.Site,
    user_id: int,
    op_type: OperationType,
) -> bool:
    if op_type == OperationType.ReadSite and site.public_readable:
        return True
    if op_type == OperationType.WriteSiteAnswer and site.public_writable_answer:
        return True
    if op_type == OperationType.WriteSiteSubmission and site.public_writable_submission:
        return True
    if op_type == OperationType.WriteSiteQuestion and site.public_writable_question:
        return True
    if op_type == OperationType.WriteSiteComment and site.public_writable_comment:
        return True
    if get_active_site_profile(db, site=site, user_id=user_id) is None:
        return False
    if op_type == OperationType.AddSiteMember and not site.addable_member:
        return False
    return True


def check_user_in_site(
    db: Session, *, site: models.Site, user_id: int, op_type: OperationType
) -> None:
    if not user_in_site(db, site=site, user_id=user_id, op_type=op_type):
        raise HTTPException_(
            status_code=400,
            detail="Current user is not allowed in this site.",
        )


def check_user_in_channel(current_user: models.User, channel: models.Channel) -> None:
    if (
        current_user not in channel.members
        and current_user is not channel.admin
        and current_user is not channel.private_with_user
    ):
        raise HTTPException_(
            status_code=400,
            detail="Unauthorized.",
        )


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
    if submission.description is not None:
        d["desc"] = RichText(
            source=submission.description,
            rendered_text=submission.description_text,
            editor=submission.description_editor,
        )
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
    if comment.answer is not None:
        return (
            f"/questions/{comment.answer.question.uuid}/answers/{comment.answer.uuid}"
        )
    elif comment.question is not None:
        return f"/questions/{comment.question.uuid}"
    elif comment.article is not None:
        return f"/articles/{comment.article.uuid}"
    elif comment.submission is not None:
        return f"/submissions/{comment.submission.uuid}"
    elif comment.parent_comment is not None:
        return root_route(comment.parent_comment)
    return None


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
        ) or is_dev()
        d["can_create_private_site"] = (
            user.karma >= settings.MIN_KARMA_CREATE_PRIVATE_SITE and enough_coins
        ) or is_dev()
    if user.is_superuser:
        d["can_create_public_site"] = True
        d["can_create_private_site"] = True
    if user.phone_number_country_code and user.phone_number_subscriber_number:
        d["phone_number"] = IntlPhoneNumber(
            country_code=user.phone_number_country_code,
            subscriber_number=user.phone_number_subscriber_number,
        )
    return schemas.User(**d)


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
        base = schemas.SiteInDBBase.from_orm(site)
        site_dict = base.dict()
        site_dict["moderator"] = self.preview_of_user(site.moderator)
        site_dict["questions_count"] = keep_items(
            site.questions, _VISIBLE_QUESTION_CONDITIONS
        ).count()
        site_dict["submissions_count"] = keep_items(
            site.submissions, _VISIBLE_SUBMISSION_CONDITIONS
        ).count()
        site_dict["members_count"] = len(site.profiles)
        if site.category_topic:
            site_dict["category_topic"] = schemas.Topic.from_orm(site.category_topic)
        else:
            site_dict["category_topic"] = None
        return schemas.Site(**site_dict)

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
        base = schemas.ArticleColumnInDBBase.from_orm(article_column)
        data_dict = base.dict()
        data_dict["owner"] = self.preview_of_user(article_column.owner)
        data_dict["subscription"] = self.get_user_article_column_subscription(
            article_column
        )
        return schemas.ArticleColumn(**data_dict)

    def get_question_preview_for_visitor(
        self, question: models.Question
    ) -> schemas.QuestionPreviewForVisitor:
        desc = None
        if question.description:
            desc = RichText(
                source=question.description,
                editor=question.description_editor,
                rendered_text=question.description_text,
            )
        return schemas.QuestionPreviewForVisitor(
            uuid=question.uuid,
            title=question.title,
            author=self.preview_of_user(question.author),
            is_placed_at_home=question.is_placed_at_home,
            created_at=question.created_at,
            desc=desc,
            answers_count=len(get_live_answers_of_question(question)),
            upvotes=self.get_question_upvotes(question),
        )

    def preview_of_question_for_visitor(
        self,
        question: models.Question,
    ) -> Optional[schemas.QuestionPreviewForVisitor]:
        if not question.site.public_readable:
            return None
        if not is_eligible_item(question, _VISIBLE_QUESTION_CONDITIONS):
            return None
        return self.get_question_preview_for_visitor(question)

    def preview_of_question(
        self, question: models.Question
    ) -> Optional[schemas.QuestionPreview]:
        if self.principal_id and not user_in_site(
            self.broker.get_db(),
            site=question.site,
            user_id=self.principal_id,
            op_type=OperationType.ReadSite,
        ):
            return None
        preview_base = self.get_question_preview_for_visitor(question)
        return schemas.QuestionPreview(
            **preview_base.dict(),
            site=self.site_schema_from_orm(question.site),
            upvotes_count=question.upvotes_count,
            comments_count=len(question.comments),
        )

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

    def preview_of_answer_for_visitor(
        self,
        answer: models.Answer,
    ) -> Optional[schemas.AnswerPreviewForVisitor]:
        if not visitor_can_read_answer(answer=answer):
            return None
        question = self.preview_of_question_for_visitor(answer.question)
        if not question:
            return None
        base = self.get_answer_preview_base(answer)
        return schemas.AnswerPreviewForVisitor(
            **base.dict(),
            question=question,
        )

    def preview_of_answer(
        self, answer: models.Answer
    ) -> Optional[schemas.AnswerPreview]:
        if self.principal_id and not can_read_answer(
            self.broker.get_db(), answer=answer, principal_id=self.principal_id
        ):
            return None
        question = self.preview_of_question(answer.question)
        if question is None:
            return None
        base = self.get_answer_preview_base(answer)
        return schemas.AnswerPreview(
            **base.dict(),
            question=question,
        )

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
        base = schemas.MessageInDBBase.from_orm(message)
        d = base.dict()
        d["author"] = self.preview_of_user(message.author)
        return schemas.Message(**d)

    def form_schema_from_orm(self, form: models.Form) -> schemas.Form:
        base = schemas.FormInDBBase.from_orm(form)
        d = base.dict()
        d["author"] = self.preview_of_user(form.author)
        return schemas.Form(**d)

    def webhook_schema_from_orm(self, webhook: models.Webhook) -> schemas.Webhook:
        base = schemas.WebhookInDB.from_orm(webhook)
        d = base.dict()
        d["site"] = self.site_schema_from_orm(webhook.site)
        return schemas.Webhook(**d)

    def form_response_schema_from_orm(
        self,
        form_response: models.FormResponse,
    ) -> schemas.FormResponse:
        base = schemas.FormResponseInDBBase.from_orm(form_response)
        d = base.dict()
        d["response_author"] = self.preview_of_user(form_response.response_author)
        d["form"] = self.form_schema_from_orm(form_response.form)
        return schemas.FormResponse(**d)

    def profile_schema_from_orm(self, profile: models.Profile) -> schemas.Profile:
        base = schemas.ProfileInDBBase.from_orm(profile)
        d = base.dict()
        d["site"] = self.site_schema_from_orm(profile.site)
        d["owner"] = self.preview_of_user(profile.owner)
        return schemas.Profile(**d)

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
        base = schemas.InvitationLinkInDB.from_orm(invitation_link)
        d = base.dict()
        d["invited_to_site"] = map_(
            invitation_link.invited_to_site, self.site_schema_from_orm
        )
        d["inviter"] = self.preview_of_user(invitation_link.inviter)
        utc_now = datetime.datetime.now(tz=datetime.timezone.utc)
        d["valid"] = (
            invitation_link.expired_at > utc_now and invitation_link.remaining_quota > 0
        )
        return schemas.InvitationLink(**d)

    def article_for_visitor_schema_from_orm(
        self,
        article: models.Article,
    ) -> Optional[schemas.ArticleForVisitor]:
        if not visitor_can_read_article(article=article):
            return None
        base = ArticleInDB.from_orm(article)
        d = base.dict()
        d["article_column"] = self.article_column_schema_from_orm(
            article.article_column
        )
        d["comments"] = filter_not_none(
            [self.comment_for_visitor_schema_from_orm(c) for c in article.comments]
        )
        d["author"] = self.preview_of_user(article.author)
        d["content"] = RichText(
            source=article.body, editor=article.editor, rendered_text=article.body_text
        )
        return schemas.ArticleForVisitor(**d)

    def article_schema_from_orm(
        self, article: models.Article
    ) -> Optional[schemas.Article]:
        if not self.principal_id:
            return None
        if not can_read_article(article=article, principal_id=self.principal_id):
            return None
        upvoted = (
            self.broker.get_db()
            .query(models.ArticleUpvotes)
            .filter_by(
                article_id=article.id, voter_id=self.principal_id, cancelled=False
            )
            .first()
            is not None
        )
        base = ArticleInDB.from_orm(article)
        d = base.dict()
        d["article_column"] = self.article_column_schema_from_orm(
            article.article_column
        )
        d["comments"] = filter_not_none(
            [self.comment_schema_from_orm(c) for c in article.comments]
        )
        d["bookmark_count"] = article.bookmarkers.count()
        principal = crud.user.get(self.broker.get_db(), id=self.principal_id)
        assert principal is not None
        d["bookmarked"] = article in principal.bookmarked_articles
        d["author"] = self.preview_of_user(article.author)
        d["upvoted"] = upvoted
        d["view_times"] = view_counters.get_views(article.uuid, "article")
        d["archives_count"] = len(article.archives)
        if article.is_published:
            body = article.body
        else:
            if article.body_draft:
                body = article.body_draft
            else:
                body = article.body
        d["content"] = RichText(
            source=body, editor=article.editor, rendered_text=article.body_text
        )
        return schemas.Article(**d)

    def reward_schema_from_orm(self, reward: models.Reward) -> schemas.Reward:
        base = schemas.RewardInDBBase.from_orm(reward)
        d = base.dict()
        d["giver"] = self.preview_of_user(reward.giver)
        d["receiver"] = self.preview_of_user(reward.receiver)
        if reward.condition:
            d["condition"] = parse_obj_as(
                schemas.reward.RewardCondition, reward.condition
            )
        return schemas.Reward(**d)

    def application_schema_from_orm(
        self, application: models.Application
    ) -> schemas.Application:
        base = schemas.ApplicationInDBBase.from_orm(application)
        d = base.dict()
        d["applicant"] = self.preview_of_user(application.applicant)
        d["applied_site"] = self.site_schema_from_orm(application.applied_site)
        return schemas.Application(**d)

    def audit_log_schema_from_orm(self, audit_log: models.AuditLog) -> schemas.AuditLog:
        base = schemas.AuditLogInDBBase.from_orm(audit_log)
        d = base.dict()
        d["user"] = self.preview_of_user(audit_log.user)
        return schemas.AuditLog(**d)

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
            if not is_dev():
                sentry_sdk.capture_message(
                    f"Event construction exception: kwargs={kwargs}, exception={e}, event_internal_json={event_internal_json}"
                )
                return None
            else:
                raise Exception(
                    f"Event construction exception: kwargs={kwargs}, exception={e}, event_internal_json={event_internal_json}"
                )

    def answer_for_visitor_schema_from_orm(
        self,
        answer: models.Answer,
    ) -> Optional[schemas.AnswerForVisitor]:
        if not visitor_can_read_answer(answer=answer):
            return None
        base = AnswerInDBBase.from_orm(answer)
        d = base.dict()
        d["site"] = self.site_schema_from_orm(answer.site)
        d["comments"] = filter_not_none(
            [self.comment_for_visitor_schema_from_orm(c) for c in answer.comments]
        )
        q = self.preview_of_question_for_visitor(answer.question)
        if q is None:
            return None
        d["question"] = q
        d["author"] = self.preview_of_user(answer.author)
        d["view_times"] = view_counters.get_views(answer.uuid, "answer")
        d["content"] = RichText(
            source=answer.body,
            rendered_text=answer.body_prerendered_text,
            editor=answer.editor,
        )
        return schemas.AnswerForVisitor(**d)

    def answer_schema_from_orm(self, answer: models.Answer) -> Optional[schemas.Answer]:
        if not self.principal_id:
            return None
        db = self.broker.get_db()
        if not can_read_answer(db, answer=answer, principal_id=self.principal_id):
            return None
        upvoted = (
            db.query(models.Answer_Upvotes)
            .filter_by(answer_id=answer.id, voter_id=self.principal_id, cancelled=False)
            .first()
            is not None
        )
        comment_writable = user_in_site(
            db,
            site=answer.site,
            user_id=self.principal_id,
            op_type=OperationType.WriteSiteComment,
        )
        base = AnswerInDBBase.from_orm(answer)
        d = base.dict()
        d["site"] = self.site_schema_from_orm(answer.site)
        d["comments"] = filter_not_none(
            [self.comment_schema_from_orm(c) for c in answer.comments]
        )
        d["author"] = self.preview_of_user(answer.author)
        d["question"] = self.preview_of_question(answer.question)
        d["upvoted"] = upvoted
        d["comment_writable"] = comment_writable
        d["bookmark_count"] = answer.bookmarkers.count()
        d["archives_count"] = len(answer.archives)
        principal = crud.user.get(db, id=self.principal_id)
        assert principal is not None
        d["bookmarked"] = answer in principal.bookmarked_answers
        d["view_times"] = view_counters.get_views(answer.uuid, "answer")
        if answer.is_published:
            body = answer.body
        else:
            if answer.body_draft:
                body = answer.body_draft
            else:
                body = answer.body
        d["content"] = RichText(
            source=body,
            rendered_text=answer.body_prerendered_text,
            editor=answer.editor,
        )
        d["suggest_editable"] = answer.body_draft is None
        return schemas.Answer(**d)

    def question_schema_from_orm(
        self, question: models.Question
    ) -> Optional[schemas.Question]:
        if not self.principal_id:
            return None
        if not user_in_site(
            self.broker.get_db(),
            site=question.site,
            user_id=self.principal_id,
            op_type=OperationType.ReadSite,
        ):
            return None
        upvoted = (
            self.broker.get_db()
            .query(models.QuestionUpvotes)
            .filter_by(
                question_id=question.id, voter_id=self.principal_id, cancelled=False
            )
            .first()
            is not None
        )
        base = QuestionInDBBase.from_orm(question)
        d = base.dict()
        d["site"] = self.site_schema_from_orm(question.site)
        d["comments"] = filter_not_none(
            [self.comment_schema_from_orm(c) for c in question.comments]
        )
        d["author"] = self.preview_of_user(question.author)
        d["editor"] = map_(question.editor, self.preview_of_user)
        d["upvoted"] = upvoted
        d["view_times"] = view_counters.get_views(question.uuid, "question")
        d["answers_count"] = len(get_live_answers_of_question(question))
        if question.description is not None:
            d["desc"] = RichText(
                source=question.description,
                editor=question.description_editor,
                rendered_text=question.description_text,
            )
        d["upvotes"] = self.get_question_upvotes(question)
        return schemas.Question(**d)

    def get_materalized_answer(
        self, answer: models.Answer
    ) -> Union[Optional[schemas.Answer], Optional[schemas.AnswerForVisitor]]:
        if self.principal_id is not None:
            return self.answer_schema_from_orm(answer)
        else:
            return self.answer_for_visitor_schema_from_orm(answer)

    def question_for_visitor_schema_from_orm(
        self,
        question: models.Question,
    ) -> Optional[schemas.QuestionForVisitor]:
        if not question.site.public_readable:
            return None
        base = QuestionInDBBase.from_orm(question)
        d = base.dict()
        d["author"] = self.preview_of_user(question.author)
        d["site"] = self.site_schema_from_orm(question.site)
        d["comments"] = filter_not_none(
            [self.comment_for_visitor_schema_from_orm(c) for c in question.comments]
        )
        d["answers_count"] = len(get_live_answers_of_question(question))
        if question.description:
            d["desc"] = RichText(
                source=question.description,
                editor=question.description_editor,
                rendered_text=question.description_text,
            )
        d["upvotes"] = self.get_question_upvotes(question)
        return schemas.QuestionForVisitor(**d)

    def submission_for_visitor_schema_from_orm(
        self,
        submission: models.Submission,
    ) -> Optional[schemas.SubmissionForVisitor]:
        if not submission.site.public_readable:
            return None
        if submission.is_hidden:
            return None
        base = schemas.SubmissionInDB.from_orm(submission)
        d = base.dict()
        d["site"] = self.site_schema_from_orm(submission.site)
        d["comments"] = filter_not_none(
            [self.comment_for_visitor_schema_from_orm(c) for c in submission.comments]
        )
        d["author"] = self.preview_of_user(submission.author)
        d["contributors"] = [self.preview_of_user(u) for u in submission.contributors]
        if submission.description:
            d["desc"] = RichText(
                source=submission.description,
                rendered_text=submission.description_text,
                editor=submission.description_editor,
            )
        return schemas.SubmissionForVisitor(**d)

    def submission_schema_from_orm(
        self, submission: models.Submission
    ) -> Optional[schemas.Submission]:
        if self.principal_id and not user_in_site(
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
        d["view_times"] = view_counters.get_views(submission.uuid, "submission")
        if submission.description is not None:
            d["desc"] = RichText(
                source=submission.description,
                rendered_text=submission.description_text,
                editor=submission.description_editor,
            )
        return schemas.Submission(**d)

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
        base = schemas.AnswerSuggestEditInDB.from_orm(answer_suggest_edit)
        d = base.dict()
        d["author"] = self.preview_of_user(answer_suggest_edit.author)
        answer = self.answer_schema_from_orm(answer_suggest_edit.answer)
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

    def comment_for_visitor_schema_from_orm(
        self,
        comment: models.Comment,
    ) -> Optional[schemas.CommentForVisitor]:
        if comment.site and not comment.site.public_readable:
            return None
        base = schemas.CommentInDBBase.from_orm(comment)
        d = base.dict()
        d["root_route"] = root_route(comment)
        d["author"] = self.preview_of_user(comment.author)
        d["content"] = RichText(
            source=comment.body,
            rendered_text=comment.body_text,
            editor=comment.editor,
        )
        d["child_comments"] = filter_not_none(
            [
                self.comment_for_visitor_schema_from_orm(c)
                for c in comment.child_comments
            ]
        )
        return schemas.CommentForVisitor(**d)

    # TODO: optimize -- principal can be unchecked if the parent (e.g. answer) is already checked with principal
    def comment_schema_from_orm(
        self, comment: models.Comment
    ) -> Optional[schemas.Comment]:
        db = self.broker.get_db()
        if comment.site:
            if self.principal_id and not user_in_site(
                db,
                site=comment.site,
                user_id=self.principal_id,
                op_type=OperationType.ReadSite,
            ):
                return None
        base = schemas.CommentInDBBase.from_orm(comment)
        upvoted = (
            db.query(models.CommentUpvotes)
            .filter_by(
                comment_id=comment.id, voter_id=self.principal_id, cancelled=False
            )
            .first()
            is not None
        )
        d = base.dict()
        d["author"] = self.preview_of_user(comment.author)
        d["upvoted"] = upvoted
        d["root_route"] = root_route(comment)
        d["content"] = RichText(
            source=comment.body,
            rendered_text=comment.body_text,
            editor=comment.editor,
        )
        d["child_comments"] = filter_not_none(
            [self.comment_schema_from_orm(c) for c in comment.child_comments]
        )
        return schemas.Comment(**d)

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
        base = schemas.ChannelInDBBase.from_orm(channel)
        d = base.dict()
        if channel.private_with_user:
            d["private_with_user"] = self.preview_of_user(channel.private_with_user)
        d["admin"] = self.preview_of_user(channel.admin)
        if channel.feedback_subject:
            d["feedback_subject"] = self.feedback_schema_from_orm(
                channel.feedback_subject
            )
        return schemas.Channel(**d)

    def report_schema_from_orm(self, report: models.Report) -> schemas.Report:
        base = schemas.ReportInDBBase.from_orm(report)
        d = base.dict()
        d["author"] = self.preview_of_user(report.author)
        return schemas.Report(**d)

    def feedback_schema_from_orm(self, f: models.Feedback) -> schemas.Feedback:
        ret = schemas.Feedback(
            id=f.id,
            created_at=f.created_at,
            description=f.description,
            status=f.status,
            has_screenshot=f.screenshot_blob is not None,
        )
        if f.user:
            ret.user = self.preview_of_user(f.user)
        elif f.user_email:
            ret.user_email = f.user_email
        return ret
