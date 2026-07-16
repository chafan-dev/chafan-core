from typing import Any, List, Optional

from fastapi import APIRouter, Depends
from chafan_core.app.config import settings

from chafan_core.app import crud, schemas
from chafan_core.app.api import deps
from chafan_core.app.infra.request_context import RequestContext
from chafan_core.utils.base import HTTPException_, filter_not_none

router = APIRouter()


@router.get("/{uuid}", response_model=schemas.ArticleColumn)
def get_article_column(
    *,
    ctx: RequestContext = Depends(deps.get_request_context),
    uuid: str,
) -> Any:
    cached_layer = deps.cached_layer_from_context(ctx)
    article_column = crud.article_column.get_by_uuid(cached_layer.get_db(), uuid=uuid)
    if article_column is None:
        raise HTTPException_(
            status_code=400,
            detail="The article_column doesn't exist in the system.",
        )
    return cached_layer.materializer.article_column_schema_from_orm(article_column)


# TODO This API should support limit and page 2025-Mar-23
@router.get("/{uuid}/articles/", response_model=List[schemas.ArticlePreview])
def get_article_column_articles(
    *,
    ctx: RequestContext = Depends(deps.get_request_context),
    uuid: str,
    current_user_id: Optional[int] = Depends(deps.try_get_current_user_id),
) -> Any:
    cached_layer = deps.cached_layer_from_context(ctx)
    article_column = crud.article_column.get_by_uuid(cached_layer.get_db(), uuid=uuid)
    if article_column is None:
        raise HTTPException_(
            status_code=400,
            detail="The article_column doesn't exist in the system.",
        )
    articles = article_column.articles
    if not current_user_id:
        articles = articles[:settings.VISITORS_READ_ARTICLE_LIMIT]
    return filter_not_none(
        [cached_layer.materializer.preview_of_article(a) for a in articles]
    )


@router.post("/", response_model=schemas.ArticleColumn)
def create_article_column(
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    *,
    article_column_in: schemas.ArticleColumnCreate,
) -> Any:
    cached_layer = deps.cached_layer_from_context(ctx)
    new_article_column = crud.article_column.create_with_owner(
        cached_layer.get_db(),
        obj_in=article_column_in,
        owner_id=cached_layer.unwrapped_principal_id(),
    )
    return cached_layer.materializer.article_column_schema_from_orm(new_article_column)


@router.put("/{uuid}", response_model=schemas.ArticleColumn)
def update_article_column(
    *,
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    uuid: str,
    article_column_in: schemas.ArticleColumnUpdate,
) -> Any:
    cached_layer = deps.cached_layer_from_context(ctx)
    db = cached_layer.get_db()
    article_column = crud.article_column.get_by_uuid(db, uuid=uuid)
    if article_column is None:
        raise HTTPException_(
            status_code=400,
            detail="The article_column doesn't exist in the system.",
        )
    if article_column.owner_id != cached_layer.principal_id:
        raise HTTPException_(
            status_code=400,
            detail="Unauthorized.",
        )
    return cached_layer.materializer.article_column_schema_from_orm(
        crud.article_column.update(db, db_obj=article_column, obj_in=article_column_in),
    )
