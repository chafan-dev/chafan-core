from typing import Any, List, Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from chafan_core.app import crud, schemas
from chafan_core.app.api import deps
from chafan_core.app.cached_layer import CachedLayer
from chafan_core.app.common import OperationType, is_dev
from chafan_core.app.endpoint_utils import get_site
from chafan_core.app.materialize import (
    check_user_in_site,
    get_active_site_profile,
    user_in_site,
)
from chafan_core.utils.base import HTTPException_

router = APIRouter()

if is_dev():

    @router.post("/", response_model=schemas.Profile, include_in_schema=False)
    def create_profile(
        *,
        cached_layer: CachedLayer = Depends(deps.get_cached_layer_logged_in),
        db: Session = Depends(deps.get_db),
        profile_in: schemas.ProfileCreate,
    ) -> Any:
        """
        Invite and create new profile for new user as moderator.
        """
        site = crud.site.get_by_uuid(db, uuid=profile_in.site_uuid)
        if not site:
            raise HTTPException_(
                status_code=400,
                detail="The site doesn't exists in the system.",
            )
        if cached_layer.principal_id != site.moderator_id:
            raise HTTPException_(
                status_code=400,
                detail="The site is not moderated by current user.",
            )
        owner = crud.user.get_by_uuid(db, uuid=profile_in.owner_uuid)
        if owner is None:
            raise HTTPException_(
                status_code=400,
                detail="Invalid owner UUID",
            )
        site = crud.site.get_by_uuid(db, uuid=profile_in.site_uuid)
        if site is None:
            raise HTTPException_(
                status_code=400,
                detail="Invalid site UUID",
            )
        profile = crud.profile.get_by_user_and_site(
            db, owner_id=owner.id, site_id=site.id
        )
        if profile:
            raise HTTPException_(
                status_code=400,
                detail="The profile exists.",
            )
        return cached_layer.create_site_profile(owner=owner, site_uuid=site.uuid)


@router.get("/members/{site_uuid}/{owner_uuid}", response_model=Optional[schemas.Profile])  # type: ignore
def view_profile(
    *,
    cached_layer: CachedLayer = Depends(deps.get_cached_layer_logged_in),
    site_uuid: str,
    owner_uuid: str,
    current_user_id: int = Depends(deps.get_current_user_id),
) -> Any:
    """
    View profile as one self or another user in the same site.
    """
    db = cached_layer.get_db()
    site = get_site(db, site_uuid)
    if user_in_site(
        db,
        site=site,
        user_id=current_user_id,
        op_type=OperationType.ReadSite,
    ):
        owner = crud.user.get_by_uuid(db, uuid=owner_uuid)
        if owner is None:
            raise HTTPException_(
                status_code=400,
                detail="Invalid user UUID.",
            )
        profile = get_active_site_profile(db, site=site, user_id=owner.id)
        if profile:
            return cached_layer.materializer.profile_schema_from_orm(profile)
    return None


@router.get("/members/{site_uuid}", response_model=List[schemas.Profile])
def get_profiles(
    *,
    cached_layer: CachedLayer = Depends(deps.get_cached_layer_logged_in),
    site_uuid: str,
    current_user_id: int = Depends(deps.get_current_user_id),
) -> Any:
    """
    Get profiles of a site as moderator or site member.
    """
    db = cached_layer.get_db()
    site = get_site(db, site_uuid)
    if current_user_id != site.moderator_id:
        check_user_in_site(
            db, site=site, user_id=current_user_id, op_type=OperationType.ReadSite
        )
    return [cached_layer.materializer.profile_schema_from_orm(p) for p in site.profiles]
