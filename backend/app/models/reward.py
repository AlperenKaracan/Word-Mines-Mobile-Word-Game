from pydantic import BaseModel
class RewardUse(BaseModel):
    game_id: str
    reward_type: str
