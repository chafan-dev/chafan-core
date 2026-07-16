from typing import Any, List, Optional

from fastapi import APIRouter, Depends

from chafan_core.app import schemas
from chafan_core.app.api import deps
from chafan_core.app.infra.request_context import RequestContext
from chafan_core.app.services import article_columns as article_columns_service

router = APIRouter()


@router.get("/{uuid}", response_model=schemas.ArticleColumn)
def get_article_column(
    *,
    ctx: RequestContext = Depends(deps.get_request_context),
    uuid: str,
) -> Any:
    return article_columns_service.get_article_column(ctx, uuid)


# TODO This API should support limit and page 2025-Mar-23
@router.get("/{uuid}/articles/", response_model=List[schemas.ArticlePreview])
def get_article_column_articles(
    *,
    ctx: RequestContext = Depends(deps.get_request_context),
    uuid: str,
    current_user_id: Optional[int] = Depends(deps.try_get_current_user_id),
) -> Any:
    return article_columns_service.list_column_articles(
        ctx, uuid=uuid, current_user_id=current_user_id
    )


@router.post("/", response_model=schemas.ArticleColumn)
def create_article_column(
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    *,
    article_column_in: schemas.ArticleColumnCreate,
) -> Any:
    return article_columns_service.create_article_column(
        ctx, article_column_in=article_column_in
    )


@router.put("/{uuid}", response_model=schemas.ArticleColumn)
def update_article_column(
    *,
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    uuid: str,
    article_column_in: schemas.ArticleColumnUpdate,
) -> Any:
    return article_columns_service.update_article_column(
        ctx, uuid=uuid, article_column_in=article_column_in
    )
