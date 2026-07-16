from typing import Any, List

from fastapi import APIRouter, Depends

from chafan_core.app import schemas
from chafan_core.app.api import deps
from chafan_core.app.infra.request_context import RequestContext
from chafan_core.app.services import drafts as drafts_service

router = APIRouter()


@router.get("/answers/", response_model=List[schemas.AnswerPreview])
def get_draft_answers(
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
) -> Any:
    return drafts_service.list_draft_answers(ctx)


@router.get("/articles/", response_model=List[schemas.ArticlePreview])
def get_draft_articles(
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
) -> Any:
    return drafts_service.list_draft_articles(ctx)
