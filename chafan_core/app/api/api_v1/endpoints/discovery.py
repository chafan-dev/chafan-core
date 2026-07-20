from typing import Any, List

from fastapi import APIRouter, Depends, Query

from chafan_core.app import schemas
from chafan_core.app.api import deps
from chafan_core.app.infra.request_context import RequestContext
from chafan_core.app.services import discovery as discovery_service
from chafan_core.utils.constants import MAX_FEATURED_ANSWERS_LIMIT

router = APIRouter()


@router.get(
    "/pinned-questions/", response_model=List[schemas.QuestionPreview]
)
def pinned_questions(
    ctx: RequestContext = Depends(deps.get_request_context),
) -> Any:
    return discovery_service.pinned_questions(ctx)


@router.get(
    "/pending-questions/",
    response_model=List[schemas.QuestionPreview],
)
def get_pending_questions(
    ctx: RequestContext = Depends(deps.get_request_context),
) -> Any:
    return discovery_service.pending_questions(ctx)


@router.get(
    "/interesting-questions/",
    response_model=List[schemas.QuestionPreview],
)
def get_interesting_questions(
    ctx: RequestContext = Depends(deps.get_request_context),
) -> Any:
    return discovery_service.interesting_questions(ctx)


@router.get("/interesting-users/", response_model=List[schemas.UserPreview])
def get_interesting_users(
    ctx: RequestContext = Depends(deps.get_request_context),
) -> Any:
    return discovery_service.interesting_users(ctx)


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
    return discovery_service.featured_answers(ctx, skip=skip, limit=limit)
