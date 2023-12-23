import datetime
from typing import List, Optional

import dramatiq
from dramatiq.brokers.rabbitmq import RabbitmqBroker
from sqlalchemy.orm.session import Session

from chafan_core.app import crud, models, schemas
from chafan_core.app.aws_ses import send_email_ses
from chafan_core.app.cached_layer import CachedLayer
from chafan_core.app.config import get_mq_url, settings
from chafan_core.app.crud.crud_activity import (
    create_answer_activity,
    create_article_activity,
)
from chafan_core.app.data_broker import DataBroker
from chafan_core.app.recs.indexing import (
    compute_interesting_questions_ids_for_normal_user,
    compute_interesting_questions_ids_for_visitor_user,
    compute_interesting_users_ids_for_normal_user,
    compute_interesting_users_ids_for_visitor_user,
)
from chafan_core.app.schemas.event import (
    AcceptAnswerSuggestEditInternal,
    AcceptSubmissionSuggestionInternal,
    AnswerQuestionInternal,
    AnswerUpdateInternal,
    CommentAnswerInternal,
    CommentArticleInternal,
    CommentQuestionInternal,
    CommentSubmissionInternal,
    CreateAnswerSuggestEditInternal,
    CreateArticleInternal,
    CreateQuestionInternal,
    CreateSubmissionInternal,
    CreateSubmissionSuggestionInternal,
    EditQuestionInternal,
    EventInternal,
    MentionedInCommentInternal,
    ReplyCommentInternal,
    SiteBroadcastInternal,
    SystemBroadcast,
)
from chafan_core.app.task_utils import execute_with_broker, execute_with_db
from chafan_core.app.text_analysis import (
    update_answer_keywords,
    update_question_keywords,
    update_submission_keywords,
)
from chafan_core.app.webhook_utils import (
    SiteNewAnswerEvent,
    SiteNewQuestionEvent,
    SiteNewSubmissionEvent,
    call_webhook,
)
from chafan_core.db.session import SessionLocal
from chafan_core.utils.base import TaskStatus, get_utc_now

rabbitmq_broker = RabbitmqBroker(url=get_mq_url())
dramatiq.set_broker(rabbitmq_broker)


@dramatiq.actor
def super_broadcast(task_id: int, message_body: str) -> None:
    def runnable(broker: DataBroker) -> None:
        task = broker.get_db().query(models.Task).filter_by(id=task_id).first()
        assert task is not None
        for user in crud.user.get_all_active_users(broker.get_db()):
            utc_now = datetime.datetime.now(tz=datetime.timezone.utc)
            notification = crud.notification.create_with_content(
                broker,
                event=EventInternal(
                    created_at=utc_now,
                    content=SystemBroadcast(
                        message=message_body,
                    ),
                ),
                receiver_id=user.id,
            )
            print(
                f"Broadcasting system notification {notification.id} to user {user.id} ..."
            )
        task.status = TaskStatus.FINISHED

    execute_with_broker(runnable)


@dramatiq.actor
def site_broadcast(task_id: int, submission_id: int, site_id: int) -> None:
    def runnable(broker: DataBroker) -> None:
        task = broker.get_db().query(models.Task).filter_by(id=task_id).first()
        assert task is not None
        site = crud.site.get_by_id(broker.get_db(), id=site_id)
        assert site is not None
        for membership in site.profiles:
            utc_now = datetime.datetime.now(tz=datetime.timezone.utc)
            notification = crud.notification.create_with_content(
                broker,
                event=EventInternal(
                    created_at=utc_now,
                    content=SiteBroadcastInternal(
                        submission_id=submission_id,
                        site_id=site.id,
                    ),
                ),
                receiver_id=membership.owner_id,
            )
            print(
                f"Broadcasting site notification {notification.id} to user {membership.owner_id} ..."
            )
        task.status = TaskStatus.FINISHED

    execute_with_broker(runnable)


def notify_mentioned_users(
    broker: DataBroker, comment: models.Comment, user_handles: List[str]
) -> None:
    utc_now = datetime.datetime.now(tz=datetime.timezone.utc)
    event = EventInternal(
        created_at=utc_now,
        content=MentionedInCommentInternal(
            subject_id=comment.author_id,
            comment_id=comment.id,
        ),
    )
    for handle in user_handles:
        user = crud.user.get_by_handle(broker.get_db(), handle=handle)
        if user is None:
            continue
        crud.notification.create_with_content(
            broker,
            receiver_id=user.id,
            event=event,
        )


def get_comment_event(comment: models.Comment) -> Optional[EventInternal]:
    if comment.question is not None:
        return EventInternal(
            created_at=comment.updated_at,
            content=CommentQuestionInternal(
                subject_id=comment.author_id,
                comment_id=comment.id,
                question_id=comment.question.id,
            ),
        )
    if comment.submission is not None:
        return EventInternal(
            created_at=comment.updated_at,
            content=CommentSubmissionInternal(
                subject_id=comment.author_id,
                comment_id=comment.id,
                submission_id=comment.submission.id,
            ),
        )
    if comment.answer is not None:
        return EventInternal(
            created_at=comment.updated_at,
            content=CommentAnswerInternal(
                subject_id=comment.author_id,
                comment_id=comment.id,
                answer_id=comment.answer.id,
            ),
        )
    if comment.article is not None:
        return EventInternal(
            created_at=comment.updated_at,
            content=CommentArticleInternal(
                subject_id=comment.author_id,
                comment_id=comment.id,
                article_id=comment.article.id,
            ),
        )
    if comment.parent_comment is not None:
        return EventInternal(
            created_at=comment.updated_at,
            content=ReplyCommentInternal(
                subject_id=comment.author_id,
                reply_id=comment.id,
                parent_comment_id=comment.parent_comment.id,
            ),
        )
    return None


@dramatiq.actor
def postprocess_new_comment(
    comment_id: int, shared_to_timeline: bool, mentioned: Optional[List[str]]
) -> None:
    print("postprocess_new_comment")

    def runnable(broker: DataBroker) -> None:
        comment = crud.comment.get(broker.get_db(), id=comment_id)
        assert comment is not None
        if mentioned:
            notify_mentioned_users(broker, comment, mentioned)
        event = get_comment_event(comment)
        if event:
            if (
                comment.question is not None
                and comment.author_id != comment.question.author_id
            ):
                crud.notification.create_with_content(
                    broker,
                    receiver_id=comment.question.author.id,
                    event=event,
                )
            if (
                comment.submission is not None
                and comment.author_id != comment.submission.author_id
            ):
                crud.notification.create_with_content(
                    broker,
                    receiver_id=comment.submission.author.id,
                    event=event,
                )
            if (
                comment.answer is not None
                and comment.author_id != comment.answer.author_id
            ):
                crud.notification.create_with_content(
                    broker,
                    receiver_id=comment.answer.author.id,
                    event=event,
                )
            if (
                comment.article is not None
                and comment.author_id != comment.article.author_id
            ):
                crud.notification.create_with_content(
                    broker,
                    receiver_id=comment.article.author.id,
                    event=event,
                )
            if (
                comment.parent_comment is not None
                and comment.author_id != comment.parent_comment.author_id
            ):
                crud.notification.create_with_content(
                    broker,
                    receiver_id=comment.parent_comment.author.id,
                    event=event,
                )
        if shared_to_timeline and event is not None:
            broker.get_db().add(
                models.Activity(
                    created_at=comment.updated_at,
                    site_id=comment.site_id,
                    event_json=event.json(),
                )
            )
            broker.get_db().commit()

    execute_with_broker(runnable)


@dramatiq.actor
def postprocess_comment_update(
    comment_id: int,
    was_shared_to_timeline: bool,
    shared_to_timeline: bool = False,
    mentioned: Optional[List[str]] = None,
) -> None:
    print("postprocess_comment_update")

    def runnable(broker: DataBroker) -> None:
        comment = crud.comment.get(broker.get_db(), id=comment_id)
        assert comment is not None
        event = get_comment_event(comment)
        if not was_shared_to_timeline and shared_to_timeline and event:
            broker.get_db().add(
                models.Activity(
                    created_at=event.created_at,
                    site_id=comment.site_id,
                    event_json=event.json(),
                )
            )
            broker.get_db().commit()
        if mentioned:
            notify_mentioned_users(
                broker,
                comment,
                mentioned,
            )

    execute_with_broker(runnable)


def postprocess_question_common(question: models.Question) -> None:
    update_question_keywords(question)


@dramatiq.actor
def postprocess_new_question(question_id: int) -> None:
    print("postprocess_new_question")

    def runnable(broker: DataBroker) -> None:
        question = crud.question.get(broker.get_db(), id=question_id)
        assert question is not None
        utc_now = datetime.datetime.now(tz=datetime.timezone.utc)
        event_json = EventInternal(
            created_at=utc_now,
            content=CreateQuestionInternal(
                subject_id=question.author.id,
                question_id=question.id,
            ),
        ).json()
        crud.coin_payment.make_payment(
            broker.get_db(),
            obj_in=schemas.CoinPaymentCreate(
                payee_id=question.site.moderator_id,
                amount=question.site.create_question_coin_deduction,
                event_json=event_json,
            ),
            payer=question.author,
            payee=question.site.moderator,
        )
        broker.get_db().add(
            models.Activity(
                created_at=utc_now,
                site_id=question.site_id,
                event_json=event_json,
            )
        )
        postprocess_question_common(question)
        for webhook in question.site.webhooks:
            call_webhook(
                CachedLayer(broker, None),
                webhook=webhook,
                event=SiteNewQuestionEvent(question=question),
            )

    execute_with_broker(runnable)


@dramatiq.actor
def postprocess_updated_question(question_id: int) -> None:
    print("postprocess_updated_question")

    def runnable(broker: DataBroker) -> None:
        question = crud.question.get(broker.get_db(), id=question_id)
        assert question is not None
        utc_now = datetime.datetime.now(tz=datetime.timezone.utc)
        assert question.editor_id is not None
        if question.author_id != question.editor_id:
            crud.notification.create_with_content(
                broker,
                receiver_id=question.author_id,
                event=EventInternal(
                    created_at=utc_now,
                    content=EditQuestionInternal(
                        subject_id=question.editor_id,
                        question_id=question.id,
                    ),
                ),
            )
        postprocess_question_common(question)

    execute_with_broker(runnable)


def postprocess_submission_common(submission: models.Submission) -> None:
    update_submission_keywords(submission)


@dramatiq.actor
def postprocess_new_submission(submission_id: int) -> None:
    def runnable(broker: DataBroker) -> None:
        submission = crud.submission.get(broker.get_db(), id=submission_id)
        assert submission is not None
        utc_now = datetime.datetime.now(tz=datetime.timezone.utc)
        event_json = EventInternal(
            created_at=utc_now,
            content=CreateSubmissionInternal(
                subject_id=submission.author.id,
                submission_id=submission.id,
            ),
        ).json()

        crud.coin_payment.make_payment(
            broker.get_db(),
            obj_in=schemas.CoinPaymentCreate(
                payee_id=submission.site.moderator_id,
                amount=submission.site.create_submission_coin_deduction,
                event_json=event_json,
            ),
            payer=submission.author,
            payee=submission.site.moderator,
        )
        postprocess_submission_common(submission)
        for webhook in submission.site.webhooks:
            call_webhook(
                CachedLayer(broker, None),
                webhook=webhook,
                event=SiteNewSubmissionEvent(submission=submission),
            )

    execute_with_broker(runnable)


@dramatiq.actor
def postprocess_new_submission_suggestion(submission_suggestion_id: int) -> None:
    def runnable(broker: DataBroker) -> None:
        submission_suggestion = crud.submission_suggestion.get(
            broker.get_db(), id=submission_suggestion_id
        )
        assert submission_suggestion is not None
        utc_now = datetime.datetime.now(tz=datetime.timezone.utc)
        event = EventInternal(
            created_at=utc_now,
            content=CreateSubmissionSuggestionInternal(
                subject_id=submission_suggestion.author.id,
                submission_suggestion_id=submission_suggestion.id,
            ),
        )
        site = submission_suggestion.submission.site
        crud.coin_payment.make_payment(
            broker.get_db(),
            obj_in=schemas.CoinPaymentCreate(
                payee_id=site.moderator_id,
                amount=site.create_suggestion_coin_deduction,
                event_json=event.json(),
            ),
            payer=submission_suggestion.author,
            payee=site.moderator,
        )
        crud.notification.create_with_content(
            broker,
            receiver_id=submission_suggestion.submission.author_id,
            event=event,
        )

    execute_with_broker(runnable)


@dramatiq.actor
def postprocess_accept_submission_suggestion(submission_suggestion_id: int) -> None:
    def runnable(db: Session) -> None:
        submission_suggestion = crud.submission_suggestion.get(
            db, id=submission_suggestion_id
        )
        assert submission_suggestion is not None
        utc_now = datetime.datetime.now(tz=datetime.timezone.utc)
        event_json = EventInternal(
            created_at=utc_now,
            content=AcceptSubmissionSuggestionInternal(
                subject_id=submission_suggestion.author.id,
                submission_suggestion_id=submission_suggestion.id,
            ),
        ).json()
        crud.coin_payment.make_payment(
            db,
            obj_in=schemas.CoinPaymentCreate(
                payee_id=submission_suggestion.author_id,
                amount=submission_suggestion.submission.site.create_suggestion_coin_deduction,
                event_json=event_json,
            ),
            payer=submission_suggestion.submission.author,
            payee=submission_suggestion.author,
        )

    execute_with_db(SessionLocal(), runnable)


@dramatiq.actor
def postprocess_new_answer_suggest_edit(answer_suggest_edit_id: int) -> None:
    def runnable(broker: DataBroker) -> None:
        answer_suggest_edit = crud.answer_suggest_edit.get(
            broker.get_db(), id=answer_suggest_edit_id
        )
        assert answer_suggest_edit is not None
        utc_now = get_utc_now()
        event = EventInternal(
            created_at=utc_now,
            content=CreateAnswerSuggestEditInternal(
                subject_id=answer_suggest_edit.author.id,
                answer_suggest_edit_id=answer_suggest_edit.id,
            ),
        )
        site = answer_suggest_edit.answer.site
        crud.coin_payment.make_payment(
            broker.get_db(),
            obj_in=schemas.CoinPaymentCreate(
                payee_id=site.moderator_id,
                amount=site.create_suggestion_coin_deduction,
                event_json=event.json(),
            ),
            payer=answer_suggest_edit.author,
            payee=site.moderator,
        )
        crud.notification.create_with_content(
            broker,
            receiver_id=answer_suggest_edit.answer.author_id,
            event=event,
        )

    execute_with_broker(runnable)


@dramatiq.actor
def postprocess_accept_answer_suggest_edit(answer_suggest_edit_id: int) -> None:
    def runnable(db: Session) -> None:
        answer_suggest_edit = crud.answer_suggest_edit.get(
            db, id=answer_suggest_edit_id
        )
        assert answer_suggest_edit is not None
        utc_now = get_utc_now()
        event_json = EventInternal(
            created_at=utc_now,
            content=AcceptAnswerSuggestEditInternal(
                subject_id=answer_suggest_edit.author.id,
                answer_suggest_edit_id=answer_suggest_edit.id,
            ),
        ).json()
        crud.coin_payment.make_payment(
            db,
            obj_in=schemas.CoinPaymentCreate(
                payee_id=answer_suggest_edit.author_id,
                amount=answer_suggest_edit.answer.site.create_suggestion_coin_deduction,
                event_json=event_json,
            ),
            payer=answer_suggest_edit.answer.author,
            payee=answer_suggest_edit.author,
        )

    execute_with_db(SessionLocal(), runnable)


@dramatiq.actor
def postprocess_updated_submission(submission_id: int) -> None:
    def runnable(db: Session) -> None:
        submission = crud.submission.get(db, id=submission_id)
        assert submission is not None
        postprocess_submission_common(submission)

    execute_with_db(SessionLocal(), runnable)


@dramatiq.actor
def postprocess_new_answer(answer_id: int, was_published: bool) -> None:
    def runnable(broker: DataBroker) -> None:
        answer = crud.answer.get(broker.get_db(), id=answer_id)
        assert answer is not None and answer.is_published
        utc_now = datetime.datetime.now(tz=datetime.timezone.utc)
        if not was_published:
            if answer.question.author.id != answer.author.id:
                crud.notification.create_with_content(
                    broker,
                    event=EventInternal(
                        created_at=utc_now,
                        content=AnswerQuestionInternal(
                            subject_id=answer.author.id, answer_id=answer.id
                        ),
                    ),
                    receiver_id=answer.question.author.id,
                )
            broker.get_db().add(
                create_answer_activity(
                    answer=answer,
                    site_id=answer.question.site.id,
                    created_at=utc_now,
                )
            )
            broker.get_db().commit()
        for user in answer.bookmarkers:
            crud.notification.create_with_content(
                broker,
                event=EventInternal(
                    created_at=utc_now,
                    content=AnswerUpdateInternal(
                        subject_id=answer.author.id, answer_id=answer.id
                    ),
                ),
                receiver_id=user.id,
            )
        update_answer_keywords(answer)
        for webhook in answer.site.webhooks:
            call_webhook(
                CachedLayer(broker),
                webhook=webhook,
                event=SiteNewAnswerEvent(answer=answer),
            )

    execute_with_broker(runnable)


@dramatiq.actor
def postprocess_new_article(article_id: int) -> None:
    def runnable(broker: DataBroker) -> None:
        article = crud.article.get(broker.get_db(), id=article_id)
        assert article is not None and article.is_published
        superuser = crud.user.get_superuser(broker.get_db())
        utc_now = datetime.datetime.now(tz=datetime.timezone.utc)
        event = CreateArticleInternal(
            subject_id=article.author.id,
            article_id=article.id,
        )
        event_internal = EventInternal(
            created_at=utc_now,
            content=event,
        )
        crud.coin_payment.make_payment(
            broker.get_db(),
            obj_in=schemas.CoinPaymentCreate(
                payee_id=superuser.id,
                amount=settings.CREATE_ARTICLE_COIN_DEDUCTION,
                event_json=event_internal.json(),
            ),
            payer=article.author,
            payee=superuser,
        )
        for subscriber in article.article_column.subscribers:
            crud.notification.create_with_content(
                broker,
                event=event_internal,
                receiver_id=subscriber.id,
            )
        broker.get_db().add(
            create_article_activity(article=article, created_at=utc_now)
        )

    execute_with_broker(runnable)


@dramatiq.actor
def postprocess_updated_article(article_id: int, was_published: bool) -> None:
    def runnable(db: Session) -> None:
        article = crud.article.get(db, id=article_id)
        assert article is not None and article.is_published
        utc_now = datetime.datetime.now(tz=datetime.timezone.utc)
        if not was_published:
            # NOTE: Since is_published will not be reverted, thus this should only be delivered once
            # TODO: Implement the update subscription logic
            db.add(create_article_activity(article=article, created_at=utc_now))

    execute_with_db(SessionLocal(), runnable)


@dramatiq.actor
def postprocess_new_feedback(feedback_id: int) -> None:
    def runnable(db: Session) -> None:
        feedback = (
            db.query(models.Feedback).filter(models.Feedback.id == feedback_id).first()
        )
        assert feedback is not None
        send_email_ses(
            email_to="root@cha.fan",
            subject="New feedback",
            body_html=f"ID: {feedback.id}\n{feedback.description}",
        )

    execute_with_db(SessionLocal(), runnable)


@dramatiq.actor
def refresh_interesting_question_ids_for_user(user_id: int) -> None:
    def runnable(db: Session) -> None:
        user = crud.user.get(db, user_id)
        if user is None:
            return
        if user_id == settings.VISITOR_USER_ID:
            user.interesting_question_ids = (
                compute_interesting_questions_ids_for_visitor_user(db)
            )
        else:
            user.interesting_question_ids = (
                compute_interesting_questions_ids_for_normal_user(db, user)
            )
        user.interesting_question_ids_updated_at = get_utc_now()

    execute_with_db(SessionLocal(), runnable)


@dramatiq.actor
def refresh_interesting_user_ids_for_user(user_id: int) -> None:
    def runnable(db: Session) -> None:
        user = crud.user.get(db, user_id)
        if user is None:
            return
        if user_id == settings.VISITOR_USER_ID:
            user.interesting_user_ids = compute_interesting_users_ids_for_visitor_user(
                db
            )
        else:
            user.interesting_user_ids = compute_interesting_users_ids_for_normal_user(
                db, user
            )
        user.interesting_user_ids_updated_at = get_utc_now()

    execute_with_db(SessionLocal(), runnable)
