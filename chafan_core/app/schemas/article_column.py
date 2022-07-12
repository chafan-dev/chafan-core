import datetime
from typing import Optional

from pydantic import BaseModel

from chafan_core.app.schemas.preview import UserPreview
from chafan_core.utils.validators import UUID, StrippedNonEmptyStr


# Shared properties
class ArticleColumnBase(BaseModel):
    pass


# Properties to receive via API on creation
class ArticleColumnCreate(ArticleColumnBase):
    name: StrippedNonEmptyStr
    description: Optional[str] = None


# Properties to receive via API on update
class ArticleColumnUpdate(ArticleColumnBase):
    name: Optional[StrippedNonEmptyStr] = None
    description: Optional[str] = None


class ArticleColumnInDBBase(ArticleColumnBase):
    uuid: UUID
    name: StrippedNonEmptyStr
    description: Optional[str]
    created_at: datetime.datetime

    class Config:
        orm_mode = True


class UserArticleColumnSubscription(BaseModel):
    article_column_uuid: str
    subscription_count: int
    subscribed_by_me: bool


# Additional properties to return via API
class ArticleColumn(ArticleColumnInDBBase):
    owner: UserPreview
    subscription: Optional[UserArticleColumnSubscription] = None
