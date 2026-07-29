"""Notification domain service."""

from __future__ import annotations

from typing import List, Literal

from sqlalchemy.orm import Session

from chafan_core.app import crud, schemas
from chafan_core.app.infra.request_context import RequestContext
from chafan_core.app.responders import event as event_responder
from chafan_core.app.schemas.notification import NotificationUpdate
from chafan_core.app.infra.runtime import execute_with_broker
from chafan_core.utils.base import HTTPException_, filter_not_none, unwrap
from chafan_core.utils.validators import CaseInsensitiveEmailStr


def list_unread(ctx) -> List[schemas.Notification]:
    return filter_not_none(
        [
            event_responder.notification_schema_from_orm(ctx.principal_view, n)
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
            event_responder.notification_schema_from_orm(ctx.principal_view, n)
            for n in crud.notification.get_read(
                ctx.get_db(),
                receiver_id=ctx.unwrapped_principal_id(),
            )
        ]
    )


def unsubscribe_by_email_token(
    db: Session,
    *,
    email: CaseInsensitiveEmailStr,
    type: Literal["unread_notifications"],
    unsubscribe_token: str,
) -> None:
    """Turn off an email digest from a one-click link in that email.

    The unsubscribe token *is* the credential here -- these links are opened
    straight from a mail client, with no session. A bad token and an unknown
    address deliberately report the same "Invalid link".
    """
    user = crud.user.get_by_email(db, email=email)
    if user is None:
        raise HTTPException_(status_code=400, detail="Invalid link")
    if user.unsubscribe_token != unsubscribe_token:
        raise HTTPException_(status_code=400, detail="Invalid link")
    if type == "unread_notifications":
        user.enable_deliver_unread_notifications = False


def update_notification(
    *, id: int, current_user_id: int, notif_in: NotificationUpdate
) -> None:
    def runnable(broker: RequestContext) -> None:
        broker.principal_id = current_user_id
        broker.update_notification(
            unwrap(crud.notification.get(broker.get_db(), id)), notif_in
        )

    execute_with_broker(runnable)
