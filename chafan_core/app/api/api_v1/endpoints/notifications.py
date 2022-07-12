import asyncio
from typing import Any, List

from fastapi import APIRouter, Depends, Request, Response

from chafan_core.app import crud, schemas
from chafan_core.app.api import deps
from chafan_core.app.cached_layer import CachedLayer
from chafan_core.app.data_broker import DataBroker
from chafan_core.app.limiter import limiter
from chafan_core.app.schemas.notification import NotificationUpdate
from chafan_core.app.task_utils import execute_with_broker
from chafan_core.utils.base import unwrap

router = APIRouter()


@router.get("/unread/", response_model=List[schemas.Notification])
def get_unread_notifications(
    *,
    cached_layer: CachedLayer = Depends(deps.get_cached_layer_logged_in),
) -> Any:
    notifs = [
        cached_layer.materializer.notification_schema_from_orm(n)
        for n in crud.notification.get_unread(
            cached_layer.get_db(),
            receiver_id=cached_layer.unwrapped_principal_id(),
        )
    ]
    return [n for n in notifs if n is not None]


@router.get("/read/", response_model=List[schemas.Notification])
def get_read_notifications(
    *,
    cached_layer: CachedLayer = Depends(deps.get_cached_layer_logged_in),
) -> Any:
    # TODO: pagination
    notifs = [
        cached_layer.materializer.notification_schema_from_orm(n)
        for n in crud.notification.get_read(
            cached_layer.get_db(),
            receiver_id=cached_layer.unwrapped_principal_id(),
        )
    ]
    return [n for n in notifs if n is not None]


async def _update_notification(
    *, id: int, current_user_id: int, notif_in: NotificationUpdate
) -> None:
    def runnable(broker: DataBroker) -> None:
        cached_layer = CachedLayer(broker, current_user_id)
        cached_layer.update_notification(
            unwrap(crud.notification.get(cached_layer.get_db(), id)), notif_in
        )

    execute_with_broker(runnable)


@router.put("/{id}", response_model=schemas.GenericResponse)
@limiter.limit("60/minute")
async def update_notification(
    response: Response,
    request: Request,
    *,
    id: int,
    notif_in: NotificationUpdate,
    current_user_id: int = Depends(deps.get_current_user_id),
) -> Any:
    asyncio.create_task(
        _update_notification(id=id, current_user_id=current_user_id, notif_in=notif_in)
    )
    return schemas.GenericResponse()
