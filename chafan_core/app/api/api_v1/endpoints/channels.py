from typing import Any, List

from fastapi import APIRouter, Depends

from chafan_core.app import crud, schemas
from chafan_core.app.api import deps
from chafan_core.app.cached_layer import CachedLayer
from chafan_core.app.materialize import check_user_in_channel
from chafan_core.utils.base import HTTPException_

import logging
logger = logging.getLogger(__name__)


router = APIRouter()


@router.get("/{id}", response_model=schemas.Channel)
def get_channel(
    cached_layer: CachedLayer = Depends(deps.get_cached_layer_logged_in),
    *,
    id: int,
) -> Any:
    """
    Get channel that user belongs to.
    """
    channel = crud.channel.get(cached_layer.get_db(), id=id)
    if channel is None:
        raise HTTPException_(
            status_code=400,
            detail="The channel doesn't exists in the system.",
        )
    current_user = cached_layer.get_current_active_user()
    check_user_in_channel(current_user, channel)
    return cached_layer.channel_schema_from_orm(channel)


@router.get("/{id}/messages/", response_model=List[schemas.Message])
def get_channel_messages(
    cached_layer: CachedLayer = Depends(deps.get_cached_layer_logged_in),
    *,
    id: int,
) -> Any:
    """
    Get channel's all messages that user belongs to.

    TODO: add skip/limit
    """
    channel = crud.channel.get(cached_layer.get_db(), id=id)
    if channel is None:
        raise HTTPException_(
            status_code=400,
            detail="The channel doesn't exists in the system.",
        )
    current_user = cached_layer.get_current_active_user()
    check_user_in_channel(current_user, channel)
    return [
        cached_layer.materializer.message_schema_from_orm(m) for m in channel.messages
    ]


@router.post("/", response_model=schemas.Channel)
def create_channel(
    cached_layer: CachedLayer = Depends(deps.get_cached_layer_logged_in),
    *,
    channel_in: schemas.ChannelCreate,
) -> Any:
    """
    Create new private channel by the current user.
    """
    logger.info("create_channel")
    private_with_user = crud.user.get_by_uuid(
        cached_layer.get_db(), uuid=channel_in.private_with_user_uuid
    )
    if private_with_user is None:
        raise HTTPException_(
            status_code=400,
            detail="The user doesn't exists in the system.",
        )
    current_user = cached_layer.get_current_active_user()
    return cached_layer.channel_schema_from_orm(
        crud.channel.get_or_create_private_channel_with(
            cached_layer.get_db(),
            host_user=current_user,
            with_user=private_with_user,
            obj_in=channel_in,
        )
    )
