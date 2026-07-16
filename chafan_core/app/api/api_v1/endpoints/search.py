from typing import Any, List

from fastapi import APIRouter, Depends, Request, Response

from chafan_core.app import schemas
from chafan_core.app.api import deps
from chafan_core.app.infra.request_context import RequestContext
from chafan_core.app.limiter import limiter
from chafan_core.app.services import search as search_service

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
    return search_service.search_users(ctx, q)


@router.get("/sites/", response_model=List[schemas.Site])
@limiter.limit(_SEARCH_RATE_LIMIT)
def search_sites(
    response: Response,
    request: Request,
    *,
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    q: str,
) -> Any:
    return search_service.search_sites(ctx, q)


@router.get("/topics/", response_model=List[schemas.Topic])
@limiter.limit(_SEARCH_RATE_LIMIT)
def search_topics(
    response: Response,
    request: Request,
    *,
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    q: str,
) -> Any:
    return search_service.search_topics(ctx, q)


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
    return search_service.search_questions(ctx, q)


@router.get("/articles/", response_model=List[schemas.ArticlePreview])
@limiter.limit(_SEARCH_RATE_LIMIT)
def search_articles(
    response: Response,
    request: Request,
    *,
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    q: str,
) -> Any:
    return search_service.search_articles(ctx, q)


@router.get("/submissions/", response_model=List[schemas.Submission])
@limiter.limit(_SEARCH_RATE_LIMIT)
def search_submissions(
    response: Response,
    request: Request,
    *,
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    q: str,
) -> Any:
    return search_service.search_submissions(ctx, q)


@router.get("/answers/", response_model=List[schemas.AnswerPreview])
@limiter.limit(_SEARCH_RATE_LIMIT)
def search_answers(
    response: Response,
    request: Request,
    *,
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    q: str,
) -> Any:
    return search_service.search_answers(ctx, q)
