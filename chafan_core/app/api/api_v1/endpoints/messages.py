from typing import Any

from fastapi import APIRouter, Depends

from chafan_core.app import crud, schemas
from chafan_core.app.api import deps
from chafan_core.app.cached_layer import CachedLayer
from chafan_core.app.materialize import check_user_in_channel
from chafan_core.utils.base import HTTPException_

router = APIRouter()


@router.get("/{id}", response_model=schemas.Message)
def get_message(
    *,
    cached_layer: CachedLayer = Depends(deps.get_cached_layer_logged_in),
    id: int,
) -> Any:
    """
    Get message from a channel that user belongs to.
    """
    message = crud.message.get(cached_layer.get_db(), id=id)
    if message is None:
        raise HTTPException_(
            status_code=400,
            detail="The message doesn't exists in the system.",
        )
    check_user_in_channel(cached_layer.get_current_active_user(), message.channel)
    return cached_layer.materializer.message_schema_from_orm(message)


@router.post("/", response_model=schemas.Message)
def create_message(
    *,
    cached_layer: CachedLayer = Depends(deps.get_cached_layer_logged_in),
    message_in: schemas.MessageCreate,
) -> Any:
    """
    Create new message authored by the current user in one of the belonging channels.
    """
    channel = crud.channel.get(cached_layer.get_db(), id=message_in.channel_id)
    if channel is None:
        raise HTTPException_(
            status_code=400,
            detail="The channel doesn't exists in the system.",
        )
    current_user = cached_layer.get_current_active_user()
    check_user_in_channel(current_user, channel)
    return cached_layer.materializer.message_schema_from_orm(
        crud.message.create_with_author(
            cached_layer.broker,
            obj_in=message_in,
            author=current_user,
        )
    )
