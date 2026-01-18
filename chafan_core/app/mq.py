import logging

logger = logging.getLogger(__name__)


import logging

from chafan_core.app import models
from chafan_core.app.data_broker import DataBroker
from chafan_core.app.materialize import Materializer
from chafan_core.app.schemas.mq import WsUserMsg

logger = logging.getLogger(__name__)


def get_ws_queue_for_user(user_id: int) -> str:
    return f"chafan.ws.users.{user_id}"


def push_notification(data_broker: DataBroker, *, notif: models.Notification) -> None:
    n = Materializer(data_broker, notif.receiver_id).notification_schema_from_orm(
        notif,
    )
    logger.info("push_notification " + str(n)[:100])
    if n is None:
        return
    queue_name = get_ws_queue_for_user(notif.receiver_id)
    msg = WsUserMsg(
        type="notification",
        data=n,
    )
    redis = data_broker.get_redis()
    redis.rpush(queue_name, msg.json())
