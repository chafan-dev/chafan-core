"""View-count Redis drain → Postgres."""

from __future__ import annotations

from collections import Counter
import logging

from chafan_core.app.infra.cache import BUMP_VIEW_COUNT_QUEUE_CACHE_KEY
from chafan_core.app.infra.request_context import RequestContext
from chafan_core.app.infra.runtime import execute_with_broker
from chafan_core.app.models.viewcount import (
    ViewCountAnswer,
    ViewCountArticle,
    ViewCountQuestion,
    ViewCountSubmission,
)

logger = logging.getLogger(__name__)

# TODO Should I move this function to another file? 2025-07-23
def _add_viewcount_to_db(broker: RequestContext, key: str, count: int) -> None:
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
        db.flush()

    def bump_answer():
        prev = db.query(ViewCountAnswer).filter(ViewCountAnswer.answer_id == row_id).first()
        if prev is None:
            prev = ViewCountAnswer()
            prev.answer_id = row_id
            prev.view_count = 0
        prev.view_count += count
        db.add(prev)
        db.flush()
    def bump_article():
        prev = db.query(ViewCountArticle).filter(ViewCountArticle.article_id == row_id).first()
        if prev is None:
            prev = ViewCountArticle()
            prev.article_id = row_id
            prev.view_count = 0
        prev.view_count += count
        db.add(prev)
        db.flush()

    def bump_submission():
        prev = db.query(ViewCountSubmission).filter(ViewCountSubmission.submission_id == row_id).first()
        if prev is None:
            prev = ViewCountSubmission()
            prev.submission_id = row_id
            prev.view_count = 0
        prev.view_count += count
        db.add(prev)
        db.flush()

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
    def runnable(broker: RequestContext):
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


