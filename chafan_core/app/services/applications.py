"""Site membership application domain service."""

from __future__ import annotations

from typing import List

from chafan_core.app import crud, models, schemas
from chafan_core.app.responders import misc as misc_responder
from chafan_core.app.services import sites as sites_service
from chafan_core.utils.base import HTTPException_


def application_schema(ctx, application: models.Application) -> schemas.Application:
    return misc_responder.application_schema_from_orm(ctx.principal_view, application)


def list_pending_applications(ctx) -> List[schemas.Application]:
    current_user = ctx.get_current_active_user()
    db = ctx.get_db()
    if current_user.is_superuser:
        sites = crud.site.get_all(db)
    else:
        sites = current_user.moderated_sites
    return [
        application_schema(ctx, application)
        for site in sites
        for application in crud.application.get_pending_applications(
            db, site_id=site.id
        )
    ]


def approve_application(ctx, *, application_id: int) -> schemas.Application:
    db = ctx.get_db()
    current_user_id = ctx.unwrapped_principal_id()
    application = crud.application.get(db, id=application_id)
    if application is None:
        raise HTTPException_(
            status_code=400,
            detail="The application doesn't exist in the system.",
        )
    if (
        not ctx.get_current_user().is_superuser
    ) and application.applied_site.moderator_id != current_user_id:
        raise HTTPException_(
            status_code=400,
            detail="Unauthorized.",
        )
    if not application.pending:
        raise HTTPException_(
            status_code=400,
            detail="Not pending.",
        )
    existing_profile = crud.profile.get_by_user_and_site(
        db, owner_id=application.applicant.id, site_id=application.applied_site.id
    )
    if not existing_profile:
        sites_service.create_site_profile(
            db,
            ctx.principal_view,
            owner=application.applicant,
            site_uuid=application.applied_site.uuid,
        )
    application.pending = False
    db.add(application)
    db.commit()
    db.refresh(application)
    return application_schema(ctx, application)
