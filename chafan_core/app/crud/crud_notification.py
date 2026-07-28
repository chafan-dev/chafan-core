import datetime
from typing import Any, Dict, Iterable, List, Optional, Union

from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from chafan_core.app.infra.request_context import RequestContext
from chafan_core.app.models.notification import Notification
from chafan_core.app.mq import push_notification
from chafan_core.app.schemas.event import EventInternal
from chafan_core.app.schemas.notification import NotificationCreate, NotificationUpdate


def get(db: Session, id: Any) -> Optional[Notification]:
    return db.query(Notification).filter(Notification.id == id).first()


def get_unread(db: Session, *, receiver_id: int) -> List[Notification]:
    return (
        db.query(Notification)
        .filter_by(receiver_id=receiver_id, is_read=False)
        .order_by(Notification.created_at.desc())
        .all()
    )


def get_read(db: Session, *, receiver_id: int) -> List[Notification]:
    return (
        db.query(Notification)
        .filter_by(receiver_id=receiver_id, is_read=True)
        .order_by(Notification.created_at.desc())
        .limit(50)
        .all()
    )


def get_undelivered_unread(db: Session) -> Iterable[Notification]:
    return (
        db.query(Notification)
        .filter_by(is_delivered=False, is_read=False)
        .order_by(Notification.created_at.asc())
    )


def create(db: Session, *, obj_in: NotificationCreate) -> Notification:
    obj_in_data = jsonable_encoder(obj_in)
    db_obj = Notification(**obj_in_data)
    db.add(db_obj)
    db.flush()
    db.refresh(db_obj)
    return db_obj


def create_with_content(
    broker: RequestContext,
    *,
    event: EventInternal,
    receiver_id: int,
) -> Notification:
    notification = create(
        broker.get_db(),
        obj_in=NotificationCreate(
            receiver_id=receiver_id,
            created_at=datetime.datetime.now(tz=datetime.timezone.utc),
            event_json=event.json(),
        ),
    )
    # FIXME crud layer should not call higher level components. However, I'd leave it for now. 2025-Jul-11
    push_notification(broker, notif=notification)
    return notification


def update(
    db: Session,
    *,
    db_obj: Notification,
    obj_in: Union[NotificationUpdate, Dict[str, Any]],
) -> Notification:
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
