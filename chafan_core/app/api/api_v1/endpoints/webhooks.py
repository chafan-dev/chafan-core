from typing import Any

from fastapi import APIRouter, Depends

from chafan_core.app import schemas
from chafan_core.app.api import deps
from chafan_core.app.infra.request_context import RequestContext
from chafan_core.app.services import webhooks as webhooks_service

router = APIRouter()


@router.post("/", response_model=schemas.Webhook)
def create_webhook(
    *,
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    webhook_in: schemas.WebhookCreate,
) -> Any:
    """
    Create new webhook as user.
    """
    return webhooks_service.create_webhook(ctx, webhook_in=webhook_in)


@router.put("/{id}", response_model=schemas.Webhook)
def update_webhook(
    *,
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    id: int,
    webhook_in: schemas.WebhookUpdate,
) -> Any:
    return webhooks_service.update_webhook(
        ctx, webhook_id=id, webhook_in=webhook_in
    )
