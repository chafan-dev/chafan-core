from typing import Optional

from pydantic import BaseModel

from chafan_core.app.schemas.preview import UserPreview
from chafan_core.app.schemas.site import Site


# Shared properties
class ProfileBase(BaseModel):
    pass


# Properties to receive via API on creation
class ProfileCreate(ProfileBase):
    site_uuid: str
    owner_uuid: str


class ProfileUpdate(ProfileBase):
    pass


class ProfileInDBBase(ProfileBase):
    karma: int

    class Config:
        from_attributes = True


# Additional properties to return via API
class Profile(ProfileInDBBase):
    owner: UserPreview
    site: Site
    introduction: Optional[str] = None


# Additional properties stored in DB
class ProfileInDB(ProfileInDBBase):
    pass
