from typing import Any, List

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from chafan_core.app import crud, schemas
from chafan_core.app.api import deps
from chafan_core.app.cache_controllers.site_profiles import CachedSiteProfiles
from chafan_core.app.cached_layer import CachedLayer
from chafan_core.app.endpoint_utils import get_site
from chafan_core.app.limiter import limiter
from chafan_core.utils.base import HTTPException_

router = APIRouter()


@router.get("/pending/{site_uuid}/", response_model=List[schemas.Application])
def get_pending_applications(
    *,
    cached_layer: CachedLayer = Depends(deps.get_cached_layer_logged_in),
    site_uuid: str,
) -> Any:
    site = get_site(cached_layer.get_db(), site_uuid)
    if site is None:
        raise HTTPException_(
            status_code=400,
            detail="The site doesn't exists in the system.",
        )
    if (
        not cached_layer.get_current_user().is_superuser
    ) and site.moderator_id != cached_layer.principal_id:
        raise HTTPException_(
            status_code=400,
            detail="Unauthorized.",
        )
    return [
        cached_layer.materializer.application_schema_from_orm(application)
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
        CachedSiteProfiles.create_site_profile(
            cached_layer,
            owner=application.applicant,
            site_uuid=application.applied_site.uuid,
        )
    application.pending = False
    db.add(application)
    db.commit()
    db.refresh(application)
    return cached_layer.materializer.application_schema_from_orm(application)
