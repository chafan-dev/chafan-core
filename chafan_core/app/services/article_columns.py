"""Article column domain service."""

from __future__ import annotations

from typing import List, Optional

from chafan_core.app import crud, schemas
from chafan_core.app.config import settings
from chafan_core.app.responders import misc as misc_responder
from chafan_core.utils.base import HTTPException_, filter_not_none


def article_column_schema(ctx, article_column) -> schemas.ArticleColumn:
    return misc_responder.article_column_schema_from_orm(
        ctx.principal_view, article_column
    )


def get_article_column(ctx, uuid: str) -> schemas.ArticleColumn:
    article_column = crud.article_column.get_by_uuid(ctx.get_db(), uuid=uuid)
    if article_column is None:
        raise HTTPException_(
            status_code=400,
            detail="The article_column doesn't exist in the system.",
        )
    return article_column_schema(ctx, article_column)


def list_column_articles(
    ctx, *, uuid: str, current_user_id: Optional[int]
) -> List[schemas.ArticlePreview]:
    article_column = crud.article_column.get_by_uuid(ctx.get_db(), uuid=uuid)
    if article_column is None:
        raise HTTPException_(
            status_code=400,
            detail="The article_column doesn't exist in the system.",
        )
    articles = article_column.articles
    if not current_user_id:
        articles = articles[: settings.VISITORS_READ_ARTICLE_LIMIT]
    mat = ctx.principal_view
    return filter_not_none([mat.preview_of_article(a) for a in articles])


def create_article_column(
    ctx, *, article_column_in: schemas.ArticleColumnCreate
) -> schemas.ArticleColumn:
    new_article_column = crud.article_column.create_with_owner(
        ctx.get_db(),
        obj_in=article_column_in,
        owner_id=ctx.unwrapped_principal_id(),
    )
    return article_column_schema(ctx, new_article_column)


def update_article_column(
    ctx, *, uuid: str, article_column_in: schemas.ArticleColumnUpdate
) -> schemas.ArticleColumn:
    db = ctx.get_db()
    article_column = crud.article_column.get_by_uuid(db, uuid=uuid)
    if article_column is None:
        raise HTTPException_(
            status_code=400,
            detail="The article_column doesn't exist in the system.",
        )
    if article_column.owner_id != ctx.principal_id:
        raise HTTPException_(
            status_code=400,
            detail="Unauthorized.",
        )
    updated = crud.article_column.update(
        db, db_obj=article_column, obj_in=article_column_in
    )
    return article_column_schema(ctx, updated)
