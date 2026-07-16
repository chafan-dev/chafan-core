from typing import Any, List

from fastapi import APIRouter, Depends, Request, Response

from chafan_core.app import schemas
from chafan_core.app.api import deps
from chafan_core.app.infra.request_context import RequestContext
from chafan_core.app.limiter import limiter
from chafan_core.app.services import applications as applications_service

router = APIRouter()


@router.get("/pending/", response_model=List[schemas.Application])
@limiter.limit("10/minute")
def get_pending_applications(
    response: Response,
    request: Request,
    *,
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
) -> Any:
    return applications_service.list_pending_applications(ctx)


@router.put("/{id}/approve", response_model=schemas.Application)
@limiter.limit("60/minute")
def update_application(
    response: Response,
    request: Request,
    *,
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    id: int,
) -> Any:
    return applications_service.approve_application(ctx, application_id=id)
