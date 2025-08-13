import datetime
from typing import Literal

from pydantic import BaseModel

from chafan_core.app.schemas.preview import UserPreview

AUDIT_LOG_API_TYPE = Literal[
    "/login/access-token",
    "create access token",
    "post answer",
    "post question",
    "put question",
    "post article",
    "post submission",
    "scheduled/run_deliver_notification_task",
    "scheduled/daily",
    "scheduled/refresh_search_index",
    "scheduled/force_refresh_all_index",
]


# Properties to receive via API on creation
class AuditLogCreate(BaseModel):
    pass


class AuditLogUpdate(BaseModel):
    pass


class AuditLogInDBBase(BaseModel):
    uuid: str
    created_at: datetime.datetime
    api: AUDIT_LOG_API_TYPE
    ipaddr: str

    class Config:
        from_attributes = True


class AuditLog(AuditLogInDBBase):
    user: UserPreview
