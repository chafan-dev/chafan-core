import datetime

from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from chafan_core.app.crud.base import CRUDBase
from chafan_core.app.models.article_column import ArticleColumn
from chafan_core.app.schemas.article_column import (
    ArticleColumnCreate,
    ArticleColumnUpdate,
)


class CRUDArticleColumn(
    CRUDBase[ArticleColumn, ArticleColumnCreate, ArticleColumnUpdate]
):
    def create_with_owner(
        self, db: Session, *, obj_in: ArticleColumnCreate, owner_id: int
    ) -> ArticleColumn:
        obj_in_data = jsonable_encoder(obj_in)
        utc_now = datetime.datetime.now(tz=datetime.timezone.utc)
        db_obj = self.model(
            **obj_in_data,
            owner_id=owner_id,
            created_at=utc_now,
            uuid=self.get_unique_uuid(db)
        )
        db.add(db_obj)
        db.commit()
        return db_obj


article_column = CRUDArticleColumn(ArticleColumn)
