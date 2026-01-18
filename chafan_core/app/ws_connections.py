from typing import MutableMapping

from fastapi.websockets import WebSocket

import logging

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self) -> None:
        # User ID -> WebSocket
        self.active_connections: MutableMapping[int, WebSocket] = {}

    async def connect(self, user_id: int, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections[user_id] = websocket

    def remove(self, user_id: int) -> None:
        del self.active_connections[user_id]

    async def send_message(self, message: str, user_id: int) -> None:
        ws = self.active_connections.get(user_id)
        if ws:
            await ws.send_text(message)
        else:
            logger.error(f"Failed to send_message. No active ws for user={user_id}")


manager = ConnectionManager()
