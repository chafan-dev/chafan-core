import datetime
from typing import List

from pydantic import BaseModel

from chafan_core.app.schemas.richtext import RichText
from chafan_core.app.schemas.topic import Topic
from chafan_core.utils.constants import editor_T


class ArticleArchiveInDB(BaseModel):
    id: int
    title: str
    topics: List[Topic] = []
    created_at: datetime.datetime

    # TODO: deprecate
    body: str
    editor: editor_T

    class Config:
        from_attributes = True


class ArticleArchive(ArticleArchiveInDB):
    content: RichText
