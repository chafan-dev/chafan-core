import datetime

from pydantic import BaseModel

from chafan_core.app.schemas.preview import UserPreview
from chafan_core.utils.validators import MessageBody


# Shared properties
class MessageBase(BaseModel):
    channel_id: int
    body: MessageBody


# Properties to receive via API on creation
class MessageCreate(MessageBase):
    pass


class MessageUpdate(BaseModel):
    pass


class MessageInDBBase(MessageBase):
    id: int
    created_at: datetime.datetime
    updated_at: datetime.datetime

    class Config:
        from_attributes = True


# Additional properties to return via API
class Message(MessageInDBBase):
    author: UserPreview
