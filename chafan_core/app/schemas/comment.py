import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel

from chafan_core.app.schemas.preview import UserPreview
from chafan_core.app.schemas.richtext import RichText


# Shared properties
class CommentBase(BaseModel):
    pass


# Properties to receive via API on creation
class CommentCreate(CommentBase):
    content: RichText
    question_uuid: Optional[str]
    submission_uuid: Optional[str]
    answer_uuid: Optional[str]
    article_uuid: Optional[str]
    parent_comment_uuid: Optional[str]
    mentioned: Optional[List[str]]
    shared_to_timeline: bool = False


# Properties to receive via API on update
class CommentUpdate(CommentBase):
    content: Optional[RichText]
    shared_to_timeline: Optional[Literal[True]] = None
    mentioned: Optional[List[str]]


class CommentInDBBase(CommentBase):
    uuid: str
    updated_at: datetime.datetime
    shared_to_timeline: bool
    is_deleted: bool
    upvotes_count: int

    class Config:
        orm_mode = True


# Additional properties to return via API
class Comment(CommentInDBBase):
    content: RichText
    author: UserPreview
    root_route: Optional[str] = None
    upvoted: bool
    child_comments: List["Comment"] = []


class CommentUpvotes(BaseModel):
    comment_uuid: str
    count: int
    upvoted: bool


class CommentForVisitor(CommentInDBBase):
    content: RichText
    author: UserPreview
    root_route: Optional[str] = None
    child_comments: List["CommentForVisitor"] = []
