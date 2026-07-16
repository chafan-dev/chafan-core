from typing import Any

from fastapi import APIRouter, Depends

from chafan_core.app import schemas
from chafan_core.app.api import deps
from chafan_core.app.infra.request_context import RequestContext
from chafan_core.app.schemas.invitation_link import InvitationLinkCreate
from chafan_core.app.services import invitations as invitations_service

router = APIRouter()


@router.post("/", response_model=schemas.InvitationLink)
def create_invitation_link(
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    *,
    create_in: InvitationLinkCreate,
) -> Any:
    return invitations_service.create_invitation_link(ctx, create_in=create_in)


@router.get("/daily", response_model=schemas.InvitationLink)
def get_daily_invitation_link(
    ctx: RequestContext = Depends(deps.get_request_context),
) -> Any:
    return invitations_service.get_daily_invitation_link(ctx)


@router.get("/{uuid}", response_model=schemas.InvitationLink)
def get_invitation_link(
    ctx: RequestContext = Depends(deps.get_request_context), *, uuid: str
) -> Any:
    return invitations_service.get_invitation_link(ctx, uuid)


@router.post("/{uuid}/join", response_model=schemas.GenericResponse)
def join_site_with_invitation_link(
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    *,
    uuid: str,
) -> Any:
    invitations_service.join_site_with_invitation_link(ctx, uuid=uuid)
    return schemas.GenericResponse()
