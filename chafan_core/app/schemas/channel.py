from typing import Literal, Optional, Union

from pydantic import BaseModel

from chafan_core.app.schemas.feedback import Feedback
from chafan_core.app.schemas.preview import UserPreview


# Shared properties
class ChannelBase(BaseModel):
    pass


class FeedbackSubject(BaseModel):
    type: Literal["feedback"] = "feedback"
    id: int


class SiteCreationSubject(BaseModel):
    from chafan_core.app.schemas.site import SiteCreate

    type: Literal["site_creation"] = "site_creation"
    site_in: SiteCreate


FeedbackSubjectT = Union[FeedbackSubject, SiteCreationSubject, None]

# Properties to receive via API on creation
class ChannelCreate(ChannelBase):
    private_with_user_uuid: str
    subject: FeedbackSubjectT


class ChannelUpdate(BaseModel):
    pass


class ChannelInDBBase(ChannelBase):
    from chafan_core.app.schemas.site import SiteCreate

    id: int
    name: str
    is_private: bool
    site_creation_subject: Optional[SiteCreate] = None

    class Config:
        orm_mode = True


# Additional properties to return via API
class Channel(ChannelInDBBase):
    private_with_user: Optional[UserPreview] = None
    admin: UserPreview
    feedback_subject: Optional[Feedback] = None
