from typing import Any

from fastapi import APIRouter, Depends

from chafan_core.app import schemas
from chafan_core.app.api import deps
from chafan_core.app.infra.request_context import RequestContext
from chafan_core.app.services import messages as messages_service

router = APIRouter()


@router.get("/{id}", response_model=schemas.Message)
def get_message(
    *,
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    id: int,
) -> Any:
    """Get message from a channel that user belongs to."""
    return messages_service.get_message(ctx, id)


@router.post("/", response_model=schemas.Message)
def create_message(
    *,
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    message_in: schemas.MessageCreate,
) -> Any:
    """Create new message authored by the current user in one of the belonging channels."""
    return messages_service.create_message(ctx, message_in=message_in)
