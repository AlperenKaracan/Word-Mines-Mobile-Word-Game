from pydantic import BaseModel, Field
from typing import Literal, Dict, Any, Optional

class WebSocketMessage(BaseModel):
    type: str
    payload: Optional[Dict[str, Any]] = None

class GameStateUpdateMessage(WebSocketMessage):
    type: Literal["state_update"] = "state_update"
    payload: Dict[str, Any]

class ErrorMessage(WebSocketMessage):
    type: Literal["error"] = "error"
    payload: Dict[str, str]

class NotificationMessage(WebSocketMessage):
    type: Literal["notification"] = "notification"
    payload: Dict[str, str]