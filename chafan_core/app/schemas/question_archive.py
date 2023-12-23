import datetime
from typing import List, Optional

from pydantic import BaseModel

from chafan_core.app.schemas.preview import UserPreview
from chafan_core.app.schemas.richtext import RichText
from chafan_core.app.schemas.topic import Topic
from chafan_core.utils.validators import StrippedNonEmptyStr


class QuestionArchiveInDB(BaseModel):
    id: int
    title: StrippedNonEmptyStr
    topics: List[Topic] = []
    created_at: datetime.datetime

    class Config:
        from_attributes = True


class QuestionArchive(QuestionArchiveInDB):
    editor: Optional[UserPreview]
    desc: Optional[RichText]
