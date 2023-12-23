import asyncio
import secrets
from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends, Query, status
from fastapi.websockets import WebSocket, WebSocketDisconnect
from websockets.exceptions import ConnectionClosedError, ConnectionClosedOK

from chafan_core.app import schemas, ws_connections
from chafan_core.app.api import deps
from chafan_core.app.common import get_redis_cli
from chafan_core.app.mq import get_ws_queue_for_user, pika_chan

router = APIRouter()


@router.post("/token", response_model=schemas.WsAuthResponse)
def get_ws_token(
    *,
    current_user_id: int = Depends(deps.get_current_user_id),
) -> Any:
    redis = get_redis_cli()
    token = secrets.token_urlsafe(10)
    key = f"chafan:ws-token:{token}"
    redis.delete(key)
    redis.set(key, current_user_id, ex=timedelta(minutes=1))
    return schemas.WsAuthResponse(token=token)


@router.websocket("")
async def ws(websocket: WebSocket, token: str = Query(...)) -> Any:
    redis = get_redis_cli()
    key = f"chafan:ws-token:{token}"
    value = redis.get(key)
    if value is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    redis.delete(key)
    user_id = int(value)
    await ws_connections.manager.connect(user_id, websocket)
    queue = get_ws_queue_for_user(user_id)
    with pika_chan(queue) as chan:
        if chan:
            try:
                while True:
                    method_frame, _, body = chan.basic_get(queue)
                    if method_frame and body and method_frame.delivery_tag:
                        await ws_connections.manager.send_message(body, user_id)
                        chan.basic_ack(method_frame.delivery_tag)
                    else:
                        await asyncio.sleep(10)
            except (
                ConnectionClosedError,
                WebSocketDisconnect,
                ConnectionResetError,
                ConnectionClosedOK,
                RuntimeError,
            ):
                ws_connections.manager.remove(user_id)
