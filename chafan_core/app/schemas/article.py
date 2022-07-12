import datetime
from typing import List, Optional

from pydantic import BaseModel, validator

from chafan_core.app.schemas.article_column import ArticleColumn
from chafan_core.app.schemas.comment import Comment, CommentForVisitor
from chafan_core.app.schemas.preview import UserPreview
from chafan_core.app.schemas.richtext import RichText
from chafan_core.app.schemas.topic import Topic
from chafan_core.utils.base import ContentVisibility
from chafan_core.utils.validators import StrippedNonEmptyStr, validate_article_title


# Shared properties
class ArticleBase(BaseModel):
    pass


# Properties to receive via API on creation
class ArticleCreate(ArticleBase):
    title: StrippedNonEmptyStr
    content: RichText
    article_column_uuid: str
    is_published: bool
    writing_session_uuid: str
    visibility: ContentVisibility

    @validator("title")
    def _valid_title(cls, v: str) -> str:
        validate_article_title(v)
        return v


# Properties to receive via API on update
class ArticleUpdate(ArticleBase):
    updated_title: StrippedNonEmptyStr
    updated_content: RichText
    is_draft: bool
    visibility: ContentVisibility

    @validator("updated_title")
    def _valid_title(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            validate_article_title(v)
        return v


# Properties to receive via API on update
class ArticleTopicsUpdate(ArticleBase):
    topic_uuids: List[str]


class ArticleInDBBase(ArticleBase):
    uuid: str
    title: StrippedNonEmptyStr
    topics: List[Topic] = []
    upvotes_count: int
    is_published: bool

    initial_published_at: Optional[datetime.datetime]
    updated_at: Optional[datetime.datetime]
    # FIXME: Make it only author-viewable
    draft_saved_at: Optional[datetime.datetime]

    visibility: ContentVisibility

    class Config:
        orm_mode = True


# Additional properties to return via API
class Article(ArticleInDBBase):
    content: RichText

    author: UserPreview
    comments: List[Comment]
    article_column: ArticleColumn
    upvoted: bool
    view_times: int
    bookmark_count: int
    bookmarked: bool
    archives_count: int


# Additional properties to return via API
class ArticleForVisitor(ArticleInDBBase):
    content: RichText

    author: UserPreview
    comments: List[CommentForVisitor]
    article_column: ArticleColumn


# Additional properties stored in DB
class ArticleInDB(ArticleInDBBase):
    pass


class ArticleUpvotes(BaseModel):
    article_uuid: str
    count: int
    upvoted: bool


class ArticleDoc(BaseModel):
    """
    Used for creating ES index
    """

    id: int
    title: StrippedNonEmptyStr
    body_prerendered_text: Optional[str]

    class Config:
        orm_mode = True


class ArticleDraft(BaseModel):
    title_draft: Optional[StrippedNonEmptyStr]
    draft_saved_at: Optional[datetime.datetime]
    content_draft: Optional[RichText]


class ArticlePreview(BaseModel):
    uuid: str
    author: UserPreview
    article_column: ArticleColumn
    title: str
    body_text: Optional[str]
    upvotes_count: int
    is_published: bool
