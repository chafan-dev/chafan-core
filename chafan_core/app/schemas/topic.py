from typing import Optional

from pydantic import BaseModel

from chafan_core.utils.validators import StrippedNonEmptyStr


# Shared properties
class TopicBase(BaseModel):
    name: StrippedNonEmptyStr


# Properties to receive via API on creation
class TopicCreate(TopicBase):
    pass


# Properties to receive via API on update
class TopicUpdate(BaseModel):
    description: Optional[str] = None
    parent_topic_uuid: Optional[str] = None


class TopicInDBBase(TopicBase):
    uuid: str

    class Config:
        orm_mode = True


# Additional properties to return via API
class Topic(TopicInDBBase):
    # NOTE: this is a deliberate "problem" since parent topic is only useful when returning to the Topic page
    parent_topic_uuid: Optional[str] = None


# Additional properties stored in DB
class TopicInDB(TopicInDBBase):
    pass
