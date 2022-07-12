from typing import Literal

from pydantic import BaseModel

from chafan_core.app.schemas.notification import Notification


class WsUserMsg(BaseModel):
    type: Literal["notification"]
    data: Notification
