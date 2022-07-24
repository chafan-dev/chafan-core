from typing import Any

from fastapi import APIRouter, Depends

from chafan_core.app import crud, schemas
from chafan_core.app.api import deps
from chafan_core.app.cached_layer import CachedLayer
from chafan_core.app.common import OperationType
from chafan_core.app.endpoint_utils import get_site
from chafan_core.app.materialize import check_user_in_site
from chafan_core.app.schemas.invitation_link import InvitationLinkCreate
from chafan_core.utils.base import HTTPException_

router = APIRouter()


@router.post("/", response_model=schemas.InvitationLink)
def create_invitation_link(
    cached_layer: CachedLayer = Depends(deps.get_cached_layer_logged_in),
    *,
    create_in: InvitationLinkCreate,
) -> Any:
    current_user = cached_layer.get_current_active_user()
    invited_to_site_id = None
    db = cached_layer.get_db()
    if create_in.invited_to_site_uuid is not None:
        invited_to_site = get_site(db, create_in.invited_to_site_uuid)
        check_user_in_site(
            db,
            site=invited_to_site,
            user_id=current_user.id,
            op_type=OperationType.AddSiteMember,
        )
        invited_to_site_id = invited_to_site.id
    return cached_layer.materializer.invitation_link_schema_from_orm(
        crud.invitation_link.create_invitation(
            db, invited_to_site_id=invited_to_site_id, inviter=current_user
        )
    )


@router.get("/daily", response_model=schemas.InvitationLink)
def get_daily_invitation_link(
    cached_layer: CachedLayer = Depends(deps.get_cached_layer),
) -> Any:
    return cached_layer.get_daily_invitation_link()


@router.get("/{uuid}", response_model=schemas.InvitationLink)
def get_invitation_link(
    cached_layer: CachedLayer = Depends(deps.get_cached_layer), *, uuid: str
) -> Any:
    invitation_link = crud.invitation_link.get_by_uuid(cached_layer.get_db(), uuid=uuid)
    if invitation_link is None:
        raise HTTPException_(
            status_code=404,
            detail="Invalid invitation link",
        )
    return cached_layer.materializer.invitation_link_schema_from_orm(invitation_link)


@router.post("/{uuid}/join", response_model=schemas.GenericResponse)
def join_site_with_invitation_link(
    cached_layer: CachedLayer = Depends(deps.get_cached_layer_logged_in),
    *,
    uuid: str,
) -> Any:
    current_user = cached_layer.get_current_active_user()
    db = cached_layer.get_db()
    invitation_link = crud.invitation_link.get_by_uuid(db, uuid=uuid)
    if (
        invitation_link is None
        or not cached_layer.materializer.invitation_link_schema_from_orm(
            invitation_link
        ).valid
    ):
        raise HTTPException_(
            status_code=400,
            detail="Invalid invitation link",
        )
    if invitation_link.invited_to_site_id is None:
        raise HTTPException_(
            status_code=400,
            detail="Not for a specific site",
        )
    existing_profile = crud.profile.get_by_user_and_site(
        db, owner_id=current_user.id, site_id=invitation_link.invited_to_site_id
    )
    if not existing_profile:
        cached_layer.create_site_profile(
            owner=current_user,
            site_uuid=invitation_link.invited_to_site.uuid,
        )
        invitation_link.remaining_quota -= 1
        db.add(invitation_link)
        db.commit()
    return schemas.GenericResponse()
