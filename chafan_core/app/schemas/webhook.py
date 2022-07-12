import datetime
from typing import Literal, Optional

from pydantic import BaseModel
from pydantic.networks import HttpUrl

from chafan_core.app.schemas.site import Site


class WebhookSiteEvent(BaseModel):
    event_type: Literal["site_event"] = "site_event"
    new_question: Optional[bool] = False
    new_answer: Optional[bool] = False
    new_submission: Optional[bool] = False


class WebhookEventSpec(BaseModel):
    content: WebhookSiteEvent


# Properties to receive via API on creation
class WebhookCreate(BaseModel):
    site_uuid: str
    event_spec: WebhookEventSpec
    secret: str
    callback_url: HttpUrl


# Properties to receive via API on update
class WebhookUpdate(BaseModel):
    enabled: Optional[bool] = None
    event_spec: Optional[WebhookEventSpec] = None
    secret: Optional[str] = None
    callback_url: Optional[HttpUrl] = None


class WebhookInDB(BaseModel):
    id: int
    updated_at: datetime.datetime
    enabled: bool
    event_spec: WebhookEventSpec
    secret: str
    callback_url: HttpUrl

    class Config:
        orm_mode = True


class Webhook(WebhookInDB):
    site: Site
