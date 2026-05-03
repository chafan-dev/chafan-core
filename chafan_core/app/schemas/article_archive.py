import datetime

from pydantic import BaseModel

from chafan_core.app.schemas.richtext import RichText
from chafan_core.utils.constants import editor_T


class ArticleArchiveInDB(BaseModel):
    id: int
    title: str
    created_at: datetime.datetime

    # TODO: deprecate
    body: str
    editor: editor_T

    class Config:
        from_attributes = True


class ArticleArchive(ArticleArchiveInDB):
    content: RichText
