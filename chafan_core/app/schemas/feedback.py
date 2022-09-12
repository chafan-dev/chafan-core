import datetime
from typing import Optional

from pydantic import BaseModel

from chafan_core.app.schemas.preview import UserPreview
from chafan_core.utils.constants import feedback_status_T


class FeedbackInDBBase(BaseModel):
    id: int
    created_at: datetime.datetime
    description: str
    status: feedback_status_T
    location_url: Optional[str]

    class Config:
        orm_mode = True


class Feedback(FeedbackInDBBase):
    has_screenshot: bool
    user: Optional[UserPreview] = None
    user_email: Optional[str] = None


class FeedbackCreate(BaseModel):
    pass


class FeedbackUpdate(BaseModel):
    status: feedback_status_T
