from typing import Any

from fastapi import APIRouter, Depends

from chafan_core.app import crud, schemas
from chafan_core.app.api import deps
from chafan_core.app.infra.request_context import RequestContext
from chafan_core.utils.base import HTTPException_

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
    assert webhook_in.site_uuid is not None
    site = crud.site.get_by_uuid(ctx.get_db(), uuid=webhook_in.site_uuid)
    assert site is not None
    if site.moderator_id != ctx.principal_id:
        raise HTTPException_(
            status_code=500,
            detail="Unauthorized.",
        )
    webhook = crud.webhook.create_with_site(
        ctx.get_db(), obj_in=webhook_in, site_id=site.id
    )
    return ctx.materializer.webhook_schema_from_orm(webhook)


@router.put("/{id}", response_model=schemas.Webhook)
def update_webhook(
    *,
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    id: int,
    webhook_in: schemas.WebhookUpdate,
) -> Any:
    db = ctx.get_db()
    webhook = crud.webhook.get(db, id=id)
    assert webhook is not None
    if webhook.site.moderator_id != ctx.principal_id:
        raise HTTPException_(
            status_code=500,
            detail="Unauthorized.",
        )
    return ctx.materializer.webhook_schema_from_orm(
        crud.webhook.update(db, db_obj=webhook, obj_in=webhook_in)
    )
