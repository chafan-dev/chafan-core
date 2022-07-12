import datetime
from typing import List, Optional

from pydantic import BaseModel, validator
from pydantic.networks import AnyHttpUrl

from chafan_core.app.schemas.comment import Comment, CommentForVisitor
from chafan_core.app.schemas.preview import UserPreview
from chafan_core.app.schemas.richtext import RichText
from chafan_core.app.schemas.site import Site
from chafan_core.app.schemas.topic import Topic
from chafan_core.utils.validators import StrippedNonEmptyStr, validate_submission_title


# Shared properties
class SubmissionBase(BaseModel):
    pass


# Properties to receive via API on creation
class SubmissionCreate(SubmissionBase):
    site_uuid: str
    title: StrippedNonEmptyStr
    url: Optional[AnyHttpUrl] = None

    @validator("title")
    def _valid_title(cls, v: str) -> str:
        validate_submission_title(v)
        return v


# Properties to receive via API on update
class SubmissionUpdate(SubmissionBase):
    title: Optional[StrippedNonEmptyStr] = None
    desc: Optional[RichText] = None
    topic_uuids: Optional[List[str]] = None

    @validator("title")
    def _valid_title(
        cls, v: Optional[StrippedNonEmptyStr]
    ) -> Optional[StrippedNonEmptyStr]:
        if v is not None:
            validate_submission_title(v)
        return v


class SubmissionInDB(SubmissionBase):
    uuid: str
    title: StrippedNonEmptyStr
    url: Optional[str]
    created_at: datetime.datetime
    updated_at: datetime.datetime
    topics: List[Topic]
    keywords: Optional[List[str]]
    upvotes_count: int

    class Config:
        orm_mode = True


# Additional properties to return via API
class Submission(SubmissionInDB):
    desc: Optional[RichText]
    author: UserPreview
    contributors: List[UserPreview] = []
    comments: List[Comment]
    site: Site
    view_times: int


class SubmissionForVisitor(SubmissionInDB):
    desc: Optional[RichText]
    author: UserPreview
    contributors: List[UserPreview] = []
    site: Site
    comments: List[CommentForVisitor]


class SubmissionUpvotes(BaseModel):
    submission_uuid: str
    count: int
    upvoted: bool


class SubmissionDoc(BaseModel):
    """
    Used for creating ES index
    """

    id: int
    title: str
    description_text: Optional[str]

    class Config:
        orm_mode = True
