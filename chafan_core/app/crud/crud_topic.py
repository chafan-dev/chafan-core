from typing import Any, Dict, List, Optional, Union

from fastapi.encoders import jsonable_encoder
from sqlalchemy import desc
from sqlalchemy.orm import Session
from sqlalchemy.sql.expression import func

from chafan_core.app.models.topic import Topic
from chafan_core.app.schemas.topic import TopicCreate, TopicUpdate
from chafan_core.utils.base import get_uuid
from chafan_core.utils.validators import StrippedNonEmptyStr


def get(db: Session, id: Any) -> Optional[Topic]:
    return db.query(Topic).filter(Topic.id == id).first()


def get_by_uuid(db: Session, *, uuid: str) -> Optional[Topic]:
    return db.query(Topic).filter_by(uuid=uuid).first()


def get_all(db: Session) -> List[Topic]:
    return db.query(Topic).all()


def get_by_name(db: Session, *, name: str) -> Optional[Topic]:
    return db.query(Topic).filter(Topic.name == name).first()


def get_ilike(
    db: Session, *, fragment: str, column: Any, limit: int = 5
) -> List[Topic]:
    same_ones = (
        db.query(Topic)
        .filter(column.ilike(f"{fragment}"))
        .order_by(desc(func.length(column)))
        .limit(limit)
        .all()
    )
    similar_ones = (
        db.query(Topic)
        .filter(column.ilike(f"%{fragment}%"))
        .order_by(desc(func.length(column)))
        .limit(limit)
        .all()
    )
    return same_ones + [s for s in similar_ones if s not in same_ones]


def _get_unique_uuid(db: Session) -> str:
    while True:
        uuid = get_uuid()
        if get_by_uuid(db, uuid=uuid) is None:
            return uuid


def create(db: Session, *, obj_in: TopicCreate) -> Topic:
    obj_in_data = jsonable_encoder(obj_in)
    db_obj = Topic(**obj_in_data, uuid=_get_unique_uuid(db))
    db.add(db_obj)
    db.flush()
    db.refresh(db_obj)
    return db_obj


def get_category_topics(db: Session) -> List[Topic]:
    return db.query(Topic).filter_by(is_category=True).all()


def get_or_create(db: Session, *, name: StrippedNonEmptyStr) -> Topic:
    topic = get_by_name(db, name=name)
    if topic is not None:
        return topic
    return create(db, obj_in=TopicCreate(name=name))


def update(
    db: Session, *, db_obj: Topic, obj_in: Union[TopicUpdate, Dict[str, Any]]
) -> Topic:
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
