from typing import Any, List

import logging
logger = logging.getLogger(__name__)

from fastapi import APIRouter, Depends, Request, Response

from chafan_core.app import crud, models, schemas
from chafan_core.app.api import deps
from chafan_core.app.cached_layer import CachedLayer
from chafan_core.app.materialize import preview_of_question_as_search_hit
from chafan_core.app.limiter import limiter
from chafan_core.utils.base import filter_not_none

router = APIRouter()

_SEARCH_RATE_LIMIT = "60/minute"


@router.get("/users/", response_model=List[schemas.UserPreview])
@limiter.limit(_SEARCH_RATE_LIMIT)
def search_users(
    response: Response,
    request: Request,
    *,
    cached_layer: CachedLayer = Depends(deps.get_cached_layer_logged_in),
    q: str,
) -> Any:
    if q == "":
        return []
    users = crud.user.search_by_handle_or_full_name(cached_layer.get_db(), fragment=q)
    return [cached_layer.preview_of_user(u) for u in users]


@router.get("/sites/", response_model=List[schemas.Site])
@limiter.limit(_SEARCH_RATE_LIMIT)
def search_sites(
    response: Response,
    request: Request,
    *,
    cached_layer: CachedLayer = Depends(deps.get_cached_layer_logged_in),
    q: str,
) -> Any:
    if q == "":
        return []
    sites = crud.site.search(cached_layer.get_db(), fragment=q)
    return [cached_layer.materializer.site_schema_from_orm(s) for s in sites]


@router.get("/topics/", response_model=List[schemas.Topic])
@limiter.limit(_SEARCH_RATE_LIMIT)
def search_topics(
    response: Response,
    request: Request,
    *,
    cached_layer: CachedLayer = Depends(deps.get_cached_layer_logged_in),
    q: str,
) -> Any:
    if q == "":
        return []
    return crud.topic.get_ilike(
        cached_layer.get_db(), fragment=q, column=models.Topic.name
    )


@router.get("/questions/", response_model=List[schemas.QuestionPreviewForSearch])
@limiter.limit(_SEARCH_RATE_LIMIT)
async def search_questions(
    response: Response,
    request: Request,
    *,
    cached_layer: CachedLayer = Depends(deps.get_cached_layer_logged_in),
    # This API is very time consuming! Must check user logged in
    q: str,
) -> Any:
    if q == "":
        return []
    questions = crud.question.search(cached_layer.get_db(), q=q)
# TODO no search hit limit
    return filter_not_none(
        [await preview_of_question_as_search_hit(q) for q in questions]
    )


@router.get("/articles/", response_model=List[schemas.ArticlePreview])
@limiter.limit(_SEARCH_RATE_LIMIT)
def search_articles(
    response: Response,
    request: Request,
    *,
    cached_layer: CachedLayer = Depends(deps.get_cached_layer_logged_in),
    q: str,
) -> Any:
    if q == "":
        return []
    articles = crud.article.search(cached_layer.get_db(), q=q)
    return filter_not_none(
        [cached_layer.materializer.preview_of_article(a) for a in articles]
    )


@router.get("/submissions/", response_model=List[schemas.Submission])
@limiter.limit(_SEARCH_RATE_LIMIT)
def search_submissions(
    response: Response,
    request: Request,
    *,
    cached_layer: CachedLayer = Depends(deps.get_cached_layer_logged_in),
    q: str,
) -> Any:
    if q == "":
        return []
    submissions = crud.submission.search(cached_layer.get_db(), q=q)
    return filter_not_none(
        [cached_layer.materializer.submission_schema_from_orm(q) for q in submissions]
    )


@router.get("/answers/", response_model=List[schemas.AnswerPreview])
@limiter.limit(_SEARCH_RATE_LIMIT)
def search_answers(
    response: Response,
    request: Request,
    *,
    cached_layer: CachedLayer = Depends(deps.get_cached_layer_logged_in),
    q: str,
) -> Any:
    if q == "":
        return []
    answers = crud.answer.search(cached_layer.get_db(), q=q)
    return filter_not_none(
        [cached_layer.materializer.preview_of_answer(a) for a in answers]
    )
