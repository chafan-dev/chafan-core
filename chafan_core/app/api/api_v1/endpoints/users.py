from typing import Any

from fastapi import APIRouter, Depends, Request, Response

from chafan_core.app import schemas
from chafan_core.app.api import deps
from chafan_core.app.infra.request_context import RequestContext
from chafan_core.app.limiter import limiter
from chafan_core.app.services import users as users_service

router = APIRouter()


@router.post("/invite", response_model=schemas.GenericResponse)
@limiter.limit("60/minute")
def invite_new_user(
    response: Response,
    request: Request,
    *,
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    user_invite_in: schemas.UserInvite,
) -> Any:
    """
    Invite internal user by id to a site.
    """
    users_service.invite_user_to_site(ctx, user_invite_in=user_invite_in)
    return schemas.GenericResponse()
