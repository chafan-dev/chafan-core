"""Article domain service (reads)."""

from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from chafan_core.app import crud, models, schemas
from chafan_core.app.user_permission import article_read_allowed
import chafan_core.app.responders as responders


def get_article_by_uuid(
    db: Session, uuid: str, current_user_id: Optional[int] = None
) -> Optional[models.Article]:
    article = crud.article.get_by_uuid(db, uuid=uuid)
    if article is None or not article_read_allowed(db, article, current_user_id):
        return None
    return article


def get_article_by_id(
    db: Session, article_id: int, current_user_id: Optional[int] = None
) -> Optional[models.Article]:
    article = crud.article.get(db, id=article_id)
    if article is None or not article_read_allowed(db, article, current_user_id):
        return None
    return article


def article_schema(cached_layer, article: models.Article):
    return responders.article.article_schema_from_orm(
        cached_layer, article, cached_layer.principal_id
    )
