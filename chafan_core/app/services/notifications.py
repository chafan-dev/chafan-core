"""Notification domain service."""

from __future__ import annotations

from typing import List

from chafan_core.app import crud, schemas
from chafan_core.app.infra.request_context import RequestContext
from chafan_core.app.responders import event as event_responder
from chafan_core.app.schemas.notification import NotificationUpdate
from chafan_core.app.infra.runtime import execute_with_broker
from chafan_core.utils.base import filter_not_none, unwrap


def list_unread(ctx) -> List[schemas.Notification]:
    return filter_not_none(
        [
            event_responder.notification_schema_from_orm(ctx.materializer, n)
            for n in crud.notification.get_unread(
                ctx.get_db(),
                receiver_id=ctx.unwrapped_principal_id(),
            )
        ]
    )


def list_read(ctx) -> List[schemas.Notification]:
    # TODO: pagination
    return filter_not_none(
        [
            event_responder.notification_schema_from_orm(ctx.materializer, n)
            for n in crud.notification.get_read(
                ctx.get_db(),
                receiver_id=ctx.unwrapped_principal_id(),
            )
        ]
    )


def update_notification(
    *, id: int, current_user_id: int, notif_in: NotificationUpdate
) -> None:
    def runnable(broker: RequestContext) -> None:
        broker.principal_id = current_user_id
        broker.update_notification(
            unwrap(crud.notification.get(broker.get_db(), id)), notif_in
        )

    execute_with_broker(runnable)
