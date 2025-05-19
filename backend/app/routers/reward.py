from fastapi import APIRouter, HTTPException, Depends
from bson import ObjectId
from app.routers.auth import get_current_user
from app.db.database import db

router = APIRouter(prefix="/reward", tags=["reward"])

@router.post("/use", response_model=dict)
async def use_reward(
    game_id: str,
    reward_type: str,
    current_user: str = Depends(get_current_user)
):
    game = await db.games.find_one({"_id": ObjectId(game_id)})
    if not game:
        raise HTTPException(status_code=404, detail="Oyun bulunamadı.")
    if game["status"] != "active":
        raise HTTPException(status_code=400, detail="Oyun aktif değil.")
    if game["player1"] != current_user and game["player2"] != current_user:
        raise HTTPException(status_code=403, detail="Bu oyuna ait değilsiniz.")
    me = "player1" if game["player1"] == current_user else "player2"
    opp = "player2" if me == "player1" else "player1"
    if reward_type not in game.get("available_rewards", {}).get(me, []):
        raise HTTPException(status_code=400, detail="Ödül elinizde yok.")
    updates = {}
    if reward_type == "bolge_yasagi":
        updates["region_block"] = me == "player1" and "right" or "left"
    elif reward_type == "harf_yasagi":
        opp_hand = game["hands"][opp]
        frozen = game.get("frozen_letters", {}).get(opp, [])
        frozen.extend(opp_hand[:2])
        updates[f"frozen_letters.{opp}"] = frozen
    elif reward_type == "ekstra_hamle_jokeri":
        updates["extra_move_in_progress"] = True
    else:
        raise HTTPException(status_code=400, detail="Geçersiz reward.")

    rewards = game["available_rewards"][me]
    rewards.remove(reward_type)
    updates[f"available_rewards.{me}"] = rewards

    await db.games.update_one(
        {"_id": ObjectId(game_id)},
        {"$set": updates}
    )
    return {"message": f"'{reward_type}' kullanıldı.", "updates": updates}