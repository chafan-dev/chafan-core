import datetime
from typing import Optional

from pydantic import BaseModel

from chafan_core.app.schemas.preview import UserPreview
from chafan_core.app.schemas.site import Site


class InvitationLinkCreate(BaseModel):
    invited_to_site_uuid: Optional[str] = None


class InvitationLinkInDB(BaseModel):
    uuid: str
    created_at: datetime.datetime
    expired_at: datetime.datetime
    remaining_quota: int

    class Config:
        from_attributes = True


class InvitationLink(InvitationLinkInDB):
    invited_to_site: Optional[Site]
    inviter: UserPreview
    valid: bool


class InvitationLinkUpdate(BaseModel):
    pass
