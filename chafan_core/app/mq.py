from contextlib import contextmanager
from typing import Iterator, Optional

import pika
from pika.adapters.utils.connection_workflow import AMQPConnectionWorkflowFailed
from pika.channel import Channel
from pika.exceptions import AMQPConnectionError, ChannelClosedByBroker

from chafan_core.app import models
from chafan_core.app.config import get_mq_url
from chafan_core.app.data_broker import DataBroker
from chafan_core.app.materialize import Materializer
from chafan_core.app.schemas.mq import WsUserMsg


@contextmanager
def pika_chan(queue: str) -> Iterator[Optional[Channel]]:
    try:
        conn = pika.BlockingConnection(pika.URLParameters(get_mq_url()))
        chan = conn.channel()
        chan.queue_declare(queue=queue)
        yield chan
        chan.close()
        conn.close()
    except (
        AMQPConnectionError,
        AMQPConnectionWorkflowFailed,
        ChannelClosedByBroker,
    ):
        yield None


def get_ws_queue_for_user(user_id: int) -> str:
    return f"chafan.ws.users.{user_id}"


def push_notification(data_broker: DataBroker, *, notif: models.Notification) -> None:

    n = Materializer(data_broker, notif.receiver_id).notification_schema_from_orm(
        notif,
    )
    if n is None:
        return
    queue = get_ws_queue_for_user(notif.receiver_id)
    with pika_chan(queue) as chan:
        if chan:
            msg = WsUserMsg(
                type="notification",
                data=n,
            )
            chan.basic_publish(exchange="", routing_key=queue, body=msg.json())
