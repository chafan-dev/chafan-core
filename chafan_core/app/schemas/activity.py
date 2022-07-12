import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel

from chafan_core.app.schemas.event import Event
from chafan_core.app.schemas.site import Site


class OriginSite(BaseModel):
    origin_type: Literal["site"] = "site"
    subdomain: str


Origin = OriginSite


class UpdateOrigins(BaseModel):
    action: Literal["add", "remove"]
    origin: Origin


class UserFeedSettings(BaseModel):
    blocked_origins: List[Origin] = []


class Activity(BaseModel):
    id: int
    site: Optional[Site]
    created_at: datetime.datetime
    verb: str
    event: Event
    origins: Optional[List[Origin]]


class FeedSequence(BaseModel):
    activities: List[Activity]
    random: bool
