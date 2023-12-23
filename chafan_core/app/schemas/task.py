import datetime
from typing import Literal, Union

from pydantic import BaseModel

from chafan_core.app.schemas.preview import UserPreview
from chafan_core.utils.base import TaskStatus


class SuperUserBroadcastTaskDefinition(BaseModel):
    task_type: Literal["super_broadcast"] = "super_broadcast"
    message: str


class SiteModeratorBroadcastTaskDefinition(BaseModel):
    task_type: Literal["site_broadcast"] = "site_broadcast"
    to_members_of_site_uuid: str
    submission_uuid: str


TaskDefinition = Union[
    SuperUserBroadcastTaskDefinition, SiteModeratorBroadcastTaskDefinition
]


class TaskInDB(BaseModel):
    id: int
    created_at: datetime.datetime
    task_definition: TaskDefinition
    status: TaskStatus

    class Config:
        from_attributes = True


class Task(TaskInDB):
    initiator: UserPreview
