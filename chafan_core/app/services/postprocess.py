"""Post-response side effects (notifications, feed fanout, webhooks)."""

import datetime
from typing import List, Optional

from sqlalchemy.orm.session import Session



from chafan_core.app import crud, models, schemas
from chafan_core.app.config import settings
from chafan_core.app.services import events
from chafan_core.app.infra.request_context import RequestContext
from chafan_core.app.recs.indexing import (
    compute_interesting_questions_ids_for_normal_user,
    compute_interesting_questions_ids_for_visitor_user,
    compute_interesting_users_ids_for_normal_user,
    compute_interesting_users_ids_for_visitor_user,
)
from chafan_core.app.schemas.event import (
    AnswerQuestionInternal,
    AnswerUpdateInternal,
    CommentAnswerInternal,
    CommentArticleInternal,
    CommentQuestionInternal,
    CommentSubmissionInternal,
    CreateAnswerSuggestEditInternal,
    CreateArticleInternal,
    CreateQuestionInternal,
    CreateSubmissionSuggestionInternal,
    EditQuestionInternal,
    EventInternal,
    MentionedInCommentInternal,
    ReplyCommentInternal,
)
from chafan_core.app.infra.runtime import execute_with_broker, execute_with_db
from chafan_core.app.text_analysis import (
    update_answer_keywords,
    update_question_keywords,
    update_submission_keywords,
)
from chafan_core.app.services.webhook_delivery import (
    SiteNewAnswerEvent,
    SiteNewQuestionEvent,
    SiteNewSubmissionEvent,
    call_webhook,
)
from chafan_core.db.session import SessionLocal
from chafan_core.utils.base import get_utc_now
import chafan_core.app.services.reputation as rep


import logging
logger = logging.getLogger(__name__)




def notify_mentioned_users(
    broker: RequestContext, comment: models.Comment, user_handles: List[str]
) -> None:
    utc_now = datetime.datetime.now(tz=datetime.timezone.utc)
    event = EventInternal(
        created_at=utc_now,
        content=MentionedInCommentInternal(
            subject_id=comment.author_id,
            comment_id=comment.id,
        ),
    )
    receiver_ids = set()
    for handle in user_handles:
        user = crud.user.get_by_handle(broker.get_db(), handle=handle)
        if user is None:
            continue
        receiver_ids.add(user.id)
    # The one audience events.distribute cannot resolve: the handles come from
    # the request payload, not from MentionedInCommentInternal.
    events.notify_users(broker, event, receiver_ids)


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


def postprocess_new_comment(
    comment_id: int, shared_to_timeline: bool, mentioned: Optional[List[str]]
) -> None:

    def runnable(broker: RequestContext) -> None:
        logger.info("postprocess_new_comment: id=" + str(comment_id))
        comment = crud.comment.get(broker.get_db(), id=comment_id)
        assert comment is not None
        if mentioned:
            notify_mentioned_users(broker, comment, mentioned)
        event = get_comment_event(comment)
        if event is not None:
            # The verb picks the notified author; Exclusion.SUBJECT reproduces
            # the author_id != receiver_id guards. The Activity is written only
            # when comment.shared_to_timeline, which distribute() derives, so
            # the shared_to_timeline argument is now only a caller's record of
            # what the request asked for.
            events.distribute(broker, event)

    execute_with_broker(runnable)


def postprocess_comment_update(
    comment_id: int,
    was_shared_to_timeline: bool,
    shared_to_timeline: bool = False,
    mentioned: Optional[List[str]] = None,
) -> None:
    print("postprocess_comment_update")

    def runnable(broker: RequestContext) -> None:
        comment = crud.comment.get(broker.get_db(), id=comment_id)
        assert comment is not None
        event = get_comment_event(comment)
        if not was_shared_to_timeline and shared_to_timeline and event:
            # Activity only: the comment's author was already notified when the
            # comment was created, and sharing it later must not notify again.
            # A distinct verb would express this better -- see 3b.
            events.distribute(broker, event, sinks=frozenset({events.Sink.ACTIVITY}))
        if mentioned:
            notify_mentioned_users(
                broker,
                comment,
                mentioned,
            )

    execute_with_broker(runnable)


def postprocess_question_common(question: models.Question) -> None:
    update_question_keywords(question)


def postprocess_new_question(question_id: int) -> None:
    print("postprocess_new_question")

    def runnable(broker: RequestContext) -> None:
        logger.info(f"run postprocess_new_question for qid={question_id}")
        question = crud.question.get(broker.get_db(), id=question_id)
        assert question is not None
        utc_now = datetime.datetime.now(tz=datetime.timezone.utc)
        event = EventInternal(
            created_at=utc_now,
            content=CreateQuestionInternal(
                subject_id=question.author.id,
                question_id=question.id,
            ),
        )
        rep.award_question_created(broker.get_db(), question.author, question)
        events.distribute(broker, event)
        postprocess_question_common(question)
        for webhook in question.site.webhooks:
            call_webhook(
                broker,
                webhook=webhook,
                event=SiteNewQuestionEvent(question=question),
            )

    execute_with_broker(runnable)


def postprocess_updated_question(question_id: int) -> None:
    print("postprocess_updated_question")

    def runnable(broker: RequestContext) -> None:
        question = crud.question.get(broker.get_db(), id=question_id)
        assert question is not None
        utc_now = datetime.datetime.now(tz=datetime.timezone.utc)
        assert question.editor_id is not None
        # Exclusion.SUBJECT drops the notification when the editor is the author.
        events.distribute(
            broker,
            EventInternal(
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


def postprocess_new_submission(submission_id: int) -> None:
    def runnable(broker: RequestContext) -> None:
        submission = crud.submission.get(broker.get_db(), id=submission_id)
        assert submission is not None
        # NOTE: crud.submission.create_with_author already wrote the Activity for
        # this submission, but nothing fans it out. See activity_policy.POLICY
        # ["create_submission"]. TODO event to feed? 2025-Sep-14
        rep.award_submission_created(broker.get_db(), submission.author, submission)
        postprocess_submission_common(submission)
        for webhook in submission.site.webhooks:
            call_webhook(
                broker,
                webhook=webhook,
                event=SiteNewSubmissionEvent(submission=submission),
            )

    execute_with_broker(runnable)


def postprocess_new_submission_suggestion(submission_suggestion_id: int) -> None:
    def runnable(broker: RequestContext) -> None:
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
        rep.award_submission_suggestion_created(
            broker.get_db(), submission_suggestion.author, submission_suggestion
        )
        events.distribute(broker, event)

    execute_with_broker(runnable)


def postprocess_accept_submission_suggestion(submission_suggestion_id: int) -> None:
    def runnable(db: Session) -> None:
        submission_suggestion = crud.submission_suggestion.get(
            db, id=submission_suggestion_id
        )
        assert submission_suggestion is not None
        # NOTE: no accept_submission_suggestion event is delivered anywhere.
        # See activity_policy.POLICY["accept_submission_suggestion"].
        rep.award_submission_suggestion_accepted(
            db, submission_suggestion.author, submission_suggestion
        )

    execute_with_db(SessionLocal(), runnable)


def postprocess_new_answer_suggest_edit(answer_suggest_edit_id: int) -> None:
    def runnable(broker: RequestContext) -> None:
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
        rep.award_answer_suggest_created(
            broker.get_db(), answer_suggest_edit.author, answer_suggest_edit
        )
        events.distribute(broker, event)

    execute_with_broker(runnable)


def postprocess_accept_answer_suggest_edit(answer_suggest_edit_id: int) -> None:
    def runnable(db: Session) -> None:
        answer_suggest_edit = crud.answer_suggest_edit.get(
            db, id=answer_suggest_edit_id
        )
        assert answer_suggest_edit is not None
        # NOTE: no accept_answer_suggest_edit event is delivered anywhere.
        # See activity_policy.POLICY["accept_answer_suggest_edit"].
        rep.award_answer_suggest_accepted(
            db, answer_suggest_edit.author, answer_suggest_edit
        )

    execute_with_db(SessionLocal(), runnable)


def postprocess_updated_submission(submission_id: int) -> None:
    def runnable(db: Session) -> None:
        submission = crud.submission.get(db, id=submission_id)
        assert submission is not None
        postprocess_submission_common(submission)

    execute_with_db(SessionLocal(), runnable)


def postprocess_new_answer(answer_id: int, was_published: bool) -> None:
    def runnable(broker: RequestContext) -> None:
        answer = crud.answer.get(broker.get_db(), id=answer_id)
        logger.info(f"postprocess_new_answer id={answer_id}, was_published={was_published}")
        assert answer is not None and answer.is_published
        utc_now = datetime.datetime.now(tz=datetime.timezone.utc)
        if not was_published:
            events.distribute(
                broker,
                EventInternal(
                    created_at=utc_now,
                    content=AnswerQuestionInternal(
                        subject_id=answer.author.id, answer_id=answer.id
                    ),
                ),
            )
        events.distribute(
            broker,
            EventInternal(
                created_at=utc_now,
                content=AnswerUpdateInternal(
                    subject_id=answer.author.id, answer_id=answer.id
                ),
            ),
        )
        update_answer_keywords(answer)
        for webhook in answer.site.webhooks:
            call_webhook(
                broker,
                webhook=webhook,
                event=SiteNewAnswerEvent(answer=answer),
            )

    execute_with_broker(runnable)


def postprocess_new_article(article_id: int) -> None:
    def runnable(broker: RequestContext) -> None:
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
        rep.award_article_created(broker.get_db(), article.author, article)
        events.distribute(broker, event_internal)
        # TODO FIXME TABLE activitity 里同一篇文章有两条记录。看起来无害就先不管了 2025-aug-04

    execute_with_broker(runnable)


def postprocess_updated_article(article_id: int, was_published: bool) -> None:
    def runnable(broker: RequestContext) -> None:
        article = crud.article.get(broker.get_db(), id=article_id)
        assert article is not None and article.is_published
        utc_now = datetime.datetime.now(tz=datetime.timezone.utc)
        if not was_published:
            # NOTE: Since is_published will not be reverted, thus this should only be delivered once
            # TODO: Implement the update subscription logic
            # Activity only: this path has never fanned out or notified, and
            # widening it here would not be a neutral change. 3b deletes this
            # emitter outright -- it is one of create_article's three.
            events.distribute(
                broker,
                EventInternal(
                    created_at=utc_now,
                    content=CreateArticleInternal(
                        subject_id=article.author.id,
                        article_id=article.id,
                    ),
                ),
                sinks=frozenset({events.Sink.ACTIVITY}),
            )

    execute_with_broker(runnable)


def postprocess_new_feedback(feedback_id: int) -> None:
    def runnable(db: Session) -> None:
        feedback = (
            db.query(models.Feedback).filter(models.Feedback.id == feedback_id).first()
        )
        assert feedback is not None

    logger.error("This is not supported")

    execute_with_db(SessionLocal(), runnable)


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


