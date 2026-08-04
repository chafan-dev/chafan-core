import datetime
from typing import Any, List, Optional

from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from chafan_core.app import crud, models
from chafan_core.app.infra.request_context import RequestContext
from chafan_core.app.models.message import Message
from chafan_core.app.schemas.event import CreateMessageInternal, EventInternal
from chafan_core.app.schemas.message import MessageCreate


def get(db: Session, id: Any) -> Optional[Message]:
    return db.query(Message).filter(Message.id == id).first()


def get_multi(db: Session, *, skip: int = 0, limit: int = 100) -> List[Message]:
    return db.query(Message).offset(skip).limit(limit).all()


def create_with_author(
    broker: RequestContext,
    *,
    obj_in: MessageCreate,
    author: models.User,
) -> Message:
    db = broker.get_db()
    obj_in_data = jsonable_encoder(obj_in)
    utc_now = datetime.datetime.now(tz=datetime.timezone.utc)
    db_obj = Message(
        **obj_in_data,
        author_id=author.id,
        updated_at=utc_now,
        created_at=utc_now,
    )
    db.add(db_obj)
    db.flush()
    db.refresh(db_obj)
    db_obj.channel.updated_at = utc_now
    return db_obj
