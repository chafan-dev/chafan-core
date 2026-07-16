from typing import Any, List

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from chafan_core.app import crud, schemas
from chafan_core.app.api import deps
from chafan_core.app.infra.request_context import RequestContext
from chafan_core.app.limiter import limiter
from chafan_core.app.services import sites as sites_service
from chafan_core.utils.base import HTTPException_

router = APIRouter()


@router.get("/pending/", response_model=List[schemas.Application])
@limiter.limit("10/minute")
def get_pending_applications(
    response: Response,
    request: Request,
    *,
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
) -> Any:
    current_user = ctx.get_current_active_user()
    if current_user.is_superuser:
        sites = crud.site.get_all(ctx.get_db())
    else:
        sites = current_user.moderated_sites
    return [
        ctx.materializer.application_schema_from_orm(application)
        for site in sites
        for application in crud.application.get_pending_applications(
            ctx.get_db(), site_id=site.id
        )
    ]


@router.put("/{id}/approve", response_model=schemas.Application)
@limiter.limit("60/minute")
def update_application(
    response: Response,
    request: Request,
    *,
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    db: Session = Depends(deps.get_db),
    id: int,
    current_user_id: int = Depends(deps.get_current_user_id),
) -> Any:
    application = crud.application.get(db, id=id)
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
            ctx.materializer,
            owner=application.applicant,
            site_uuid=application.applied_site.uuid,
        )
    application.pending = False
    db.add(application)
    db.commit()
    db.refresh(application)
    return ctx.materializer.application_schema_from_orm(application)
