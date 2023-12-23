import datetime
from typing import Literal, Optional

from pydantic import BaseModel

from chafan_core.app.schemas.answer import Answer
from chafan_core.app.schemas.preview import UserPreview
from chafan_core.app.schemas.richtext import RichText


class AnswerSuggestEditInDB(BaseModel):
    uuid: str
    created_at: datetime.datetime
    comment: Optional[str]
    status: Literal["pending", "accepted", "rejected", "retracted"]
    accepted_at: Optional[datetime.datetime]
    rejected_at: Optional[datetime.datetime]
    retracted_at: Optional[datetime.datetime]
    accepted_diff_base: Optional[RichText]

    class Config:
        from_attributes = True


class AnswerSuggestEdit(AnswerSuggestEditInDB):
    body_rich_text: RichText
    author: UserPreview
    answer: Answer


class AnswerSuggestEditCreate(BaseModel):
    answer_uuid: str
    body_rich_text: RichText
    comment: Optional[str] = None


class AnswerSuggestEditUpdate(BaseModel):
    status: Literal["pending", "accepted", "rejected", "retracted"]
