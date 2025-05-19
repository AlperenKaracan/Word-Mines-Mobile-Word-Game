from fastapi import APIRouter, HTTPException, Depends, Path, Body
from pydantic import BaseModel, Field, ValidationError
from typing import List, Dict, Optional, Tuple, Any, Set
from bson import ObjectId
import time
import random
import logging
import math
from datetime import datetime, timedelta

from app.db.database import db
from app.models.game import GameCreate
from app.models.move import MoveRequest, MovePreviewRequest, MovePreviewResponse
from app.routers.auth import get_current_user
from app.core.websocket_manager import manager
from app.models.websocket_models import GameStateUpdateMessage
from .game_utils import (
    generate_letter_pool,
    deal_letters,
    assign_solid_bonuses,
    assign_mines_and_rewards,
    touches_existing_letter,
    calculate_word_score,
    find_all_formed_words,
    apply_mine_and_reward_effects,
    LETTER_DISTRIBUTION,
    LETTER_SCORES,
)
logger = logging.getLogger("game_router")
if not logger.hasHandlers():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger.info("game_router logger başlatıldı.")

router = APIRouter(prefix="/game", tags=["game"])
waiting_rooms: Dict[str, List[str]] = {}


def serialize_game_data(game_data: dict) -> dict:
    if not game_data:
        logger.warning("serialize_game_data'ya boş veri geldi.")
        return {}

    def convert_types(item):
        if isinstance(item, list): return [convert_types(i) for i in item]
        elif isinstance(item, dict):
             return {
                 str(k): convert_types(v) for k, v in item.items()
                 if not (isinstance(k, str) and k.startswith('internal_'))
             }
        elif isinstance(item, ObjectId): return str(item)
        elif isinstance(item, datetime): return item.isoformat()
        elif hasattr(item, 'model_dump'):
             try: return item.model_dump()
             except AttributeError:
                  try: return item.dict()
                  except AttributeError: return item
        return item

    serialized = {}
    is_finished = game_data.get("status", "").startswith("finished")

    for key, value in game_data.items():
        if key == "_id":
            serialized["game_id"] = str(value)
        elif key in ["internal_mines_on_board", "internal_rewards_on_board"]:
            continue
        elif key == "event_log" and not is_finished:
            continue
        else:
            serialized[key] = convert_types(value)

    serialized.setdefault('player1_username', None)
    serialized.setdefault('player2_username', None)

    p1_key = game_data.get('player1_key', 'player1')
    p2_key = game_data.get('player2_key', 'player2')

    scores_from_db = game_data.get("scores", {})
    serialized['scores'] = {
        p1_key: scores_from_db.get(p1_key, 0),
        p2_key: scores_from_db.get(p2_key, 0)
    }

    p1_user = serialized.get('player1_username')
    p2_user = serialized.get('player2_username')

    hands_from_db = game_data.get("hands", {})
    serialized['hands'] = {
        p1_user: hands_from_db.get(p1_user, []) if p1_user else [],
        p2_user: hands_from_db.get(p2_user, []) if p2_user else []
    } if p1_user and p2_user else {}

    rewards_from_db = game_data.get("allAvailableRewards", {})
    serialized['allAvailableRewards'] = {
         p1_key: rewards_from_db.get(p1_key, []),
         p2_key: rewards_from_db.get(p2_key, [])
    }
    if 'available_rewards' in serialized:
        del serialized['available_rewards']

    frozen_from_db = game_data.get("frozen_letters", {})
    serialized['frozen_letters'] = {
         p1_user: frozen_from_db.get(p1_user, []) if p1_user else [],
         p2_user: frozen_from_db.get(p2_user, []) if p2_user else []
    } if p1_user and p2_user else {}

    serialized.setdefault('pool', [])
    serialized.setdefault('status', 'unknown')
    serialized.setdefault('turn', None)
    serialized.pop('time_left', None)
    serialized.setdefault('extra_move_in_progress', False)
    serialized.setdefault('region_block', None)
    serialized.setdefault('winner', None)
    serialized.setdefault('timeOption', '0')
    serialized.setdefault('lastMoveTime', None)
    serialized.setdefault('gameStartTime', None)
    serialized.setdefault('turn_key', None)
    serialized.setdefault('player1_key', p1_key)
    serialized.setdefault('player2_key', p2_key)

    board_data = serialized.get('board')
    if isinstance(board_data, dict) and 'grid' in board_data:
        pass
    elif isinstance(board_data, list):
       serialized['board'] = {'grid': board_data}
    else:
        serialized['board'] = {'grid': [[{"letter": None, "special": None, "original_tile": None} for _ in range(15)] for _ in range(15)]}
        logger.warning(f"Oyun {serialized.get('game_id')} için DB'de geçerli tahta bulunamadı, boş tahta oluşturuldu.")

    if not is_finished:
        serialized.pop('event_log', None)
    else:
         serialized.setdefault('event_log', [])

    return serialized

async def create_matched_game(player1_username: str, player2_username: str, time_option_str: str) -> Optional[Dict]:
    try:
        if time_option_str not in ["2m", "5m", "12h", "24h"]:
             logger.warning(f"Geçersiz zaman seçeneği '{time_option_str}', '5m' olarak ayarlandı.")
             time_option_str = "5m"

        pool = generate_letter_pool()
        hand1 = deal_letters(pool, 7)
        hand2 = deal_letters(pool, 7)

        board_grid = [[{"letter": None, "special": None, "original_tile": None} for _ in range(15)] for _ in range(15)]
        assign_solid_bonuses(board_grid)
        mines_map, rewards_map = assign_mines_and_rewards(board_grid)
        board_dict = {"grid": board_grid}

        turn_player_key = random.choice(['player1', 'player2'])
        turn_player_username = player1_username if turn_player_key == 'player1' else player2_username

        game_data = GameCreate(
            player1_username=player1_username,
            player2_username=player2_username,
            board=board_dict,
            hands={player1_username: hand1, player2_username: hand2},
            pool=pool,
            status="active",
            turn=turn_player_username,
            turn_key=turn_player_key,
            player1_key="player1",
            player2_key="player2",
            timeOption=time_option_str,
            scores={"player1": 0, "player2": 0},
            consecutive_passes=0,
            gameStartTime=datetime.utcnow(),
            lastMoveTime=time.time(),
            internal_mines_on_board=mines_map,
            internal_rewards_on_board=rewards_map,
            allAvailableRewards={"player1": [], "player2": []},
            frozen_letters={player1_username: [], player2_username: []},
            event_log=[]
        )
        game_dict_to_insert = game_data.model_dump(by_alias=True, exclude_none=True)

        created_game_result = await db.games.insert_one(game_dict_to_insert)
        logger.info(f"Yeni oyun oluşturuldu: ID {created_game_result.inserted_id}, Oyuncular: {player1_username} vs {player2_username}")
        return await db.games.find_one({"_id": created_game_result.inserted_id})

    except Exception as e:
        logger.error(f"Oyun oluşturulurken hata: {e}", exc_info=True)
        return None

def get_player_keys(game: Dict, current_username: str) -> Tuple[Optional[str], Optional[str]]:
    p1_user = game.get("player1_username")
    p2_user = game.get("player2_username")
    p1_key = game.get("player1_key", "player1")
    p2_key = game.get("player2_key", "player2")

    if current_username == p1_user:
        return p1_key, p2_key
    elif current_username == p2_user:
        return p2_key, p1_key
    else:
        logger.warning(f"get_player_keys: Kullanıcı '{current_username}' oyunun parçası değil ({p1_user} vs {p2_user})")
        return None, None

def determine_winner_by_score(game: dict, scores_to_use: Optional[Dict] = None) -> Optional[str]:
    scores = scores_to_use if scores_to_use is not None else game.get("scores", {})
    p1_key = game.get("player1_key", "player1")
    p2_key = game.get("player2_key", "player2")
    p1s = scores.get(p1_key, 0)
    p2s = scores.get(p2_key, 0)
    if p1s > p2s: return p1_key
    if p2s > p1s: return p2_key
    return None

async def finish_game(game_id_obj: ObjectId, winner_player_key: Optional[str], status: str = "finished") -> Optional[Dict]:
    game = await db.games.find_one({"_id": game_id_obj})

    if not game or game.get("status", "").startswith("finished"):
        return game

    logger.info(f"Oyun bitiriliyor: ID {game_id_obj}, Durum: {status}, Belirlenen Kazanan Anahtar: {winner_player_key}")

    updates = {"status": status}
    final_scores = game.get("scores", {}).copy()
    p1_key = game.get("player1_key", "player1")
    p2_key = game.get("player2_key", "player2")
    p1_user = game.get("player1_username")
    p2_user = game.get("player2_username")

    winner_username = None

    if winner_player_key:
        winner_username = p1_user if winner_player_key == p1_key else p2_user
        updates["winner"] = winner_username if winner_username else winner_player_key
    else:
         winner_by_score_key = determine_winner_by_score(game, final_scores)
         if winner_by_score_key:
              winner_player_key = winner_by_score_key
              winner_username = p1_user if winner_player_key == p1_key else p2_user
              updates["winner"] = winner_username if winner_username else winner_player_key


    if status == "finished_hand" and winner_player_key:
        loser_player_key = p2_key if winner_player_key == p1_key else p1_key
        winner_username_for_hand = p1_user if winner_player_key == p1_key else p2_user
        loser_username = p1_user if loser_player_key == p1_key else p2_user

        loser_hand = game.get("hands", {}).get(loser_username, [])

        if loser_hand:
            remaining_points = sum(LETTER_SCORES.get(letter.upper(), 0) for letter in loser_hand)
            if remaining_points > 0:
                logger.info(f"Harf bitirme bonusu: {winner_username_for_hand} +{remaining_points}, {loser_username} -{remaining_points}")
                final_scores[winner_player_key] = final_scores.get(winner_player_key, 0) + remaining_points
                final_scores[loser_player_key] = final_scores.get(loser_player_key, 0) - remaining_points
                if final_scores[loser_player_key] < 0: final_scores[loser_player_key] = 0
                updates["scores"] = final_scores
                winner_by_final_score_key = determine_winner_by_score(game, final_scores)
                if winner_by_final_score_key:
                     winner_player_key = winner_by_final_score_key
                     winner_username = p1_user if winner_player_key == p1_key else p2_user
                     updates["winner"] = winner_username if winner_username else winner_player_key
                else:
                     updates["winner"] = None
                     winner_username = None

    if "winner" not in updates:
         winner_by_score_key = determine_winner_by_score(game, final_scores)
         if winner_by_score_key:
              winner_player_key = winner_by_score_key
              winner_username = p1_user if winner_player_key == p1_key else p2_user
              updates["winner"] = winner_username if winner_username else winner_player_key


    await db.games.update_one({"_id": game_id_obj}, {"$set": updates})
    logger.info(f"Oyun DB'de güncellendi: ID {game_id_obj}, Yeni Durum: {updates.get('status')}, Kazanan: {updates.get('winner')}")

    if p1_user and p2_user and p1_user != "Bot" and p2_user != "Bot":
        try:
            final_winner_username_for_stats = updates.get("winner")

            p1_stats_update = {"$inc": {"total_games": 1}}
            if final_winner_username_for_stats == p1_user:
                 p1_stats_update["$inc"]["wins"] = 1
            await db.users.update_one({"username": p1_user}, p1_stats_update)

            p2_stats_update = {"$inc": {"total_games": 1}}
            if final_winner_username_for_stats == p2_user:
                 p2_stats_update["$inc"]["wins"] = 1
            await db.users.update_one({"username": p2_user}, p2_stats_update)

            logger.info(f"Oyuncu istatistikleri güncellendi: {p1_user}, {p2_user}")
        except Exception as e:
            logger.error(f"Oyuncu istatistikleri güncellenirken hata: {e}", exc_info=True)

    return await db.games.find_one({"_id": game_id_obj})

class QueueBody(BaseModel):
    time_option: str = Field(..., description="Seçilen süre: 2m | 5m | 12h | 24h")
    demo: Optional[bool] = Field(False, description="Demo modu: tek kullanıcı")

@router.post("/queue", response_model=dict)
async def enter_queue(
    body: QueueBody,
    current_user: str = Depends(get_current_user)
):
    valid_options = {"2m", "5m", "12h", "24h"}
    if body.time_option not in valid_options:
        raise HTTPException(status_code=400, detail=f"Geçersiz süre seçeneği. Geçerli seçenekler: {', '.join(valid_options)}")

    if body.demo:
        try:
            game_doc = await create_matched_game(current_user, "Bot", body.time_option)
            if game_doc:
                serialized_game = serialize_game_data(game_doc)
                logger.info(f"Demo oyun oluşturuldu: {current_user} vs Bot, ID: {serialized_game.get('game_id')}")
                return {"message": "Demo oyun oluşturuldu!", "game_id": serialized_game.get("game_id"), "game_state": serialized_game}
            else:
                raise HTTPException(status_code=500, detail="Demo oyun oluşturulamadı (create_matched_game None döndü).")
        except Exception as e:
            logger.error(f"Demo oyun oluşturma hatası: {e}", exc_info=True)
            if isinstance(e, HTTPException): raise e
            raise HTTPException(status_code=500, detail=f"Demo oyun oluşturulamadı: {e}")

    else:
        opt_key = body.time_option

        current_waiting_rooms = waiting_rooms.copy()
        for key, users in current_waiting_rooms.items():
            if current_user in users:
                if key == opt_key:
                    logger.debug(f"{current_user} zaten {opt_key} odasında bekliyor.")
                    return {"message": "Zaten bu sürede bir rakip bekliyorsunuz.", "game_id": None}
                else:
                    logger.warning(f"{current_user} zaten {key} odasında bekliyor, {opt_key} sırasına giremez.")
                    raise HTTPException(status_code=400, detail=f"Zaten {key} süreli başka bir odada bekliyorsunuz. Önce oradan çıkmalısınız.")

        room_users = waiting_rooms.setdefault(opt_key, [])

        if not room_users:
            room_users.append(current_user)
            logger.info(f"{current_user} sıraya girdi: {opt_key}")
            return {"message": f"{opt_key} süreyle sıraya girdiniz, rakip bekleniyor.", "game_id": None}
        else:
            opponent = None
            try:
                opponent = room_users.pop(0)
                if opponent == current_user:
                     room_users.append(current_user)
                     logger.warning(f"Sıradaki rakip kendisi çıktı? {current_user} - {opt_key}")
                     return {"message": "Rakip bulunamadı, tekrar sıraya eklendiniz.", "game_id": None}

                logger.info(f"Rakip bulundu: {current_user} vs {opponent} ({opt_key})")
            except IndexError:
                 logger.warning(f"Oda boşaldı, {current_user} sıraya ekleniyor: {opt_key}")
                 room_users.append(current_user)
                 return {"message": f"{opt_key} süreyle sıraya girdiniz, rakip bekleniyor.", "game_id": None}

            if not room_users and opt_key in waiting_rooms:
                try: del waiting_rooms[opt_key]
                except KeyError: pass

            try:
                game_doc = await create_matched_game(current_user, opponent, body.time_option)

                if game_doc:
                    serialized_game = serialize_game_data(game_doc)
                    game_id_str = serialized_game.get("game_id")
                    logger.info(f"Eşleşme başarılı, oyun oluşturuldu: ID {game_id_str}")

                    if game_id_str:
                        notification_msg = f"Rakip bulundu: {current_user} vs {opponent}. Oyun başlıyor!"
                        await manager.broadcast_notification(game_id_str, notification_msg)
                        logger.info(f"Oyun başlangıç bildirimi gönderildi: Oda {game_id_str}")
                    else:
                        logger.error("Oyun ID'si alınamadı, bildirim gönderilemiyor.")

                    return {"message": "Oyun bulundu!", "game_id": game_id_str, "game_state": serialized_game}
                else:
                    logger.error("Eşleşme bulundu ancak oyun oluşturulamadı (create_matched_game None döndü).")
                    waiting_rooms.setdefault(opt_key, []).insert(0, opponent)
                    if current_user not in waiting_rooms.get(opt_key, []):
                         waiting_rooms.setdefault(opt_key, []).append(current_user)
                    raise HTTPException(status_code=500, detail="Eşleşme bulundu ancak oyun oluşturulamadı.")
            except Exception as e:
                 logger.error(f"Eşleşme sonrası oyun oluşturma hatası: {e}", exc_info=True)
                 waiting_rooms.setdefault(opt_key, []).insert(0, opponent)
                 if current_user not in waiting_rooms.get(opt_key, []):
                      waiting_rooms.setdefault(opt_key, []).append(current_user)
                 if isinstance(e, HTTPException): raise e
                 raise HTTPException(status_code=500, detail=f"Oyun oluşturulurken hata: {e}")

@router.post(
    "/{game_id}/preview_move",
    response_model=MovePreviewResponse,
    summary="Hamle Önizleme",
    description="Kullanıcının tahtaya geçici olarak yerleştirdiği harflerin geçerliliğini ve potansiyel skorunu kontrol eder."
)
async def preview_move(
    game_id: str = Path(..., description="Oyun ID'si"),
    preview_request: MovePreviewRequest = Body(...),
    current_user: str = Depends(get_current_user)
):
    start_time = time.time()
    logger.debug(f"Hamle önizleme isteği: Oyun {game_id}, Kullanıcı {current_user}")

    game_id_obj: Optional[ObjectId] = None
    game_id_str: Optional[str] = None

    try:
        game_id_obj = ObjectId(game_id)
        game_id_str = str(game_id_obj)
    except Exception:
        logger.warning(f"Geçersiz oyun ID formatı (önizleme): {game_id}")
        raise HTTPException(status_code=400, detail="Geçersiz oyun ID formatı.")

    try:
        game = await db.games.find_one({"_id": game_id_obj})
        if not game:
            logger.warning(f"Oyun bulunamadı (önizleme): {game_id_str}")
            raise HTTPException(status_code=404, detail="Oyun bulunamadı.")

        if not game.get("status", "").startswith("active"):
            return MovePreviewResponse(is_valid=False, potential_score=0, message="Oyun aktif değil.")

        current_player_key, opponent_key = get_player_keys(game, current_user)
        if not current_player_key:
            logger.warning(f"Yetkisiz önizleme denemesi: Oyun {game_id_str}, Kullanıcı {current_user}")
            raise HTTPException(status_code=403, detail="Bu oyuna ait değilsiniz.")

        if not preview_request.positions or not preview_request.used_letters or len(preview_request.positions) != len(preview_request.used_letters):
            return MovePreviewResponse(is_valid=False, potential_score=0, message="Pozisyon ve harf listeleri boş veya uzunlukları eşleşmiyor.")

        current_board_grid = game.get("board", {}).get("grid", [])
        if not current_board_grid:
             return MovePreviewResponse(is_valid=False, potential_score=0, message="Oyun tahtası yüklenemedi.")

        temp_board = [[cell.copy() for cell in row] for row in current_board_grid]
        placed_coords_set: Set[Tuple[int, int]] = set()
        joker_assignments = preview_request.joker_assignments or {}

        for i, pos in enumerate(preview_request.positions):
            try:
                r, c = pos
                if not (0 <= r < 15 and 0 <= c < 15):
                     return MovePreviewResponse(is_valid=False, potential_score=0, message=f"Pozisyon tahta dışında: [{r},{c}]")
                if temp_board[r][c].get("letter") is not None:
                     return MovePreviewResponse(is_valid=False, potential_score=0, message=f"Dolu kare: [{r},{c}]")

                is_player1 = current_player_key == game.get("player1_key", "player1")
                current_region_block = game.get("region_block")
                is_blocked = False
                if current_region_block == "right" and not is_player1 and c >= 7: is_blocked = True
                if current_region_block == "left" and is_player1 and c < 7: is_blocked = True
                if is_blocked:
                    return MovePreviewResponse(is_valid=False, potential_score=0, message=f"Yasaklı bölgeye harf konulamaz: [{r},{c}]")

                coord_str = f"{r},{c}"
                original_tile = preview_request.used_letters[i].upper()
                is_joker = original_tile == "JOKER"
                assigned_letter = original_tile

                if is_joker:
                    assigned_char = joker_assignments.get(coord_str)
                    if not assigned_char:
                        return MovePreviewResponse(is_valid=False, potential_score=0, message=f"Joker [{r},{c}] için harf atanmamış.")
                    assigned_letter = assigned_char.upper()
                    if len(assigned_letter) != 1 or assigned_letter not in LETTER_SCORES or assigned_letter == "JOKER":
                         return MovePreviewResponse(is_valid=False, potential_score=0, message=f"Joker için geçersiz harf ataması: '{assigned_letter}' [{r},{c}]")

                temp_board[r][c]["letter"] = assigned_letter
                temp_board[r][c]["original_tile"] = original_tile
                placed_coords_set.add((r, c))

            except (ValueError, TypeError, IndexError) as e:
                 logger.warning(f"Preview - Pozisyon/Harf işleme hatası: Oyun {game_id_str}, Hata: {e} - Pos: {pos}")
                 return MovePreviewResponse(is_valid=False, potential_score=0, message=f"Geçersiz pozisyon veya harf formatı: {pos}")

        is_first_move_in_preview = not any(cell.get("letter") for row in current_board_grid for cell in row if cell and cell.get("letter"))
        if not is_first_move_in_preview:
            if not touches_existing_letter(current_board_grid, preview_request.positions, is_first_move_in_preview):
                 return MovePreviewResponse(is_valid=False, potential_score=0, message="Harfler mevcut harflere bitişik olmalı.")
        else:
            if (7, 7) not in placed_coords_set:
                return MovePreviewResponse(is_valid=False, potential_score=0, message="İlk hamle merkez kareyi (H8) içermelidir.")

        try:
            formed_words_details, are_all_valid, invalid_words_list = find_all_formed_words(
                temp_board,
                preview_request.positions
            )
        except Exception as e:
            logger.error(f"Preview - find_all_formed_words hatası: Oyun {game_id_str}, Hata: {e}", exc_info=True)
            return MovePreviewResponse(is_valid=False, potential_score=0, message="Kelime bulma sırasında hata.")

        if not are_all_valid:
            error_msg = f"Geçersiz kelime(ler): {', '.join(invalid_words_list)}" if invalid_words_list else "Geçersiz hamle."
            if invalid_words_list and isinstance(invalid_words_list[0], str) and len(invalid_words_list) == 1 and not formed_words_details:
                 error_msg = invalid_words_list[0]

            return MovePreviewResponse(
                is_valid=False,
                potential_score=0,
                message=error_msg,
                invalid_words=invalid_words_list
            )

        if not formed_words_details and len(preview_request.positions) == 1 and is_first_move_in_preview:
             return MovePreviewResponse( is_valid=True, potential_score=0, message="İlk hamle (tek harf) geçerli." )

        total_score = 0
        if formed_words_details:
             for word_detail in formed_words_details:
                 try:
                      word_score = calculate_word_score(
                          temp_board,
                          word_detail["tiles"],
                          placed_coords_set
                      )
                      total_score += word_score
                 except Exception as calc_e:
                      logger.error(f"Preview - Skor hesaplama hatası: Oyun {game_id_str}, Hata: {calc_e}", exc_info=True)
                      return MovePreviewResponse(is_valid=False, potential_score=0, message=f"Skor hesaplanırken hata: {calc_e}")

        preview_time = time.time() - start_time
        logger.debug(f"Hamle önizleme başarılı: Oyun {game_id_str}, Kullanıcı {current_user}, Skor {total_score}, Süre {preview_time:.4f}s")
        return MovePreviewResponse( is_valid=True, potential_score=total_score, message="Yerleştirme geçerli." )

    except Exception as e:
        log_game_id = game_id_str if game_id_str else game_id
        logger.exception(f"Önizleme sırasında beklenmedik hata: Oyun {log_game_id}, Hata: {e}")
        return MovePreviewResponse(is_valid=False, potential_score=0, message=f"Önizleme sırasında sunucu hatası: {e}")

@router.post("/move/{game_id}", response_model=dict)
async def make_move(
    game_id: str,
    move: MoveRequest,
    current_user: str = Depends(get_current_user)
):
    start_time = time.time()
    logger.info(f"Hamle isteği: Oyun {game_id}, Kullanıcı {current_user}, Tip: {move.move_type if not move.pass_move else 'pass'}")

    game_id_obj: Optional[ObjectId] = None
    game_id_str: Optional[str] = None

    try:
        game_id_obj = ObjectId(game_id)
        game_id_str = str(game_id_obj)
    except Exception:
        logger.warning(f"Geçersiz oyun ID formatı: {game_id}")
        raise HTTPException(status_code=400, detail="Geçersiz oyun ID formatı.")

    try:
        game = await db.games.find_one({"_id": game_id_obj})
        if not game:
             logger.warning(f"Oyun bulunamadı: ID {game_id_str}")
             raise HTTPException(status_code=404, detail="Oyun bulunamadı.")

        current_status = game.get("status", "unknown")
        if not current_status.startswith("active"):
            detail_msg = f"Oyun aktif değil (Durum: {current_status}). Hamle yapılamaz."
            logger.warning(f"Geçersiz hamle (oyun aktif değil): Oyun {game_id_str}, Durum {current_status}")
            if current_status.startswith("finished"):
                 return {"message": detail_msg, "game_state": serialize_game_data(game)}
            raise HTTPException(status_code=400, detail=detail_msg)

        current_player_key, opponent_key = get_player_keys(game, current_user)
        if not current_player_key:
            logger.warning(f"Yetkisiz hamle denemesi: Oyun {game_id_str}, Kullanıcı {current_user}")
            raise HTTPException(status_code=403, detail="Bu oyuna ait değilsiniz.")

        if game.get("turn") != current_user:
            logger.warning(f"Sıra dışı hamle denemesi: Oyun {game_id_str}, Kullanıcı {current_user}, Sıra: {game.get('turn')}")
            raise HTTPException(status_code=400, detail=f"Sıra sizde değil (Sıra: {game.get('turn')}).")

        current_board_grid = game.get("board", {}).get("grid", [])

        last_move_time_float = game.get("lastMoveTime")
        current_time_float = time.time()
        time_limit_seconds = 300

        is_first_move_check = not any(cell.get("letter") for row in current_board_grid for cell in row if cell and cell.get("letter"))

        if is_first_move_check:
            logger.debug(f"Oyun {game_id_str}: İlk hamle için süre kontrolü (1 saat).")
            time_limit_seconds = 3600
        else:
            logger.debug(f"Oyun {game_id_str}: Sonraki hamleler için süre kontrolü.")
            time_option_str = game.get("timeOption", "5m")
            if time_option_str:
                time_option_str = time_option_str.lower()
                numeric_part = "".join(filter(str.isdigit, time_option_str))
                unit = "".join(filter(str.isalpha, time_option_str))
                try:
                    value = int(numeric_part) if numeric_part else 0
                    if unit == 'm': time_limit_seconds = value * 60
                    elif unit == 'h': time_limit_seconds = value * 3600
                    else:
                        logger.warning(f"Oyun {game_id_str}: Geçersiz zaman birimi '{unit}', 5dk varsayıldı.")
                        time_limit_seconds = 300
                except ValueError:
                    logger.warning(f"Oyun {game_id_str}: Geçersiz zaman değeri '{numeric_part}', 5dk varsayıldı.")
                    time_limit_seconds = 300
            else:
                 logger.warning(f"Oyun {game_id_str}: timeOption tanımsız, 5dk varsayıldı.")
                 time_limit_seconds = 300

            if time_limit_seconds <= 0:
                logger.warning(f"Oyun {game_id_str}: Hesaplanan süre limiti <= 0 ({time_limit_seconds}), 5dk varsayıldı.")
                time_limit_seconds = 300

        time_elapsed = current_time_float - last_move_time_float if last_move_time_float else 0
        logger.debug(f"Oyun {game_id_str}: Zaman kontrolü - Geçen: {time_elapsed:.2f}s, Limit: {time_limit_seconds}s")
        if last_move_time_float and (time_elapsed >= time_limit_seconds):
            logger.info(f"Süre doldu: Oyun {game_id_str}, Kullanıcı {current_user}, Limit: {time_limit_seconds}s, Geçen: {time_elapsed:.2f}s")
            finished_game = await finish_game(game_id_obj, opponent_key, status="finished_timeout")
            if finished_game:
                 serialized_game = serialize_game_data(finished_game)
                 await manager.broadcast(game_id_str, GameStateUpdateMessage(payload=serialized_game))
                 winner_username = finished_game.get("winner", opponent_key)
                 await manager.broadcast_notification(game_id_str, f"⏳ {current_user}'nin süresi doldu! Kazanan: {winner_username}")
                 return {"message": "Hamle süreniz doldu!", "game_state": serialized_game}
            else:
                 logger.error(f"Süre doldu ama oyun bitirilemedi: Oyun {game_id_str}")
                 raise HTTPException(status_code=500, detail="Süre doldu ancak oyun durumu güncellenemedi.")

        opponent_username = game.get("player1_username") if opponent_key == game.get("player1_key") else game.get("player2_username")
        current_hands = game.get("hands", {})
        my_hand = current_hands.get(current_user, [])
        current_pool = game.get("pool", [])
        current_passes = game.get("consecutive_passes", 0)
        my_frozen_letters = game.get("frozen_letters", {}).get(current_user, [])
        current_region_block = game.get("region_block")
        is_extra_move_active = game.get("extra_move_in_progress", False)

        db_updates: Dict[str, Any] = {}
        db_push_ops: Dict[str, Any] = {}
        notifications: List[str] = []
        new_game_status: str = "active"
        winner_player_key_on_finish: Optional[str] = None
        mine_reward_result: Dict = {}
        triggered_cells_list: List[Dict[str, Any]] = []

        if move.pass_move:
            current_passes += 1
            notifications.append(f"➡️ {current_user} pas geçti.")
            db_updates["consecutive_passes"] = current_passes
            db_updates["extra_move_in_progress"] = False
            event_log_entry = {"type": "pass", "player": current_user, "timestamp": time.time()}
            db_push_ops["event_log"] = event_log_entry

            if current_passes >= 2:
                logger.info(f"Oyun paslaşma ile bitti: Oyun {game_id_str}")
                new_game_status = "finished_pass"
                winner_player_key_on_finish = determine_winner_by_score(game)

        elif move.move_type == "shift_letter":
            if not move.positions or len(move.positions) != 2:
                raise HTTPException(status_code=400, detail="Kaydırma için 2 pozisyon (kaynak, hedef) gereklidir.")
            try:
                from_r, from_c = move.positions[0]
                to_r, to_c = move.positions[1]
                if not (0 <= from_r < 15 and 0 <= from_c < 15 and 0 <= to_r < 15 and 0 <= to_c < 15):
                    raise HTTPException(status_code=400, detail="Kaydırma pozisyonları tahta dışında.")
                original_cell = current_board_grid[from_r][from_c]
                letter_to_move = original_cell.get("letter")
                if letter_to_move is None:
                    raise HTTPException(status_code=400, detail=f"Başlangıç karesi [{from_r},{from_c}] boş.")
                if current_board_grid[to_r][to_c].get("letter") is not None:
                    raise HTTPException(status_code=400, detail=f"Hedef kare [{to_r},{to_c}] dolu.")
            except (ValueError, TypeError, IndexError) as e:
                 raise HTTPException(status_code=400, detail=f"Geçersiz kaydırma pozisyon formatı: {e}")

            row_diff = abs(from_r - to_r); col_diff = abs(from_c - to_c)
            is_adjacent = (row_diff <= 1 and col_diff <= 1) and (row_diff + col_diff > 0)
            if not is_adjacent:
                raise HTTPException(status_code=400, detail="Harfler sadece 1 birim uzağa kaydırılabilir.")

            is_player1 = current_player_key == game.get("player1_key", "player1")
            is_blocked = False
            if current_region_block == "right" and not is_player1 and to_c >= 7: is_blocked = True
            if current_region_block == "left" and is_player1 and to_c < 7: is_blocked = True
            if is_blocked:
                raise HTTPException(status_code=400, detail=f"Yasaklı bölgeye harf kaydırılamaz: [{to_r},{to_c}]")

            temp_board = [[cell.copy() for cell in row] for row in current_board_grid]
            temp_board[to_r][to_c] = {
                "letter": letter_to_move,
                "original_tile": original_cell.get("original_tile", letter_to_move),
                "special": temp_board[to_r][to_c].get("special")
            }
            temp_board[from_r][from_c] = {
                "letter": None,
                "original_tile": None,
                "special": original_cell.get("special")
            }

            db_updates["board.grid"] = temp_board
            db_updates["consecutive_passes"] = 0
            db_updates["extra_move_in_progress"] = False
            event_log_entry = { "type": "shift", "player": current_user, "from": [from_r, from_c], "to": [to_r, to_c], "timestamp": time.time() }
            db_push_ops["event_log"] = event_log_entry
            notifications.append(f"↔️ {current_user} harf kaydırdı: [{from_r},{from_c}] -> [{to_r},{to_c}]")

        elif move.move_type == "place_word":
            if not move.positions or not move.used_letters or len(move.positions) != len(move.used_letters):
                raise HTTPException(status_code=400, detail="Pozisyon ve harf listeleri boş veya uzunlukları eşleşmiyor.")

            temp_hand = my_hand[:]
            placed_letters_count = {}
            for letter in move.used_letters: placed_letters_count[letter.upper()] = placed_letters_count.get(letter.upper(), 0) + 1
            hand_letter_count = {}
            for letter in my_hand: hand_letter_count[letter.upper()] = hand_letter_count.get(letter.upper(), 0) + 1
            for letter, count in placed_letters_count.items():
                if hand_letter_count.get(letter, 0) < count:
                    raise HTTPException(status_code=400, detail=f"Elinde yeterli '{letter}' harfi yok.")
                for _ in range(count):
                     try:
                         found_letter = next(h for h in temp_hand if h.upper() == letter)
                         temp_hand.remove(found_letter)
                     except StopIteration:
                         logger.error(f"Harf çıkarma hatası: Oyun {game_id_str}, El={my_hand}, İstenen={letter}, Geçici El={temp_hand}")
                         raise HTTPException(status_code=500, detail=f"'{letter}' harfi elden çıkarılırken hata oluştu.")
            for letter in move.used_letters:
                 if letter.upper() in my_frozen_letters:
                     raise HTTPException(status_code=400, detail=f"Donmuş harf ({letter}) kullanılamaz.")

            temp_board = [[cell.copy() for cell in row] for row in current_board_grid]
            placed_tile_details: List[Dict] = []
            placed_coords_set: Set[Tuple[int, int]] = set()
            joker_assignments = move.joker_assignments or {}
            for i, pos in enumerate(move.positions):
                try:
                    r, c = pos
                    if not (0 <= r < 15 and 0 <= c < 15): raise HTTPException(status_code=400, detail=f"Pozisyon tahta dışında: [{r},{c}]")
                    if temp_board[r][c].get("letter") is not None: raise HTTPException(status_code=400, detail=f"Dolu kare: [{r},{c}]")
                    is_player1 = current_player_key == game.get("player1_key", "player1")
                    is_blocked = False
                    if current_region_block == "right" and not is_player1 and c >= 7: is_blocked = True
                    if current_region_block == "left" and is_player1 and c < 7: is_blocked = True
                    if is_blocked: raise HTTPException(status_code=400, detail=f"Yasaklı bölgeye harf konulamaz: [{r},{c}]")
                    coord_str = f"{r},{c}"
                    original_tile = move.used_letters[i].upper()
                    is_joker = original_tile == "JOKER"
                    assigned_letter = original_tile
                    if is_joker:
                        assigned_char = joker_assignments.get(coord_str)
                        if not assigned_char: raise HTTPException(status_code=400, detail=f"Joker [{r},{c}] için harf atanmamış.")
                        assigned_letter = assigned_char.upper()
                        if len(assigned_letter) != 1 or assigned_letter not in LETTER_SCORES or assigned_letter == "JOKER":
                            raise HTTPException(status_code=400, detail=f"Joker için geçersiz harf ataması: '{assigned_letter}' [{r},{c}]")
                    temp_board[r][c]["letter"] = assigned_letter
                    temp_board[r][c]["original_tile"] = original_tile
                    placed_coords_set.add((r, c))
                    placed_tile_details.append({"letter": assigned_letter, "original_tile": original_tile, "row": r, "col": c, "is_joker": is_joker})
                except (ValueError, TypeError, IndexError) as e:
                     logger.warning(f"Move - Pozisyon/Harf işleme hatası: Oyun {game_id_str}, Hata: {e} - Pos: {pos}")
                     raise HTTPException(status_code=400, detail=f"Geçersiz pozisyon veya harf formatı: {pos}")

            if not is_first_move_check:
                if not touches_existing_letter(current_board_grid, move.positions, is_first_move_check):
                    raise HTTPException(status_code=400, detail="Harfler mevcut harflere bitişik olmalı.")
            else:
                if (7, 7) not in placed_coords_set:
                     raise HTTPException(status_code=400, detail="İlk hamle merkez kareyi (H8) içermelidir.")

            try:
                formed_words_details, are_all_valid, invalid_words_found = find_all_formed_words(
                    temp_board,
                    move.positions
                )
            except Exception as e:
                 logger.error(f"Move - find_all_formed_words hatası: Oyun {game_id_str}, Hata: {e}", exc_info=True)
                 raise HTTPException(status_code=500, detail="Kelime bulma sırasında beklenmedik bir hata oluştu.")

            if not are_all_valid:
                error_message = f"Geçersiz kelime(ler): {', '.join(invalid_words_found)}" if invalid_words_found else "Geçersiz hamle yapısı."
                if invalid_words_found and isinstance(invalid_words_found[0], str) and len(invalid_words_found) == 1 and not formed_words_details:
                     error_message = invalid_words_found[0]
                logger.warning(f"Geçersiz hamle: Oyun {game_id_str}, Kullanıcı {current_user}, Mesaj: {error_message}")
                raise HTTPException(status_code=400, detail=error_message)

            total_score_gain = 0
            valid_words_formed_str_list = []
            formed_word_strings_list = []

            if not formed_words_details:
                 if len(move.positions) == 1 and is_first_move_check:
                     total_score_gain = 0
                     notifications.append(f"📝 {current_user} ilk hamlesini yaptı (tek harf).")
                 else:
                      logger.error(f"Beklenmedik durum: Kelime yok ama `are_all_valid` True? Oyun {game_id_str}")
                      raise HTTPException(status_code=500, detail="Kelime doğrulama sırasında tutarsızlık.")
            else:
                for word_detail in formed_words_details:
                    word_str = word_detail["word"]
                    formed_word_strings_list.append(word_str)
                    try:
                        word_score = calculate_word_score(
                            temp_board,
                            word_detail["tiles"],
                            placed_coords_set
                        )
                        total_score_gain += word_score
                        valid_words_formed_str_list.append(f"'{word_str}' ({word_score}p)")
                    except Exception as calc_e:
                         logger.error(f"Skor hesaplama hatası: Oyun {game_id_str}, Kelime {word_str}, Hata: {calc_e}", exc_info=True)
                         raise HTTPException(status_code=500, detail=f"'{word_str}' skoru hesaplanırken hata oluştu.")

                if len(move.positions) == 7:
                    total_score_gain += 50
                    notifications.append(f"✨ {current_user} Bingo yaptı! (+50 puan)")

                if valid_words_formed_str_list:
                     notifications.append(f"📝 {current_user} kelime(ler) oluşturdu: {', '.join(valid_words_formed_str_list)}")

            place_word_event = {
                "type": "place_word",
                "player": current_user,
                "tiles": [{"letter": t["original_tile"], "assigned": t["letter"] if t["is_joker"] else None, "pos": [t["row"], t["col"]]} for t in placed_tile_details],
                "formed_words": formed_word_strings_list,
                "score_before_mines": total_score_gain,
                "timestamp": start_time
            }

            try:
                mine_reward_result = apply_mine_and_reward_effects(
                    game_data=game,
                    placed_tiles_info=placed_tile_details,
                    score_gain=total_score_gain,
                    player_key=current_player_key,
                    opponent_key=opponent_key
                )
            except Exception as effect_e:
                 logger.error(f"Mayın/Ödül etkisi uygulama hatası: Oyun {game_id_str}, Hata: {effect_e}", exc_info=True)
                 raise HTTPException(status_code=500, detail="Mayın veya ödül etkileri uygulanırken hata oluştu.")

            final_score_gain = mine_reward_result.get("final_score", 0)
            place_word_event["score_after_mines"] = final_score_gain
            db_updates.update(mine_reward_result.get("updates", {}))
            notifications.extend(mine_reward_result.get("notifications", []))
            cancel_word = mine_reward_result.get("cancel_word", False)
            lose_letters = mine_reward_result.get("lose_letters", False)

            triggered_events = mine_reward_result.get("triggered_events", [])
            all_events_for_move = [place_word_event] + triggered_events
            db_push_ops["event_log"] = {"$each": all_events_for_move}

            for event in triggered_events:
                event_pos = event.get("pos")
                if event_pos and isinstance(event_pos, list) and len(event_pos) == 2:
                    row, col = event_pos
                    event_type = event.get("type")
                    if event_type == "mine_triggered":
                        triggered_cells_list.append({"row": row, "col": col, "type": "mine"})
                    elif event_type == "reward_earned":
                         triggered_cells_list.append({"row": row, "col": col, "type": "reward"})

            new_hand = temp_hand
            if lose_letters:
                 logger.info(f"Harf kaybı mayını: {current_user} elindeki harfler sıfırlandı.")
                 new_hand = []
                 needed = 7
            else:
                 needed = 7 - len(new_hand)

            if needed > 0 and current_pool:
                 drawn_letters = deal_letters(current_pool, needed)
                 new_hand.extend(drawn_letters)
                 logger.debug(f"{current_user} {len(drawn_letters)} harf çekti. Yeni el: {new_hand}")
                 db_updates["pool"] = current_pool
            elif needed > 0:
                 logger.info(f"Havuz boş, {current_user} harf çekemedi.")

            db_updates[f"hands.{current_user}"] = new_hand
            db_updates["board.grid"] = temp_board
            db_updates["consecutive_passes"] = 0

            if not new_hand:
                logger.info(f"Oyuncu {current_user} elindeki harfleri bitirdi.")
                new_game_status = "finished_hand"
                winner_player_key_on_finish = current_player_key

        else:
            logger.error(f"Geçersiz hamle türü alındı: {move.move_type}. Oyun {game_id_str}")
            raise HTTPException(status_code=400, detail="Geçersiz hamle türü.")

        next_turn_player_key = opponent_key
        next_turn_player_username = opponent_username

        extra_move_earned = mine_reward_result.get("extra_move_earned", False)

        if is_extra_move_active:
             logger.info(f"{current_user} ekstra hamlesini kullandı. Sıra {opponent_username}'a geçiyor.")
             db_updates["extra_move_in_progress"] = False
             next_turn_player_key = opponent_key
             next_turn_player_username = opponent_username
             event_log_extra = {"type": "extra_move_used", "player": current_user, "timestamp": time.time()}
             current_push = db_push_ops.get("event_log")
             if isinstance(current_push, dict) and "$each" in current_push:
                 current_push["$each"].append(event_log_extra)
             elif current_push:
                 db_push_ops["event_log"] = {"$each": [current_push, event_log_extra]}
             else:
                 db_push_ops["event_log"] = event_log_extra

        elif extra_move_earned:
             logger.info(f"{current_user} ekstra hamle hakkı kazandı! Sıra kendisinde kalıyor.")
             notifications.append(f"✨ {current_user} ekstra hamle hakkı kazandı!")
             db_updates["extra_move_in_progress"] = True
             next_turn_player_key = current_player_key
             next_turn_player_username = current_user
        else:
             db_updates["extra_move_in_progress"] = False
             next_turn_player_key = opponent_key
             next_turn_player_username = opponent_username

        db_updates["turn"] = next_turn_player_username
        db_updates["turn_key"] = next_turn_player_key
        db_updates["lastMoveTime"] = current_time_float

        if next_turn_player_username in game.get("frozen_letters", {}) and game["frozen_letters"][next_turn_player_username]:
             logger.info(f"Sırası gelen {next_turn_player_username} oyuncusunun donmuş harfleri temizlendi.")
             db_updates.setdefault(f"frozen_letters.{next_turn_player_username}", [])

        if db_updates or db_push_ops:
            update_query: Dict[str, Any] = {}
            if db_updates: update_query["$set"] = db_updates
            if db_push_ops: update_query["$push"] = db_push_ops

            try:
                if "$set" in update_query and "board.grid" in update_query["$set"] and "board" in update_query["$set"]:
                     del update_query["$set"]["board"]

                update_result = await db.games.update_one({"_id": game_id_obj}, update_query)
                if update_result.matched_count == 0:
                     logger.error(f"DB güncelleme hatası (eşleşme yok): Oyun {game_id_str}")
                     raise HTTPException(status_code=500, detail="Oyun durumu güncellenemedi (eşleşme bulunamadı).")
                if update_result.modified_count == 0 and (db_updates or db_push_ops.get("event_log")):
                     logger.warning(f"DB güncellemesi yapıldı ama değişiklik olmadı? Oyun {game_id_str}, Sorgu: {update_query}")

            except Exception as e:
                logger.error(f"Veritabanı güncelleme hatası: Oyun {game_id_str}, Hata: {e}", exc_info=True)
                raise HTTPException(status_code=500, detail=f"Veritabanı güncellenirken hata oluştu: {e}")

        final_game_state_doc = await db.games.find_one({"_id": game_id_obj})
        if not final_game_state_doc:
             logger.error(f"Güncelleme sonrası oyun bulunamadı: ID {game_id_str}")
             raise HTTPException(status_code=500, detail="Oyun durumu güncellenemedi (tekrar bulunamadı).")

        if new_game_status.startswith("finished"):
            finished_game_doc = await finish_game(game_id_obj, winner_player_key_on_finish, status=new_game_status)
            final_game_state_doc = finished_game_doc if finished_game_doc else final_game_state_doc
            if not finished_game_doc:
                 logger.error(f"Oyun bitirme fonksiyonu None döndü: Oyun {game_id_str}")
                 raise HTTPException(status_code=500, detail="Oyun bitirilirken hata oluştu.")

        serialized_final_state = serialize_game_data(final_game_state_doc)
        if triggered_cells_list:
            serialized_final_state["triggered_cells"] = triggered_cells_list

        await manager.broadcast(game_id_str, GameStateUpdateMessage(payload=serialized_final_state))
        logger.debug(f"Oyun durumu yayınlandı: Oyun {game_id_str}")

        for msg in notifications:
            await manager.broadcast_notification(game_id_str, msg)

        final_status = final_game_state_doc.get("status", "")
        if final_status.startswith("finished"):
             final_winner_username = final_game_state_doc.get("winner")
             result_msg = f"Oyun Bitti! Kazanan: {final_winner_username}" if final_winner_username else "Oyun Bitti! (Berabere)"
             await manager.broadcast_notification(game_id_str, f"🏁 {result_msg}")
             logger.info(f"Oyun bitiş bildirimi yayınlandı: Oyun {game_id_str}, Sonuç: {result_msg}")

        move_processing_time = time.time() - start_time
        logger.info(f"Hamle başarıyla işlendi: Oyun {game_id_str}, Süre: {move_processing_time:.4f}s")
        return {"message": "Hamle işlendi.", "game_state": serialize_game_data(final_game_state_doc)}

    except HTTPException as http_exc:
        raise http_exc
    except ValidationError as val_err:
        log_game_id = game_id_str if game_id_str else game_id
        logger.warning(f"Geçersiz hamle verisi (ValidationError): Oyun {log_game_id}, Hata: {val_err.errors()}")
        raise HTTPException(status_code=400, detail=f"Geçersiz hamle verisi: {val_err.errors()}")
    except Exception as e:
        log_game_id = game_id_str if game_id_str else game_id
        logger.exception(f"Hamle işlenirken beklenmedik hata: Oyun {log_game_id}, Hata: {e}")
        raise HTTPException(status_code=500, detail=f"Hamle işlenirken beklenmedik bir sunucu hatası oluştu.")

@router.post("/surrender/{game_id}", response_model=dict)
async def surrender(game_id: str, current_user: str = Depends(get_current_user)):
    logger.info(f"Teslim olma isteği: Oyun {game_id}, Kullanıcı {current_user}")
    game_id_obj: Optional[ObjectId] = None
    game_id_str: Optional[str] = None
    try:
        game_id_obj = ObjectId(game_id)
        game_id_str = str(game_id_obj)
    except Exception:
        logger.warning(f"Geçersiz ID formatı (teslim olma): {game_id}")
        raise HTTPException(status_code=400, detail="Geçersiz ID formatı.")

    try:
        game = await db.games.find_one({"_id": game_id_obj})
        if not game:
            logger.warning(f"Oyun bulunamadı (teslim olma): {game_id_str}")
            raise HTTPException(status_code=404, detail="Oyun bulunamadı.")

        current_status = game.get("status", "")
        if current_status.startswith("finished"):
            return {"message": "Oyun zaten bitmiş.", "game_state": serialize_game_data(game)}
        if not current_status.startswith("active"):
            logger.warning(f"Aktif olmayan oyunda teslim olma denemesi: {game_id_str}")
            raise HTTPException(status_code=400, detail="Oyun aktif değilken teslim olunamaz.")

        current_player_key, opponent_key = get_player_keys(game, current_user)
        if not current_player_key:
            logger.warning(f"Yetkisiz teslim olma denemesi: Oyun {game_id_str}, Kullanıcı {current_user}")
            raise HTTPException(status_code=403, detail="Bu oyuna ait değilsiniz.")

        event_log_entry = {"type": "surrender", "player": current_user, "timestamp": time.time()}
        await db.games.update_one({"_id": game_id_obj}, {"$push": {"event_log": event_log_entry}})

        finished_game = await finish_game(game_id_obj, opponent_key, status="finished_surrender")

        if finished_game:
            serialized_game = serialize_game_data(finished_game)
            await manager.broadcast(game_id_str, GameStateUpdateMessage(payload=serialized_game))
            surrender_msg = f"🏳️ {current_user} teslim oldu."
            await manager.broadcast_notification(game_id_str, surrender_msg)
            winner_username = finished_game.get("winner")
            await manager.broadcast_notification(game_id_str, f"🏁 Oyun Bitti! Kazanan: {winner_username}")
            logger.info(f"Oyuncu teslim oldu: Oyun {game_id_str}, Teslim olan: {current_user}, Kazanan: {winner_username}")
            return {"message": "Teslim olundu.", "game_state": serialized_game}
        else:
            logger.error(f"Teslim olma sonrası oyun bitirilemedi: Oyun {game_id_str}")
            raise HTTPException(status_code=500, detail="Teslim olundu ancak oyun durumu güncellenemedi.")
    except Exception as e:
        log_game_id = game_id_str if game_id_str else game_id
        logger.exception(f"Teslim olma sırasında beklenmedik hata: Oyun {log_game_id}, Hata: {e}")
        raise HTTPException(status_code=500, detail=f"Teslim olma sırasında beklenmedik bir sunucu hatası oluştu.")

@router.get("/list/active", response_model=List[dict])
async def list_active_games(current_user: str = Depends(get_current_user)):
    logger.debug(f"Aktif oyun listesi isteği: Kullanıcı {current_user}")
    try:
        projection = { "_id": 1, "player1_username": 1, "player2_username": 1, "turn": 1, "timeOption": 1, "scores": 1, "player1_key": 1, "player2_key": 1, "lastMoveTime": 1 }
        games_cursor = db.games.find(
            {"status": "active", "$or": [{"player1_username": current_user}, {"player2_username": current_user}]},
            projection=projection
        ).sort([("lastMoveTime", -1)])

        active_games = []
        async for game in games_cursor:
             game_id_str = str(game["_id"])
             current_player_key, opponent_key = get_player_keys(game, current_user)
             opponent_username = None
             if opponent_key:
                  opponent_username = game.get("player1_username") if opponent_key == game.get("player1_key") else game.get("player2_username")
             my_score = game.get("scores",{}).get(current_player_key, 0) if current_player_key else 0
             opponent_score = game.get("scores",{}).get(opponent_key, 0) if opponent_key else 0

             active_games.append({
                 "game_id": game_id_str,
                 "opponent": opponent_username if opponent_username else "Bilinmiyor",
                 "turn": game.get("turn"),
                 "isMyTurn": game.get("turn") == current_user,
                 "timeOption": game.get("timeOption"),
                 "myScore": my_score,
                 "opponentScore": opponent_score,
             })
        logger.debug(f"{current_user} için {len(active_games)} aktif oyun bulundu.")
        return active_games
    except Exception as e:
        logger.error(f"Aktif oyunları listelerken hata: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Aktif oyunlar listelenemedi.")

@router.get("/list/finished", response_model=List[dict])
async def list_finished_games(current_user: str = Depends(get_current_user)):
    logger.debug(f"Bitmiş oyun listesi isteği: Kullanıcı {current_user}")
    try:
        projection = { "_id": 1, "player1_username": 1, "player2_username": 1, "winner": 1, "status": 1, "scores": 1, "gameStartTime": 1, "player1_key": 1, "player2_key": 1 }
        games_cursor = db.games.find(
            {"status": {"$regex": "^finished"}, "$or": [{"player1_username": current_user}, {"player2_username": current_user}]},
            projection=projection
        ).sort([("gameStartTime", -1)]).limit(50)

        finished_games = []
        async for game in games_cursor:
             game_id_str = str(game["_id"])
             current_player_key, opponent_key = get_player_keys(game, current_user)
             opponent_username = None
             if opponent_key:
                  opponent_username = game.get("player1_username") if opponent_key == game.get("player1_key") else game.get("player2_username")
             winner_username = game.get("winner")
             my_score = game.get("scores",{}).get(current_player_key, 0) if current_player_key else 0
             opponent_score = game.get("scores",{}).get(opponent_key, 0) if opponent_key else 0
             result_text = "Berabere"
             if winner_username: result_text = "Kazandınız" if winner_username == current_user else "Kaybettiniz"

             finished_games.append({
                 "game_id": game_id_str,
                 "opponent": opponent_username if opponent_username else "Bilinmiyor",
                 "winner": winner_username,
                 "status": game.get("status"),
                 "myScore": my_score,
                 "opponentScore": opponent_score,
                 "result": result_text
             })
        logger.debug(f"{current_user} için {len(finished_games)} bitmiş oyun bulundu.")
        return finished_games
    except Exception as e:
        logger.error(f"Bitmiş oyunları listelerken hata: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Bitmiş oyunlar listelenemedi.")

@router.get("/user/stats", response_model=dict)
async def get_user_stats(current_user: str = Depends(get_current_user)):
    logger.debug(f"Kullanıcı istatistik isteği: {current_user}")
    try:
        user_doc = await db.users.find_one({"username": current_user}, projection={"wins": 1, "total_games": 1})
        if not user_doc:
            logger.warning(f"İstatistik için kullanıcı bulunamadı: {current_user}")
            return {"username": current_user, "wins": 0, "total_games": 0, "success_rate": 0.0}
        wins = user_doc.get("wins", 0)
        total_games = user_doc.get("total_games", 0)
        success_rate = (wins / total_games * 100) if total_games > 0 else 0.0
        stats = {"username": current_user, "wins": wins, "total_games": total_games, "success_rate": round(success_rate, 2)}
        logger.debug(f"{current_user} istatistikleri: {stats}")
        return stats
    except Exception as e:
        logger.error(f"Kullanıcı istatistikleri alınırken hata: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Kullanıcı istatistikleri alınamadı.")

@router.get("/detail/{game_id}", response_model=dict)
async def get_game_detail(game_id: str, current_user: str = Depends(get_current_user)):
    logger.debug(f"Oyun detayı isteği: Oyun {game_id}, Kullanıcı {current_user}")
    game_id_obj: Optional[ObjectId] = None
    game_id_str: Optional[str] = None
    try:
        game_id_obj = ObjectId(game_id)
        game_id_str = str(game_id_obj)
    except Exception:
        logger.warning(f"Geçersiz ID formatı (detay): {game_id}")
        raise HTTPException(status_code=400, detail="Geçersiz ID formatı.")
    try:
        game = await db.games.find_one({"_id": game_id_obj})
        if not game:
            logger.warning(f"Oyun bulunamadı (detay): {game_id_str}")
            raise HTTPException(status_code=404, detail="Oyun bulunamadı.")
        if current_user not in (game.get("player1_username"), game.get("player2_username")):
            logger.warning(f"Yetkisiz oyun detayı erişimi: Oyun {game_id_str}, Kullanıcı {current_user}")
            raise HTTPException(status_code=403, detail="Bu oyun detaylarını görme yetkiniz yok.")
        serialized_game = serialize_game_data(game)
        logger.debug(f"Oyun detayı başarıyla döndürüldü: Oyun {game_id_str}")
        return serialized_game
    except Exception as e:
        log_game_id = game_id_str if game_id_str else game_id
        logger.exception(f"Oyun detayı alınırken beklenmedik hata: Oyun {log_game_id}, Hata: {e}")
        raise HTTPException(status_code=500, detail=f"Oyun detayı alınırken beklenmedik bir sunucu hatası oluştu.")