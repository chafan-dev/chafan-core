import datetime
from typing import List, Optional

from pydantic import BaseModel
from pydantic.networks import AnyHttpUrl

from chafan_core.app.schemas.comment import Comment, CommentForVisitor
from chafan_core.app.schemas.preview import UserPreview
from chafan_core.app.schemas.richtext import RichText
from chafan_core.app.schemas.site import Site
from chafan_core.app.schemas.topic import Topic
from chafan_core.utils.validators import StrippedNonEmptyStr, SubmissionTitle


# Shared properties
class SubmissionBase(BaseModel):
    pass


# Properties to receive via API on creation
class SubmissionCreate(SubmissionBase):
    site_uuid: str
    title: SubmissionTitle
    url: Optional[AnyHttpUrl] = None


# Properties to receive via API on update
class SubmissionUpdate(SubmissionBase):
    title: Optional[SubmissionTitle] = None
    desc: Optional[RichText] = None
    topic_uuids: Optional[List[str]] = None


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
        from_attributes = True


# Additional properties to return via API
class Submission(SubmissionInDB):
    desc: Optional[RichText] = None
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
