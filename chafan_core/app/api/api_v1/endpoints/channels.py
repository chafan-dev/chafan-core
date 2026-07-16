from typing import Any, List

from fastapi import APIRouter, Depends

from chafan_core.app import schemas
from chafan_core.app.api import deps
from chafan_core.app.infra.request_context import RequestContext
from chafan_core.app.services import channels as channels_service
from chafan_core.app.services import messages as messages_service

import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/{id}", response_model=schemas.Channel)
def get_channel(
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    *,
    id: int,
) -> Any:
    """Get channel that user belongs to."""
    return channels_service.get_channel(ctx, id)


@router.get("/{id}/messages/", response_model=List[schemas.Message])
def get_channel_messages(
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    *,
    id: int,
) -> Any:
    """Get channel's all messages that user belongs to."""
    return messages_service.list_channel_messages(ctx, id)


@router.post("/", response_model=schemas.Channel)
def create_channel(
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    *,
    channel_in: schemas.ChannelCreate,
) -> Any:
    """Create new private channel by the current user."""
    logger.info("create_channel")
    return channels_service.create_private_channel(ctx, channel_in=channel_in)
