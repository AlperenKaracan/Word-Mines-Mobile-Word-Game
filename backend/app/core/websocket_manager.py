import logging
import json
from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict, List, Set

from app.core.jwt_handler import verify_token
from app.models.websocket_models import WebSocketMessage

logger = logging.getLogger("websocket_manager")
logger.setLevel(logging.INFO)

class ConnectionManager:
    def __init__(self):
        self.rooms: Dict[str, Set[WebSocket]] = {}
        self.authenticated_users: Dict[WebSocket, str] = {}

    async def connect(self, websocket: WebSocket, room_id: str, token: str | None = None):
        await websocket.accept()
        username = None
        if token:
            payload = verify_token(token)
            if payload:
                username = payload.get("sub")

        if not username:
            logger.warning(f"Kimliği doğrulanmamış bağlantı reddedildi: {room_id}")
            await websocket.close(code=4001, reason="Authentication required")
            return False

        if room_id not in self.rooms:
            self.rooms[room_id] = set()
        self.rooms[room_id].add(websocket)
        self.authenticated_users[websocket] = username
        logger.info(f"WebSocket bağlandı: {username}, oda: {room_id} ({len(self.rooms[room_id])} kullanıcı)")
        return True

    def disconnect(self, websocket: WebSocket, room_id: str):
        if room_id in self.rooms:
            self.rooms[room_id].discard(websocket)
            if not self.rooms[room_id]:
                 del self.rooms[room_id]
        username = self.authenticated_users.pop(websocket, "Unknown")
        logger.info(f"WebSocket bağlantısı kesildi: {username}, oda: {room_id}")

    async def send_personal_message(self, message: WebSocketMessage, websocket: WebSocket):
        try:
            await websocket.send_text(message.model_dump_json())
        except Exception as e:
            logger.error(f"Özel mesaj gönderimi hatası: {e}")

    async def broadcast(self, room_id: str, message: WebSocketMessage):
        if room_id in self.rooms:
            disconnected_websockets = set()
            message_json = message.model_dump_json()
            for connection in self.rooms[room_id]:
                try:
                    await connection.send_text(message_json)
                except Exception as e:
                    logger.warning(f"{room_id} odasındaki bir bağlantı  başarısız oldu, bağlantı kesiliyor. Hata: {e}")
                    disconnected_websockets.add(connection)

            for ws in disconnected_websockets:
                 self.disconnect(ws, room_id)

    async def broadcast_game_state(self, room_id: str, game_data: Dict):
        from app.models.websocket_models import GameStateUpdateMessage
        message = GameStateUpdateMessage(payload=game_data)
        await self.broadcast(room_id, message)

    async def broadcast_notification(self, room_id: str, notification: str):
        from app.models.websocket_models import NotificationMessage
        message = NotificationMessage(payload={"message": notification})
        await self.broadcast(room_id, message)


manager = ConnectionManager()