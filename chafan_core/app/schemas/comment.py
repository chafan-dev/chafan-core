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
    question_uuid: Optional[str] = None
    submission_uuid: Optional[str] = None
    answer_uuid: Optional[str] = None
    article_uuid: Optional[str] = None
    parent_comment_uuid: Optional[str] = None
    mentioned: Optional[List[str]] = None
    shared_to_timeline: bool = False


# Properties to receive via API on update
class CommentUpdate(CommentBase):
    content: Optional[RichText] = None
    shared_to_timeline: Optional[Literal[True]] = None
    mentioned: Optional[List[str]] = None


class CommentInDBBase(CommentBase):
    uuid: str
    updated_at: datetime.datetime
    shared_to_timeline: bool
    is_deleted: bool
    upvotes_count: int

    class Config:
        from_attributes = True


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
