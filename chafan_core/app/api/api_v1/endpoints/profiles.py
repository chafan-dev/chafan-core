from typing import Any, List, Optional

from fastapi import APIRouter, Depends

from chafan_core.app import schemas
from chafan_core.app.api import deps
from chafan_core.app.infra.request_context import RequestContext
from chafan_core.app.services import profiles as profiles_service

router = APIRouter()


@router.get(
    "/members/{site_uuid}/{owner_uuid}", response_model=Optional[schemas.Profile]
)
def view_profile(
    *,
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    site_uuid: str,
    owner_uuid: str,
    current_user_id: int = Depends(deps.get_current_user_id),
) -> Any:
    """
    View profile as one self or another user in the same site.
    """
    return profiles_service.view_profile(
        ctx,
        site_uuid=site_uuid,
        owner_uuid=owner_uuid,
        current_user_id=current_user_id,
    )


@router.get("/members/{site_uuid}", response_model=List[schemas.Profile])
def get_profiles(
    *,
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    site_uuid: str,
    current_user_id: int = Depends(deps.get_current_user_id),
) -> Any:
    """
    Get profiles of a site as moderator or site member.
    """
    return profiles_service.list_site_profiles(
        ctx, site_uuid=site_uuid, current_user_id=current_user_id
    )
