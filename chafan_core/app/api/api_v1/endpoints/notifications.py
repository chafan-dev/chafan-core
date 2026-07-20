from typing import Any, List

from fastapi import APIRouter, Depends, Request, Response

from chafan_core.app import schemas
from chafan_core.app.api import deps
from chafan_core.app.infra.request_context import RequestContext
from chafan_core.app.limiter import limiter
from chafan_core.app.schemas.notification import NotificationUpdate
from chafan_core.app.services import notifications as notifications_service

router = APIRouter()


@router.get("/unread/", response_model=List[schemas.Notification])
def get_unread_notifications(
    *,
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
) -> Any:
    return notifications_service.list_unread(ctx)


@router.get("/read/", response_model=List[schemas.Notification])
def get_read_notifications(
    *,
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
) -> Any:
    return notifications_service.list_read(ctx)


@router.put("/{id}", response_model=schemas.GenericResponse)
@limiter.limit("60/minute")
def update_notification(
    response: Response,
    request: Request,
    *,
    id: int,
    notif_in: NotificationUpdate,
    current_user_id: int = Depends(deps.get_current_user_id),
) -> Any:
    notifications_service.update_notification(
        id=id, current_user_id=current_user_id, notif_in=notif_in
    )
    return schemas.GenericResponse()
