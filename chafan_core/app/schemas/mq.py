from typing import Literal, Union

from pydantic import BaseModel

from chafan_core.app.schemas.notification import Notification


class WsUserMsg(BaseModel):
    type: Literal["notification"]
    data: Notification
