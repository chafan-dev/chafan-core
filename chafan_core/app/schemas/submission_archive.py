import datetime
from typing import List, Optional

from pydantic import BaseModel

from chafan_core.app.schemas.richtext import RichText


class SubmissionEditableSnapshot(BaseModel):
    title: str
    desc: Optional[RichText]
    topic_uuids: Optional[List[str]]


class SubmissionArchive(SubmissionEditableSnapshot):
    id: int
    url: Optional[str]
    created_at: datetime.datetime
