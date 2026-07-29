"""Read side of the per-object view counters.

The write side (Redis queue drain into these tables) lives in
``services/viewcounts.py``; these are the plain reads used by responders.
"""

from sqlalchemy.orm import Session

from chafan_core.app.models.viewcount import (
    ViewCountAnswer,
    ViewCountArticle,
    ViewCountQuestion,
    ViewCountSubmission,
)


def get_viewcount_question(db: Session, row_id: int) -> int:
    row = (
        db.query(ViewCountQuestion)
        .filter(ViewCountQuestion.question_id == row_id)
        .first()
    )
    if row is None:
        return 0
    return row.view_count


def get_viewcount_article(db: Session, row_id: int) -> int:
    row = (
        db.query(ViewCountArticle).filter(ViewCountArticle.article_id == row_id).first()
    )
    if row is None:
        return 0
    return row.view_count


def get_viewcount_submission(db: Session, row_id: int) -> int:
    row = (
        db.query(ViewCountSubmission)
        .filter(ViewCountSubmission.submission_id == row_id)
        .first()
    )
    if row is None:
        return 0
    return row.view_count


def get_viewcount_answer(db: Session, row_id: int) -> int:
    row = db.query(ViewCountAnswer).filter(ViewCountAnswer.answer_id == row_id).first()
    if row is None:
        return 0
    return row.view_count
