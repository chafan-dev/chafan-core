from typing import Any, List


from fastapi import APIRouter, Depends, Request, Response

from chafan_core.app import crud, models, schemas
from chafan_core.app.api import deps
from chafan_core.app.services import sites as sites_service
from chafan_core.app.services import submissions as submissions_service
from chafan_core.app.infra.request_context import RequestContext
from chafan_core.app.materialize import preview_of_question_as_search_hit
from chafan_core.app.limiter import limiter
from chafan_core.utils.base import filter_not_none

import logging
logger = logging.getLogger(__name__)

router = APIRouter()

_SEARCH_RATE_LIMIT = "60/minute"


@router.get("/users/", response_model=List[schemas.UserPreview])
@limiter.limit(_SEARCH_RATE_LIMIT)
def search_users(
    response: Response,
    request: Request,
    *,
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    q: str,
) -> Any:
    if q == "":
        return []
    users = crud.user.search_by_handle_or_full_name(ctx.get_db(), fragment=q)
    return [ctx.preview_of_user(u) for u in users]


@router.get("/sites/", response_model=List[schemas.Site])
@limiter.limit(_SEARCH_RATE_LIMIT)
def search_sites(
    response: Response,
    request: Request,
    *,
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    q: str,
) -> Any:
    if q == "":
        return []
    sites = crud.site.search(ctx.get_db(), fragment=q)
    return [sites_service.site_schema(ctx, s) for s in sites]


@router.get("/topics/", response_model=List[schemas.Topic])
@limiter.limit(_SEARCH_RATE_LIMIT)
def search_topics(
    response: Response,
    request: Request,
    *,
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    q: str,
) -> Any:
    if q == "":
        return []
    return crud.topic.get_ilike(
        ctx.get_db(), fragment=q, column=models.Topic.name
    )


@router.get("/questions/", response_model=List[schemas.QuestionPreviewForSearch])
@limiter.limit(_SEARCH_RATE_LIMIT)
def search_questions(
    response: Response,
    request: Request,
    *,
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    # This API is very time consuming! Must check user logged in
    q: str,
) -> Any:
    if q == "":
        return []
    questions = crud.question.search(ctx.get_db(), q=q)
# TODO no search hit limit
    return filter_not_none(
        [preview_of_question_as_search_hit(q) for q in questions]
    )


@router.get("/articles/", response_model=List[schemas.ArticlePreview])
@limiter.limit(_SEARCH_RATE_LIMIT)
def search_articles(
    response: Response,
    request: Request,
    *,
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    q: str,
) -> Any:
    if q == "":
        return []
    articles = crud.article.search(ctx.get_db(), q=q)
    return filter_not_none(
        [ctx.materializer.preview_of_article(a) for a in articles]
    )


@router.get("/submissions/", response_model=List[schemas.Submission])
@limiter.limit(_SEARCH_RATE_LIMIT)
def search_submissions(
    response: Response,
    request: Request,
    *,
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    q: str,
) -> Any:
    if q == "":
        return []
    submissions = crud.submission.search(ctx.get_db(), q=q)
    return filter_not_none(
        [submissions_service.submission_schema(ctx, q) for q in submissions]
    )


@router.get("/answers/", response_model=List[schemas.AnswerPreview])
@limiter.limit(_SEARCH_RATE_LIMIT)
def search_answers(
    response: Response,
    request: Request,
    *,
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    q: str,
) -> Any:
    if q == "":
        return []
    answers = crud.answer.search(ctx.get_db(), q=q)
    return filter_not_none(
        [ctx.materializer.preview_of_answer(a) for a in answers]
    )
