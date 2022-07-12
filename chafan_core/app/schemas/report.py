import datetime
from typing import Optional

from pydantic import BaseModel

from chafan_core.app.schemas.preview import UserPreview
from chafan_core.utils.base import ReportReason


# Properties to receive via API on creation
class ReportCreate(BaseModel):
    question_uuid: Optional[str]
    submission_uuid: Optional[str]
    answer_uuid: Optional[str]
    article_uuid: Optional[str]
    comment_uuid: Optional[str]
    reason: ReportReason
    reason_comment: Optional[str]


# Properties to receive via API on update
class ReportUpdate(BaseModel):
    pass


class ReportInDBBase(BaseModel):
    id: int
    created_at: datetime.datetime
    reason: ReportReason
    reason_comment: Optional[str]

    class Config:
        orm_mode = True


# Additional properties to return via API
class Report(ReportInDBBase):
    author: UserPreview
