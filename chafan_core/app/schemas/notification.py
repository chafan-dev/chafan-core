import datetime
from typing import Optional

from pydantic import BaseModel

from chafan_core.app.schemas.event import Event


# Shared properties
class NotificationBase(BaseModel):
    pass


class NotificationCreate(NotificationBase):
    receiver_id: int
    created_at: datetime.datetime
    event_json: str


class NotificationUpdate(BaseModel):
    is_read: bool


class NotificationInDBBase(NotificationBase):
    id: int
    created_at: datetime.datetime
    is_read: bool

    class Config:
        orm_mode = True


# Additional properties to return via API
class Notification(NotificationInDBBase):
    event: Optional[Event]
