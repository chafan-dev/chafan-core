import datetime
import json
from typing import Any, List, Union

from fastapi import APIRouter, Depends, Query
from fastapi.encoders import jsonable_encoder
from pydantic.tools import parse_raw_as
from sqlalchemy.orm.session import Session

from chafan_core.app import crud, models, schemas
from chafan_core.app.api import deps
from chafan_core.app.cached_layer import CachedLayer
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
    "/pinned-questions/", response_model=List[schemas.QuestionPreviewForVisitor]
)
def pinned_questions(
    cached_layer: CachedLayer = Depends(deps.get_cached_layer),
) -> Any:
    redis = cached_layer.get_redis()
    key = f"chafan:api:/discovery/pinned-questions"
    value = redis.get(key)
    if value:
        return parse_raw_as(List[schemas.QuestionPreviewForVisitor], value)

    def runnable(db: Session) -> List[schemas.QuestionPreviewForVisitor]:
        questions = crud.question.get_placed_at_home(db)
        data = filter_not_none(
            [
                cached_layer.materializer.preview_of_question_for_visitor(q)
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
    cached_layer: CachedLayer,
) -> Union[List[schemas.QuestionPreview], List[schemas.QuestionPreviewForVisitor]]:
    if cached_layer.principal_id:
        current_user = crud.user.get(
            cached_layer.get_db(), id=cached_layer.principal_id
        )
        assert current_user is not None
        questions: List[schemas.QuestionPreview] = []
        for profile in current_user.profiles:
            questions.extend(
                filter_not_none(
                    [
                        cached_layer.materializer.preview_of_question(q)
                        for q in profile.site.questions
                        if len(get_live_answers_of_question(q)) == 0 and not q.is_hidden
                    ]
                )
            )
        return questions
    else:
        questions_for_visitors: List[schemas.QuestionPreviewForVisitor] = []
        for site in crud.site.get_all_public_readable(cached_layer.get_db()):
            questions_for_visitors.extend(
                filter_not_none(
                    [
                        cached_layer.materializer.preview_of_question_for_visitor(q)
                        for q in site.questions
                        if len(get_live_answers_of_question(q)) == 0 and not q.is_hidden
                    ]
                )[:10]
            )
        return questions_for_visitors


@router.get(
    "/pending-questions/",
    response_model=Union[
        List[schemas.QuestionPreview], List[schemas.QuestionPreviewForVisitor]
    ],
)
def get_pending_questions(
    cached_layer: CachedLayer = Depends(deps.get_cached_layer),
) -> Any:
    redis = get_redis_cli()
    key = f"chafan:pending-questions-for-user:{cached_layer.principal_id}"
    value = redis.get(key)
    if value is not None:
        if cached_layer.principal_id:
            return parse_raw_as(List[schemas.QuestionPreview], value)
        else:
            return parse_raw_as(List[schemas.QuestionPreviewForVisitor], value)
    data = _get_pending_questions(cached_layer)
    if not is_dev():
        redis.set(
            key, json.dumps(jsonable_encoder(data)), ex=datetime.timedelta(hours=24)
        )
    return data


@router.get(
    "/interesting-questions/",
    response_model=Union[
        List[schemas.QuestionPreview], List[schemas.QuestionPreviewForVisitor]
    ],
)
def get_interesting_questions(
    cached_layer: CachedLayer = Depends(deps.get_cached_layer),
) -> Any:
    return indexed_layer.get_interesting_questions(cached_layer)


@router.get("/interesting-users/", response_model=List[schemas.UserPreview])
def get_interesting_users(
    cached_layer: CachedLayer = Depends(deps.get_cached_layer),
) -> Any:
    return indexed_layer.get_interesting_users(cached_layer)


@router.get(
    "/featured-answers/",
    response_model=Union[
        List[schemas.AnswerPreview], List[schemas.AnswerPreviewForVisitor]
    ],
)
def get_featured_answers(
    cached_layer: CachedLayer = Depends(deps.get_cached_layer),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(
        default=MAX_FEATURED_ANSWERS_LIMIT,
        le=MAX_FEATURED_ANSWERS_LIMIT,
        gt=0,
    ),
) -> Any:
    db = cached_layer.get_db()
    stream = (
        db.query(models.Answer)
        .filter(models.Answer.featured_at != None)
        .order_by(models.Answer.featured_at.desc())
    )
    stream = stream[skip : skip + limit]
    return filter_not_none([cached_layer.preview_of_answer(a) for a in stream])
