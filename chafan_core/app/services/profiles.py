"""Site profile (membership) domain service."""

from __future__ import annotations

from typing import List, Optional

from chafan_core.app import crud, schemas
from chafan_core.app.common import OperationType
from chafan_core.app.endpoint_utils import get_site
from chafan_core.app.responders import misc as misc_responder
from chafan_core.app.user_permission import (
    check_user_in_site,
    get_active_site_profile,
    user_in_site,
)
from chafan_core.utils.base import HTTPException_


def profile_schema(ctx, profile) -> schemas.Profile:
    return misc_responder.profile_schema_from_orm(ctx.principal_view, profile)


def view_profile(
    ctx, *, site_uuid: str, owner_uuid: str, current_user_id: int
) -> Optional[schemas.Profile]:
    """View profile as one self or another user in the same site."""
    db = ctx.get_db()
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
            return profile_schema(ctx, profile)
    return None


def list_site_profiles(
    ctx, *, site_uuid: str, current_user_id: int
) -> List[schemas.Profile]:
    """Get profiles of a site as moderator or site member."""
    db = ctx.get_db()
    site = get_site(db, site_uuid)
    if current_user_id != site.moderator_id:
        check_user_in_site(
            db, site=site, user_id=current_user_id, op_type=OperationType.ReadSite
        )
    return [profile_schema(ctx, p) for p in site.profiles]
