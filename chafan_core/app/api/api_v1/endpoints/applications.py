from typing import Any, List

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from chafan_core.app import crud, schemas
from chafan_core.app.api import deps
from chafan_core.app.cached_layer import CachedLayer
from chafan_core.app.limiter import limiter
from chafan_core.utils.base import HTTPException_

router = APIRouter()


@router.get("/pending/", response_model=List[schemas.Application])
@limiter.limit("10/minute")
def get_pending_applications(
    response: Response,
    request: Request,
    *,
    cached_layer: CachedLayer = Depends(deps.get_cached_layer_logged_in),
) -> Any:
    current_user = cached_layer.get_current_active_user()
    if current_user.is_superuser:
        sites = crud.site.get_all(cached_layer.get_db())
    else:
        sites = current_user.moderated_sites
    return [
        cached_layer.materializer.application_schema_from_orm(application)
        for site in sites
        for application in crud.application.get_pending_applications(
            cached_layer.get_db(), site_id=site.id
        )
    ]


@router.put("/{id}/approve", response_model=schemas.Application)
@limiter.limit("60/minute")
def update_application(
    response: Response,
    request: Request,
    *,
    cached_layer: CachedLayer = Depends(deps.get_cached_layer_logged_in),
    db: Session = Depends(deps.get_db),
    id: int,
    current_user_id: int = Depends(deps.get_current_user_id),
) -> Any:
    application = crud.application.get(db, id=id)
    if application is None:
        raise HTTPException_(
            status_code=400,
            detail="The application doesn't exists in the system.",
        )
    if (
        not cached_layer.get_current_user().is_superuser
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
        cached_layer.create_site_profile(
            owner=application.applicant,
            site_uuid=application.applied_site.uuid,
        )
    application.pending = False
    db.add(application)
    db.commit()
    db.refresh(application)
    return cached_layer.materializer.application_schema_from_orm(application)
