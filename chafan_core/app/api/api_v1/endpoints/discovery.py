import datetime
import json
from typing import Any, List, Union

from fastapi import APIRouter, Depends, Query
from fastapi.encoders import jsonable_encoder
from pydantic import TypeAdapter
from sqlalchemy.orm.session import Session

from chafan_core.app import crud, models, schemas
from chafan_core.app.api import deps
from chafan_core.app.infra.request_context import RequestContext
from chafan_core.app.common import get_redis_cli, is_dev
from chafan_core.app.model_utils import get_live_answers_of_question
from chafan_core.app.recs import indexed_layer
from chafan_core.app.task_utils import execute_with_db
from chafan_core.db.session import ReadSessionLocal
from chafan_core.utils.base import filter_not_none
from chafan_core.utils.constants import MAX_FEATURED_ANSWERS_LIMIT

SITE_INTERESTING_QUESTION_IDS_CACHE_KEY = "chafan:site-interesting-questions:{site_id}"


router = APIRouter()


@router.get(
    "/pinned-questions/", response_model=List[schemas.QuestionPreview]
)
def pinned_questions(
    ctx: RequestContext = Depends(deps.get_request_context),
) -> Any:
    redis = ctx.get_redis()
    key = f"chafan:api:/discovery/pinned-questions"
    value = redis.get(key)
    if value:
        return TypeAdapter(List[schemas.QuestionPreview]).validate_json(value)

    def runnable(db: Session) -> List[schemas.QuestionPreview]:
        questions = crud.question.get_placed_at_home(db)
        data = filter_not_none(
            [
                ctx.materializer.preview_of_question(q)
                for q in questions
            ]
        )
        if not is_dev():
            redis.set(
                key, json.dumps(jsonable_encoder(data)), ex=datetime.timedelta(hours=12)
            )
        return data

    return execute_with_db(ReadSessionLocal(), runnable)


def _get_pending_questions(
    ctx: RequestContext,
) -> List[schemas.QuestionPreview]:
    if ctx.principal_id:
        current_user = crud.user.get(
            ctx.get_db(), id=ctx.principal_id
        )
        assert current_user is not None
        questions: List[schemas.QuestionPreview] = []
        for profile in current_user.profiles:
            questions.extend(
                filter_not_none(
                    [
                        ctx.materializer.preview_of_question(q)
                        for q in profile.site.questions
                        if len(get_live_answers_of_question(q)) == 0 and not q.is_hidden
                    ]
                )
            )
        return questions
    else:
        questions: List[schemas.QuestionPreview] = []
        for site in crud.site.get_all_public_readable(ctx.get_db()):
            questions.extend(
                filter_not_none(
                    [
                        ctx.materializer.preview_of_question(q)
                        for q in site.questions
                        if len(get_live_answers_of_question(q)) == 0 and not q.is_hidden
                    ]
                )[:10]
            )
        return questions


@router.get(
    "/pending-questions/",
    response_model=List[schemas.QuestionPreview],
)
def get_pending_questions(
    ctx: RequestContext = Depends(deps.get_request_context),
) -> Any:
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


@router.get(
    "/interesting-questions/",
    response_model=List[schemas.QuestionPreview],
)
def get_interesting_questions(
    ctx: RequestContext = Depends(deps.get_request_context),
) -> Any:
    return indexed_layer.get_interesting_questions(ctx)


@router.get("/interesting-users/", response_model=List[schemas.UserPreview])
def get_interesting_users(
    ctx: RequestContext = Depends(deps.get_request_context),
) -> Any:
    return indexed_layer.get_interesting_users(ctx)


@router.get(
    "/featured-answers/",
    response_model=List[schemas.AnswerPreview],
)
def get_featured_answers(
    ctx: RequestContext = Depends(deps.get_request_context),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(
        default=MAX_FEATURED_ANSWERS_LIMIT,
        le=MAX_FEATURED_ANSWERS_LIMIT,
        gt=0,
    ),
) -> Any:
    db = ctx.get_db()
    stream = (
        db.query(models.Answer)
        .filter(models.Answer.featured_at != None)
        .order_by(models.Answer.featured_at.desc())
    )
    stream = stream[skip : skip + limit]
    return filter_not_none([ctx.preview_of_answer(a) for a in stream])
