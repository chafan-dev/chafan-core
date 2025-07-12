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
from chafan_core.app.mq import get_ws_queue_for_user

import logging
logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/token", response_model=schemas.WsAuthResponse)
async def get_ws_token(
    *,
    current_user_id: int = Depends(deps.get_current_user_id),
) -> Any:
    redis = get_redis_cli()
    token = secrets.token_urlsafe(10)
    key = f"chafan:ws-token:{token}"
    redis.delete(key)
    redis.set(key, current_user_id, ex=timedelta(minutes=1))
    logger.info(f"Set WS token for user={current_user_id}")
    return schemas.WsAuthResponse(token=token)


async def _read_message_queue(redis, queue_name:str):
    item = redis.lpop(queue_name)
    return item


@router.websocket("")
async def ws(websocket: WebSocket, token: str = Query(...)) -> Any:
    # TODO 1. should not depend on redis directly 2. should use dependency
    redis = get_redis_cli()
    key = f"chafan:ws-token:{token}"
    value = redis.get(key)
    logger.info(f"Token({key}) is for user={value}")
    if value is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    redis.delete(key)
    user_id = int(value)
    await ws_connections.manager.connect(user_id, websocket)
    queue_name = get_ws_queue_for_user(user_id)
    try:
        while True:
            await asyncio.sleep(10)
            msg = await _read_message_queue(redis, queue_name)
            if msg is None or msg == "":
                continue
            logger.info(f"read from redis: {msg}")
            await ws_connections.manager.send_message(msg, user_id)
    except (
        ConnectionClosedError,
        WebSocketDisconnect,
        ConnectionResetError,
        ConnectionClosedOK,
        RuntimeError,
    ) as e:
        logger.error("websocket error: " + str(e))
        ws_connections.manager.remove(user_id)
