import datetime

from pydantic import BaseModel

from chafan_core.app.schemas.richtext import RichText


class AnswerArchiveInDB(BaseModel):
    id: int
    created_at: datetime.datetime

    class Config:
        orm_mode = True


class AnswerArchive(AnswerArchiveInDB):
    content: RichText
