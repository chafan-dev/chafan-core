"""Topic domain service."""

from __future__ import annotations

import datetime
import json
from typing import List

from fastapi.encoders import jsonable_encoder
from pydantic import TypeAdapter
from sqlalchemy.orm import Session

from chafan_core.app import crud, models, schemas
from chafan_core.app.common import get_redis_cli
from chafan_core.app.infra.runtime import execute_with_db
from chafan_core.db.session import SessionLocal
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
    mat = ctx.principal_view
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


# TODO Remove or modify this. Should not depend on redis directly
def get_category_topics() -> List[schemas.Topic]:
    """Category topics, cached in redis for a day.

    Runs on its own session rather than the request's -- kept as-is; changing
    it would change when the cache is populated relative to the request.
    """
    redis = get_redis_cli()
    key = "chafan:category-topics"
    value = redis.get(key)
    if value is not None:
        return TypeAdapter(List[schemas.Topic]).validate_json(value)

    def runnable(db: Session) -> List[schemas.Topic]:
        data = [schemas.Topic.from_orm(t) for t in crud.topic.get_category_topics(db)]
        redis.set(
            key, json.dumps(jsonable_encoder(data)), ex=datetime.timedelta(days=1)
        )
        return data

    data = execute_with_db(SessionLocal(), runnable)
    assert data is not None
    return data
