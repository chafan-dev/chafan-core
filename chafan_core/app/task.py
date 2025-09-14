import datetime
from typing import List, Optional

from collections import Counter
import dramatiq
from dramatiq.brokers.redis import RedisBroker
from sqlalchemy.orm.session import Session



from chafan_core.app import crud, models, schemas
from chafan_core.app.cached_layer import CachedLayer
from chafan_core.app.cached_layer import BUMP_VIEW_COUNT_QUEUE_CACHE_KEY
from chafan_core.app.config import settings
from chafan_core.app.feed import (
        new_activity_into_feed,
)
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
from chafan_core.app.models.activity import Activity
import chafan_core.app.rep_manager as rep


import logging
logger = logging.getLogger(__name__)


# TODO do we need a better way to get url?
redis_url = settings.REDIS_URL
logger.info(f"Create DramatiqBroker with redis {redis_url}")
dramatiq_broker = RedisBroker(url=redis_url, namespace="dramatiq")
dramatiq.set_broker(dramatiq_broker)



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

    def runnable(broker: DataBroker) -> None:
        logger.info("postprocess_new_comment: id=" + str(comment_id))
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


@dramatiq.actor
def postprocess_question_common(question: models.Question) -> None:
    update_question_keywords(question)


@dramatiq.actor
def postprocess_new_question(question_id: int) -> None:
    print("postprocess_new_question")

    def runnable(broker: DataBroker) -> None:
        logger.info(f"run postprocess_new_question for qid={question_id}")
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
        rep.new_question(question)

        question_ac = models.Activity(
                created_at=utc_now,
                site_id=question.site_id,
                event_json=event_json,
            )
        db = broker.get_db()
        db.add(question_ac)
        db.flush()
        db.commit()
        new_activity_into_feed(broker, question_ac)
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
        # TODO event to feed? 2025-Sep-14

        rep.new_submission(submission)
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
        rep.new_submission_suggestion(submission_suggestion)

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
        rep.accept_submission_suggestion(submission_suggestion)

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
        rep.new_answer_suggest(answer_suggest_edit)
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
        rep.accept_answer_suggest(answer_suggest_edit)

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
        logger.info(f"postprocess_new_answer id={answer_id}, was_published={was_published}")
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
            answer_ac: Activity = create_answer_activity(
                    answer=answer,
                    site_id=answer.question.site.id,
                    created_at=utc_now,
                )
            db = broker.get_db()
            db.add(answer_ac)
            db.flush()
            db.commit()
            new_activity_into_feed(broker, answer_ac)
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
        rep.new_article(article)
        for subscriber in article.article_column.subscribers:
            crud.notification.create_with_content(
                broker,
                event=event_internal,
                receiver_id=subscriber.id,
            )
        article_ac: Activity = create_article_activity(article=article, created_at=utc_now)
        db = broker.get_db()
        db.add(article_ac)
        db.flush()
        db.commit()
        new_activity_into_feed(broker, article_ac)
        # TODO FIXME TABLE activitity 里同一篇文章有两条记录。看起来无害就先不管了 2025-aug-04

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

    logger.error("This is not supported")

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


from chafan_core.app.models.viewcount import ViewCountQuestion, ViewCountAnswer, ViewCountArticle, ViewCountSubmission

# TODO Should I move this function to another file? 2025-07-23
def _add_viewcount_to_db(broker: DataBroker, key: str, count: int) -> None:
    segs = key.split(":")
    row_type = segs[0]
    row_id = segs[1]
    row_id = int(row_id)
    db = broker.get_db()

    def bump_question():
        prev = db.query(ViewCountQuestion).filter(ViewCountQuestion.question_id == row_id).first()
        if prev is None:
            prev = ViewCountQuestion()
            prev.question_id = row_id
            prev.view_count = 0

        prev.view_count += count
        db.add(prev)
        db.commit()

    def bump_answer():
        prev = db.query(ViewCountAnswer).filter(ViewCountAnswer.answer_id == row_id).first()
        if prev is None:
            prev = ViewCountAnswer()
            prev.answer_id = row_id
            prev.view_count = 0
        prev.view_count += count
        db.add(prev)
        db.commit()
    def bump_article():
        prev = db.query(ViewCountArticle).filter(ViewCountArticle.article_id == row_id).first()
        if prev is None:
            prev = ViewCountArticle()
            prev.article_id = row_id
            prev.view_count = 0
        prev.view_count += count
        db.add(prev)
        db.commit()

    def bump_submission():
        prev = db.query(ViewCountSubmission).filter(ViewCountSubmission.submission_id == row_id).first()
        if prev is None:
            prev = ViewCountSubmission()
            prev.submission_id = row_id
            prev.view_count = 0
        prev.view_count += count
        db.add(prev)
        db.commit()

    if row_type == "question":
        bump_question()
    elif row_type == "answer":
        bump_answer()
    elif row_type == "article":
        bump_article()
    elif row_type == "submission":
        bump_submission()
    else:
        logger.error(f"Unhandled viewcount key: {key}")




def write_view_count_to_db() -> None:
    def runnable(broker: DataBroker):
        logger.debug("write_view_count_to_db called")
        redis = broker.get_redis()
        views = redis.lrange(BUMP_VIEW_COUNT_QUEUE_CACHE_KEY, 0, -1)
        redis.delete(BUMP_VIEW_COUNT_QUEUE_CACHE_KEY) # Race condition here. But losing a few view counts is okay
        view_dict = Counter(views)
        logger.debug("get views " + str(view_dict))
        for k,v in view_dict.items():
            _add_viewcount_to_db(broker, k, v)
    execute_with_broker(runnable)
    return None


import os
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy.orm.session import Session
from whoosh import writing  # type: ignore
from whoosh.index import create_in  # type: ignore
from whoosh.index import open_dir

from chafan_core.app import crud
from chafan_core.app.config import settings
from chafan_core.app.search import schemas
from chafan_core.app.task_utils import execute_with_db
from chafan_core.db.session import ReadSessionLocal
from chafan_core.utils.constants import indexed_object_T

@contextmanager
def _index_rewriter(index_type: indexed_object_T) -> Iterator[writing.IndexWriter]:
    index_dir = settings.SEARCH_INDEX_FILESYSTEM_PATH + "/" + index_type
    schema = schemas[index_type]
    if os.path.exists(index_dir):
        ix = open_dir(index_dir)
    else:
        # Initialize search index
        os.makedirs(index_dir)
        ix = create_in(index_dir, schema)
    writer = ix.writer()

    try:
        yield writer
    finally:
        writer.commit(mergetype=writing.CLEAR)


def refresh_search_index() -> None:
    def runnable(db: Session) -> None:
        logger.info("refresh_search_index executed")
        with _index_rewriter("question") as writer:
            for q in crud.question.get_all_valid(db):
                writer.add_document(
                    id=str(q.id), title=q.title, description_text=q.description_text
                )
        with _index_rewriter("site") as writer:
            for s in crud.site.get_all(db):
                writer.add_document(
                    id=str(s.id),
                    name=s.name,
                    description=s.description,
                    subdomain=s.subdomain,
                )
        with _index_rewriter("submission") as writer:
            for submission in crud.submission.get_all_valid(db):
                writer.add_document(
                    id=str(submission.id),
                    title=submission.title,
                    description_text=submission.description_text,
                )
        with _index_rewriter("answer") as writer:
            for a in crud.answer.get_all_published(db):
                writer.add_document(
                    id=str(a.id),
                    body_prerendered_text=a.body_prerendered_text,
                    question_title=a.question.title,
                    question_description_text=a.question.description_text,
                )
        with _index_rewriter("article") as writer:
            for article in crud.article.get_all_published(db):
                writer.add_document(
                    id=str(article.id),
                    title=article.title,
                    body_text=article.body_text,
                )

    execute_with_db(ReadSessionLocal(), runnable)
