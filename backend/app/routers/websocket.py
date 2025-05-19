from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from typing import Optional
import logging

from app.core.websocket_manager import manager

router = APIRouter()
logger = logging.getLogger("websocket")

@router.websocket("/ws/game/{game_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    game_id: str,
    token: Optional[str] = Query(None)
):
    connected = await manager.connect(websocket, game_id, token)
    if not connected:
        return

    try:
        while True:
            data = await websocket.receive_text()
            logger.debug(f"Received raw message from {manager.authenticated_users.get(websocket, 'Unknown')}: {data}")

    except WebSocketDisconnect:
        manager.disconnect(websocket, game_id)
    except Exception as e:
        logger.error(f"{game_id} odasında WebSocket hatası: {e}")
        manager.disconnect(websocket, game_id)