"""Topic domain service."""

from __future__ import annotations

from typing import List

from sqlalchemy.orm import Session

from chafan_core.app import crud, models, schemas
from chafan_core.utils.base import HTTPException_, filter_not_none


def get_topic(db: Session, uuid: str) -> models.Topic:
    topic = crud.topic.get_by_uuid(db, uuid=uuid)
    if topic is None:
        raise HTTPException_(
            status_code=400,
            detail="The topic doesn't exist in the system.",
        )
    return topic


def create_topic(db: Session, *, name: str) -> models.Topic:
    return crud.topic.get_or_create(db, name=name)


def list_topic_questions(
    ctx, *, uuid: str, skip: int = 0, limit: int = 100
) -> List[schemas.QuestionPreview]:
    db = ctx.get_db()
    topic = get_topic(db, uuid)
    # FIXME: expensive
    questions: List[models.Question] = topic.questions[skip : (skip + limit)]
    mat = ctx.materializer
    return filter_not_none(
        [
            mat.preview_of_question(question)
            for question in questions
            if not question.is_hidden
        ]
    )


def list_sub_topics(db: Session, uuid: str) -> List[models.Topic]:
    topic = get_topic(db, uuid)
    return list(topic.child_topics)
