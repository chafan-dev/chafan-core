"""Home/discovery feed content service."""

from __future__ import annotations

import datetime
import json
from typing import List

from fastapi.encoders import jsonable_encoder
from pydantic import TypeAdapter
from sqlalchemy.orm.session import Session

from chafan_core.app import crud, models, schemas
from chafan_core.app.common import get_redis_cli, is_dev
from chafan_core.app.model_utils import get_live_answers_of_question
from chafan_core.app.recs import indexed_layer
from chafan_core.app.task_utils import execute_with_db
from chafan_core.db.session import SessionLocal
from chafan_core.utils.base import filter_not_none
from chafan_core.utils.constants import MAX_FEATURED_ANSWERS_LIMIT


def pinned_questions(ctx) -> List[schemas.QuestionPreview]:
    redis = ctx.get_redis()
    key = "chafan:api:/discovery/pinned-questions"
    value = redis.get(key)
    if value:
        return TypeAdapter(List[schemas.QuestionPreview]).validate_json(value)

    mat = ctx.materializer

    def runnable(db: Session) -> List[schemas.QuestionPreview]:
        questions = crud.question.get_placed_at_home(db)
        data = filter_not_none([mat.preview_of_question(q) for q in questions])
        if not is_dev():
            redis.set(
                key, json.dumps(jsonable_encoder(data)), ex=datetime.timedelta(hours=12)
            )
        return data

    return execute_with_db(SessionLocal(), runnable)


def _get_pending_questions(ctx) -> List[schemas.QuestionPreview]:
    mat = ctx.materializer
    if ctx.principal_id:
        current_user = crud.user.get(ctx.get_db(), id=ctx.principal_id)
        assert current_user is not None
        questions: List[schemas.QuestionPreview] = []
        for profile in current_user.profiles:
            questions.extend(
                filter_not_none(
                    [
                        mat.preview_of_question(q)
                        for q in profile.site.questions
                        if len(get_live_answers_of_question(q)) == 0 and not q.is_hidden
                    ]
                )
            )
        return questions
    questions = []
    for site in crud.site.get_all_public_readable(ctx.get_db()):
        questions.extend(
            filter_not_none(
                [
                    mat.preview_of_question(q)
                    for q in site.questions
                    if len(get_live_answers_of_question(q)) == 0 and not q.is_hidden
                ]
            )[:10]
        )
    return questions


def pending_questions(ctx) -> List[schemas.QuestionPreview]:
    redis = get_redis_cli()
    key = f"chafan:pending-questions-for-user:{ctx.principal_id}"
    value = redis.get(key)
    if value is not None:
        return TypeAdapter(List[schemas.QuestionPreview]).validate_json(value)
    data = _get_pending_questions(ctx)
    if not is_dev():
        redis.set(
            key, json.dumps(jsonable_encoder(data)), ex=datetime.timedelta(hours=24)
        )
    return data


def interesting_questions(ctx) -> List[schemas.QuestionPreview]:
    return indexed_layer.get_interesting_questions(ctx)


def interesting_users(ctx) -> List[schemas.UserPreview]:
    return indexed_layer.get_interesting_users(ctx)


def featured_answers(
    ctx, *, skip: int = 0, limit: int = MAX_FEATURED_ANSWERS_LIMIT
) -> List[schemas.AnswerPreview]:
    db = ctx.get_db()
    stream = (
        db.query(models.Answer)
        .filter(models.Answer.featured_at != None)
        .order_by(models.Answer.featured_at.desc())
    )
    stream = stream[skip : skip + limit]
    return filter_not_none([ctx.preview_of_answer(a) for a in stream])
