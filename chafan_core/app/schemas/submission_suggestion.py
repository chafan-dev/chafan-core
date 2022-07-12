import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel

from chafan_core.app.schemas.preview import UserPreview
from chafan_core.app.schemas.richtext import RichText
from chafan_core.app.schemas.submission import Submission
from chafan_core.app.schemas.submission_archive import SubmissionEditableSnapshot
from chafan_core.app.schemas.topic import Topic


class SubmissionSuggestionInDB(BaseModel):
    uuid: str
    title: str
    created_at: datetime.datetime
    comment: Optional[str]
    status: Literal["pending", "accepted", "rejected", "retracted"]
    accepted_at: Optional[datetime.datetime]
    rejected_at: Optional[datetime.datetime]
    retracted_at: Optional[datetime.datetime]
    accepted_diff_base: Optional[SubmissionEditableSnapshot]
    topics: Optional[List[Topic]] = None

    class Config:
        orm_mode = True


class SubmissionSuggestion(SubmissionSuggestionInDB):
    desc: Optional[RichText]
    author: UserPreview
    submission: Submission


class SubmissionSuggestionCreate(BaseModel):
    submission_uuid: str
    title: Optional[str] = None
    desc: Optional[RichText] = None
    topic_uuids: Optional[List[str]] = None
    comment: Optional[str] = None


class SubmissionSuggestionUpdate(BaseModel):
    status: Literal["pending", "accepted", "rejected", "retracted"]
