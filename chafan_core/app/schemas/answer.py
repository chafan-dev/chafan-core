import datetime
from typing import List, Optional

from pydantic import BaseModel

from chafan_core.utils.base import ContentVisibility
from chafan_core.app.schemas.comment import Comment, CommentForVisitor
from chafan_core.app.schemas.preview import UserPreview
from chafan_core.app.schemas.question import QuestionPreview, QuestionPreviewForVisitor
from chafan_core.app.schemas.richtext import RichText
from chafan_core.app.schemas.site import Site


# Shared properties
class AnswerBase(BaseModel):
    pass


# Properties to receive via API on creation
class AnswerCreate(AnswerBase):
    content: RichText
    question_uuid: str
    is_published: bool
    visibility: ContentVisibility
    writing_session_uuid: str


# Properties to receive via API on update
class AnswerUpdate(AnswerBase):
    updated_content: Optional[RichText]
    is_draft: bool
    visibility: ContentVisibility


class AnswerInDBBase(AnswerBase):
    uuid: str
    updated_at: datetime.datetime
    featured_at: Optional[datetime.datetime] = None
    # Whether there is any published version, and if so, the `body` will be published one, otherwise `body` is the draft
    is_published: bool
    # The auto-save date of draft
    draft_saved_at: Optional[datetime.datetime]
    is_hidden_by_moderator: bool
    visibility: ContentVisibility
    keywords: Optional[List[str]]

    class Config:
        orm_mode = True


class AnswerModUpdate(BaseModel):
    is_hidden_by_moderator: Optional[bool] = None


class AnswerUpvotes(BaseModel):
    answer_uuid: str
    count: int
    upvoted: bool


# Additional properties to return via API
class Answer(AnswerInDBBase):
    content: RichText
    comments: List[Comment] = []
    author: UserPreview
    question: QuestionPreview
    site: Site
    comment_writable: bool
    bookmark_count: int
    bookmarked: bool
    view_times: int
    archives_count: int
    upvotes: Optional[AnswerUpvotes] = None
    suggest_editable: bool = False


class AnswerForVisitor(AnswerInDBBase):
    content: RichText
    author: UserPreview
    site: Site
    view_times: int
    comments: List[CommentForVisitor] = []
    question: QuestionPreviewForVisitor
    upvotes: Optional[AnswerUpvotes] = None
    suggest_editable: bool = False


class AnswerDoc(BaseModel):
    """
    Used for creating ES index
    """

    from chafan_core.app.schemas.question import QuestionDoc

    id: int
    question: QuestionDoc
    body_prerendered_text: str


class AnswerDraft(BaseModel):
    content_draft: Optional[RichText]
    draft_saved_at: Optional[datetime.datetime]


class AnswerPreviewBase(BaseModel):
    uuid: str
    body: str
    body_is_truncated: bool = True
    author: UserPreview
    upvotes_count: int
    is_hidden_by_moderator: bool
    featured_at: Optional[datetime.datetime] = None


class AnswerPreview(AnswerPreviewBase):
    question: QuestionPreview
    full_answer: Optional[Answer]


class AnswerPreviewForVisitor(AnswerPreviewBase):
    question: QuestionPreviewForVisitor
    full_answer: Optional[AnswerForVisitor]
