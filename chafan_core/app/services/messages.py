"""Private-message domain service."""

from __future__ import annotations

from typing import List

from chafan_core.app import crud, schemas
from chafan_core.app.responders import misc as misc_responder
from chafan_core.app.user_permission import check_user_in_channel
from chafan_core.utils.base import HTTPException_


def get_message(ctx, message_id: int) -> schemas.Message:
    message = crud.message.get(ctx.get_db(), id=message_id)
    if message is None:
        raise HTTPException_(
            status_code=400,
            detail="The message doesn't exist in the system.",
        )
    check_user_in_channel(ctx.get_current_active_user(), message.channel)
    return misc_responder.message_schema_from_orm(ctx.principal_view, message)


def create_message(ctx, *, message_in: schemas.MessageCreate) -> schemas.Message:
    channel = crud.channel.get(ctx.get_db(), id=message_in.channel_id)
    if channel is None:
        raise HTTPException_(
            status_code=400,
            detail="The channel doesn't exist in the system.",
        )
    current_user = ctx.get_current_active_user()
    check_user_in_channel(current_user, channel)
    message = crud.message.create_with_author(
        ctx,
        obj_in=message_in,
        author=current_user,
    )
    return misc_responder.message_schema_from_orm(ctx.principal_view, message)


def list_channel_messages(ctx, channel_id: int) -> List[schemas.Message]:
    channel = crud.channel.get(ctx.get_db(), id=channel_id)
    if channel is None:
        raise HTTPException_(
            status_code=400,
            detail="The channel doesn't exist in the system.",
        )
    check_user_in_channel(ctx.get_current_active_user(), channel)
    mat = ctx.principal_view
    return [misc_responder.message_schema_from_orm(mat, m) for m in channel.messages]
