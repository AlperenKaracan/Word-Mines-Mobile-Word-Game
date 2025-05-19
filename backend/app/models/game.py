from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime
import time

class GameCreate(BaseModel):
    player1_username: str
    player2_username: Optional[str] = None
    player1_key: str = "player1"
    player2_key: str = "player2"
    board: Dict[str, List[List[Dict[str, Any]]]] = Field(...)
    hands: Dict[str, List[str]] = Field(...)
    pool: List[str] = Field(...)

    status: str = "waiting"
    turn: Optional[str] = None
    turn_key: Optional[str] = None
    timeOption: str = "5m"
    internal_mines_on_board: Dict[str, str] = Field(default_factory=dict)
    internal_rewards_on_board: Dict[str, str] = Field(default_factory=dict)
    scores: Dict[str, int] = Field(default_factory=lambda: {"player1": 0, "player2": 0})
    allAvailableRewards: Dict[str, List[str]] = Field(
        default_factory=lambda: {"player1": [], "player2": []}
    )
    frozen_letters: Dict[str, List[str]] = Field(
        default_factory=lambda: {"player1": [], "player2": []}
    )
    consecutive_passes: int = 0
    extra_move_in_progress: bool = False
    region_block: Optional[str] = None
    winner: Optional[str] = None
    lastMoveTime: float = Field(default_factory=time.time)
    gameStartTime: datetime = Field(default_factory=datetime.utcnow)
    event_log: List[Dict[str, Any]] = Field(default_factory=list)

    class Config:
        pass
