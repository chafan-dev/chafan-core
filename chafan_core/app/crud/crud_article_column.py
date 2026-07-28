import datetime
from typing import Any, Dict, List, Optional, Union

from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from chafan_core.app.models.article_column import ArticleColumn
from chafan_core.app.schemas.article_column import (
    ArticleColumnCreate,
    ArticleColumnUpdate,
)
from chafan_core.utils.base import get_uuid


def get(db: Session, id: Any) -> Optional[ArticleColumn]:
    return db.query(ArticleColumn).filter(ArticleColumn.id == id).first()


def get_by_uuid(db: Session, *, uuid: str) -> Optional[ArticleColumn]:
    return db.query(ArticleColumn).filter_by(uuid=uuid).first()


def get_all(db: Session) -> List[ArticleColumn]:
    return db.query(ArticleColumn).all()


def _get_unique_uuid(db: Session) -> str:
    while True:
        uuid = get_uuid()
        if get_by_uuid(db, uuid=uuid) is None:
            return uuid


def create_with_owner(
    db: Session, *, obj_in: ArticleColumnCreate, owner_id: int
) -> ArticleColumn:
    obj_in_data = jsonable_encoder(obj_in)
    utc_now = datetime.datetime.now(tz=datetime.timezone.utc)
    db_obj = ArticleColumn(
        **obj_in_data,
        owner_id=owner_id,
        created_at=utc_now,
        uuid=_get_unique_uuid(db),
    )
    db.add(db_obj)
    db.flush()
    return db_obj


def update(
    db: Session,
    *,
    db_obj: ArticleColumn,
    obj_in: Union[ArticleColumnUpdate, Dict[str, Any]],
) -> ArticleColumn:
    if isinstance(obj_in, dict):
        update_data = obj_in
    else:
        update_data = obj_in.dict(exclude_unset=True)
    for field in update_data:
        if hasattr(db_obj, field):
            setattr(db_obj, field, update_data[field])
    db.add(db_obj)
    db.flush()
    db.refresh(db_obj)
    return db_obj
