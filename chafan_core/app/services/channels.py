"""Channel domain service."""

from __future__ import annotations

from chafan_core.app import crud, schemas
from chafan_core.app.responders import misc as misc_responder
from chafan_core.app.user_permission import check_user_in_channel
from chafan_core.utils.base import HTTPException_


def get_channel(ctx, channel_id: int) -> schemas.Channel:
    channel = crud.channel.get(ctx.get_db(), id=channel_id)
    if channel is None:
        raise HTTPException_(
            status_code=400,
            detail="The channel doesn't exist in the system.",
        )
    check_user_in_channel(ctx.get_current_active_user(), channel)
    return misc_responder.channel_schema_from_orm(ctx.materializer, channel)


def create_private_channel(
    ctx, *, channel_in: schemas.ChannelCreate
) -> schemas.Channel:
    db = ctx.get_db()
    private_with_user = crud.user.get_by_uuid(
        db, uuid=channel_in.private_with_user_uuid
    )
    if private_with_user is None:
        raise HTTPException_(
            status_code=400,
            detail="The user doesn't exist in the system.",
        )
    current_user = ctx.get_current_active_user()
    channel = crud.channel.get_or_create_private_channel_with(
        db,
        host_user=current_user,
        with_user=private_with_user,
        obj_in=channel_in,
    )
    return misc_responder.channel_schema_from_orm(ctx.materializer, channel)
