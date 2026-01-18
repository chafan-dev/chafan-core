import datetime
from typing import List, Optional

from pydantic import BaseModel

from chafan_core.app.schemas.comment import Comment, CommentForVisitor
from chafan_core.app.schemas.preview import UserPreview
from chafan_core.app.schemas.richtext import RichText
from chafan_core.app.schemas.site import Site
from chafan_core.app.schemas.topic import Topic
from chafan_core.utils.validators import QuestionTitle, StrippedNonEmptyStr


# Shared properties
class QuestionBase(BaseModel):
    pass


# Properties to receive via API on creation
class QuestionCreate(QuestionBase):
    site_uuid: str
    title: QuestionTitle


# Properties to receive via API on update
class QuestionUpdate(QuestionBase):
    title: Optional[QuestionTitle] = None
    desc: Optional[RichText] = None
    topic_uuids: Optional[List[str]] = None


class QuestionInDBBase(QuestionBase):
    uuid: str
    title: StrippedNonEmptyStr
    created_at: datetime.datetime
    updated_at: datetime.datetime
    topics: List[Topic]
    is_placed_at_home: bool
    keywords: Optional[List[str]]

    class Config:
        from_attributes = True


class QuestionUpvotes(BaseModel):
    question_uuid: str
    count: int
    upvoted: bool


# Additional properties to return via API
class Question(QuestionInDBBase):
    desc: Optional[RichText] = None
    author: UserPreview
    editor: Optional[UserPreview]
    comments: List[Comment]
    site: Site
    answers_count: int
    view_times: int
    upvotes: Optional[QuestionUpvotes] = None


class QuestionForVisitor(QuestionInDBBase):
    desc: Optional[RichText] = None
    comments: List[CommentForVisitor]
    answers_count: int
    author: UserPreview
    site: Site
    upvotes: Optional[QuestionUpvotes] = None


# Additional properties stored in DB
class QuestionInDB(QuestionInDBBase):
    pass


class QuestionPreviewForSearch(BaseModel):
    uuid: str
    title: str


# class QuestionPreviewForVisitor(QuestionPreviewForSearch):
class QuestionPreviewForVisitor(BaseModel):
    uuid: str
    title: str
    author: UserPreview
    desc: Optional[RichText]
    is_placed_at_home: bool
    created_at: datetime.datetime
    answers_count: int
    upvotes: Optional[QuestionUpvotes]


class QuestionPreview(QuestionPreviewForVisitor):
    site: Site
    upvotes_count: int
    comments_count: int
