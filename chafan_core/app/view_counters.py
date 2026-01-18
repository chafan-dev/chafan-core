import logging
from typing import Literal

logger = logging.getLogger(__name__)

# from chafan_core.app.cached_layer import CachedLayer


async def add_view_async(
    cached_layer,  # TODO 2025-07-20 due to cyclic dep, turn off this type hint: CachedLayer,
    object_type: Literal["question", "answer", "profile", "article", "submission"],
    obj_id: int,
) -> None:

    assert object_type in ["question", "answer", "article", "submission"]
    cached_layer.bump_view(object_type, obj_id)


def add_view(
    object_uuid: str,
    object_type: Literal["question", "answer", "profile", "article", "submission"],
    user_id: int,
) -> int:
    logger.error("add_view is a deprecated function")
    return 0


from chafan_core.app.models.viewcount import (
    ViewCountAnswer,
    ViewCountArticle,
    ViewCountQuestion,
    ViewCountSubmission,
)


def get_viewcount_question(broker, row_id: int) -> int:
    db = broker.get_db()
    row = (
        db.query(ViewCountQuestion)
        .filter(ViewCountQuestion.question_id == row_id)
        .first()
    )
    if row is None:
        return 0
    return row.view_count


def get_viewcount_article(broker, row_id: int) -> int:
    db = broker.get_db()
    row = (
        db.query(ViewCountArticle).filter(ViewCountArticle.article_id == row_id).first()
    )
    if row is None:
        return 0
    return row.view_count


def get_viewcount_submission(broker, row_id: int) -> int:
    db = broker.get_db()
    row = (
        db.query(ViewCountSubmission)
        .filter(ViewCountSubmission.submission_id == row_id)
        .first()
    )
    if row is None:
        return 0
    return row.view_count


def get_viewcount_answer(broker, row_id: int) -> int:
    db = broker.get_db()
    row = db.query(ViewCountAnswer).filter(ViewCountAnswer.answer_id == row_id).first()
    if row is None:
        return 0
    return row.view_count


# object_type: Literal["question", "answer", "profile", "article", "submission"],
