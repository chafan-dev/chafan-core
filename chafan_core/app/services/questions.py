"""Question domain service (reads)."""

from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from chafan_core.app import crud, models, schemas, user_permission
from chafan_core.utils.base import HTTPException_


def get_question_model(db: Session, uuid: str) -> Optional[models.Question]:
    return crud.question.get_by_uuid(db, uuid=uuid)


def get_question_model_http(db: Session, uuid: str) -> models.Question:
    question = get_question_model(db, uuid)
    if question is None:
        raise HTTPException_(
            status_code=400,
            detail="The question doesn't exist in the system.",
        )
    return question


def get_readable_question(
    db: Session,
    *,
    uuid: str,
    principal_id: Optional[int],
    cached_layer,
) -> Optional[models.Question]:
    """Fetch question if principal may read it (hidden-question gate)."""
    question = get_question_model(db, uuid)
    if question is None:
        return None
    if not user_permission.question_read_allowed(cached_layer, question, principal_id):
        return None
    return question


def question_schema(cached_layer, question: models.Question) -> Optional[schemas.Question]:
    return cached_layer.question_schema_from_orm(question)
