import datetime

from pydantic import BaseModel

from chafan_core.app.schemas.preview import UserPreview
from chafan_core.app.schemas.site import Site


# Shared properties
class ApplicationBase(BaseModel):
    pass


class ApplicationCreate(ApplicationBase):
    applied_site_id: int


class ApplicationUpdate(BaseModel):
    pending: bool


class ApplicationInDBBase(ApplicationBase):
    id: int
    pending: bool
    created_at: datetime.datetime

    class Config:
        from_attributes = True


# Additional properties to return via API
class Application(ApplicationInDBBase):
    applicant: UserPreview
    applied_site: Site
