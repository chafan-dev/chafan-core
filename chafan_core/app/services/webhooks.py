"""Webhook domain service."""

from __future__ import annotations

from chafan_core.app import crud, schemas
from chafan_core.app.responders import misc as misc_responder
from chafan_core.utils.base import HTTPException_


def webhook_schema(ctx, webhook) -> schemas.Webhook:
    return misc_responder.webhook_schema_from_orm(ctx.materializer, webhook)


def create_webhook(ctx, *, webhook_in: schemas.WebhookCreate) -> schemas.Webhook:
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
    return webhook_schema(ctx, webhook)


def update_webhook(
    ctx, *, webhook_id: int, webhook_in: schemas.WebhookUpdate
) -> schemas.Webhook:
    db = ctx.get_db()
    webhook = crud.webhook.get(db, id=webhook_id)
    assert webhook is not None
    if webhook.site.moderator_id != ctx.principal_id:
        raise HTTPException_(
            status_code=500,
            detail="Unauthorized.",
        )
    updated = crud.webhook.update(db, db_obj=webhook, obj_in=webhook_in)
    return webhook_schema(ctx, updated)
