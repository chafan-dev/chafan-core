import datetime
from typing import Iterable, List

from sqlalchemy.orm import Session

from chafan_core.app.crud.base import CRUDBase
from chafan_core.app.data_broker import DataBroker
from chafan_core.app.models.notification import Notification
from chafan_core.app.mq import push_notification
from chafan_core.app.schemas.event import EventInternal
from chafan_core.app.schemas.notification import NotificationCreate, NotificationUpdate


class CRUDNotification(CRUDBase[Notification, NotificationCreate, NotificationUpdate]):
    def get_unread(self, db: Session, *, receiver_id: int) -> List[Notification]:
        return (
            db.query(Notification)
            .filter_by(receiver_id=receiver_id, is_read=False)
            .order_by(Notification.created_at.desc())
            .all()
        )

    def get_read(self, db: Session, *, receiver_id: int) -> List[Notification]:
        return (
            db.query(Notification)
            .filter_by(receiver_id=receiver_id, is_read=True)
            .order_by(Notification.created_at.desc())
            .limit(50)
            .all()
        )

    def get_undelivered_unread(self, db: Session) -> Iterable[Notification]:
        return (
            db.query(Notification)
            .filter_by(is_delivered=False, is_read=False)
            .order_by(Notification.created_at.asc())
        )

    def create_with_content(
        self,
        broker: DataBroker,
        *,
        event: EventInternal,
        receiver_id: int,
    ) -> Notification:
        notification = self.create(
            broker.get_db(),
            obj_in=NotificationCreate(
                receiver_id=receiver_id,
                created_at=datetime.datetime.now(tz=datetime.timezone.utc),
                event_json=event.json(),
            ),
        )
        push_notification(broker, notif=notification)
        return notification


notification = CRUDNotification(Notification)
