from typing import Literal

import logging

from chafan_core.app.infra import cache as infra_cache

logger = logging.getLogger(__name__)


def add_view_async(
    cached_layer_or_none,  # accepts CachedLayer or None; redis taken from infra when needed
    object_type: Literal["question", "answer", "profile", "article", "submission"],
    obj_id: int,
) -> None:
    """Enqueue a view bump. Prefer infra_cache; optional layer still accepted for callers."""
    assert object_type in ["question", "answer", "article", "submission"]
    redis_cli = None
    if cached_layer_or_none is not None and hasattr(cached_layer_or_none, "get_redis"):
        redis_cli = cached_layer_or_none.get_redis()
    infra_cache.bump_view(object_type, obj_id, redis_cli)


def add_view(
    object_uuid: str,
    object_type: Literal["question", "answer", "profile", "article", "submission"],
    user_id: int,
) -> int:
    logger.error("add_view is a deprecated function")
    return 0


from chafan_core.app.models.viewcount import ViewCountQuestion, ViewCountAnswer, ViewCountArticle, ViewCountSubmission


def get_viewcount_question(broker, row_id:int)->int:
    db = broker.get_db()
    row = db.query(ViewCountQuestion).filter(ViewCountQuestion.question_id == row_id).first()
    if row is None:
        return 0
    return row.view_count
def get_viewcount_article(broker, row_id:int)->int:
    db = broker.get_db()
    row = db.query(ViewCountArticle).filter(ViewCountArticle.article_id == row_id).first()
    if row is None:
        return 0
    return row.view_count
def get_viewcount_submission(broker, row_id:int)->int:
    db = broker.get_db()
    row = db.query(ViewCountSubmission).filter(ViewCountSubmission.submission_id == row_id).first()
    if row is None:
        return 0
    return row.view_count
def get_viewcount_answer(broker, row_id:int)->int:
    db = broker.get_db()
    row = db.query(ViewCountAnswer).filter(ViewCountAnswer.answer_id == row_id).first()
    if row is None:
        return 0
    return row.view_count
#object_type: Literal["question", "answer", "profile", "article", "submission"],
