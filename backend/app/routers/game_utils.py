import random
import logging
from typing import List, Dict, Tuple, Any, Set
import pathlib
import math
import time


logger = logging.getLogger("game_utils")
if not logger.hasHandlers():

    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger.info("game_utils logger başlatıldı.")


BASE_DIR = pathlib.Path(__file__).parent.resolve()
KELIME_LISTESI_PATH = BASE_DIR / "kelime_listesi.txt"
WORD_LIST: Set[str] = set()

try:

    if KELIME_LISTESI_PATH.is_file():
        with open(KELIME_LISTESI_PATH, "r", encoding="utf-8") as f:

            WORD_LIST = {line.strip().lower() for line in f if line.strip()}
            logger.info(f"{len(WORD_LIST)} kelime başarıyla yüklendi: {KELIME_LISTESI_PATH}")
    else:
        logger.warning(f"Kelime listesi bulunamadı: {KELIME_LISTESI_PATH}")
except Exception as e:
    logger.error(f"Kelime listesi yüklenirken hata oluştu: {e}", exc_info=True)

def is_valid_word(word: str) -> bool:
    if not WORD_LIST:
        logger.warning("Kelime listesi boş veya yüklenemedi, tüm kelimeler geçerli sayılıyor.")
        return True
    is_valid = word.strip().lower() in WORD_LIST

    return is_valid


LETTER_DISTRIBUTION = {
    "A": {"count": 12, "point": 1}, "B": {"count": 2, "point": 3},
    "C": {"count": 2, "point": 4}, "Ç": {"count": 2, "point": 4},
    "D": {"count": 2, "point": 3}, "E": {"count": 8, "point": 1},
    "F": {"count": 1, "point": 7}, "G": {"count": 1, "point": 5},
    "Ğ": {"count": 1, "point": 8}, "H": {"count": 1, "point": 5},
    "I": {"count": 4, "point": 2}, "İ": {"count": 7, "point": 1},
    "J": {"count": 1, "point": 10}, "K": {"count": 7, "point": 1},
    "L": {"count": 7, "point": 1}, "M": {"count": 4, "point": 2},
    "N": {"count": 5, "point": 1}, "O": {"count": 3, "point": 2},
    "Ö": {"count": 1, "point": 7}, "P": {"count": 1, "point": 5},
    "R": {"count": 6, "point": 1}, "S": {"count": 3, "point": 2},
    "Ş": {"count": 2, "point": 4}, "T": {"count": 5, "point": 1},
    "U": {"count": 3, "point": 2}, "Ü": {"count": 2, "point": 3},
    "V": {"count": 1, "point": 7}, "Y": {"count": 2, "point": 3},
    "Z": {"count": 1, "point": 4},
    "JOKER": {"count": 2, "point": 0}
}

LETTER_SCORES: Dict[str, int] = {
    letter: data["point"]
    for letter, data in LETTER_DISTRIBUTION.items()
}

total_letters = sum(d['count'] for d in LETTER_DISTRIBUTION.values())

MINE_TYPES_COUNT = {
    "puan_bolunmesi": 5, "puan_transferi": 4, "harf_kaybi": 3,
    "ekstra_hamle_engeli": 2, "kelime_iptali": 2
}
REWARD_TYPES_COUNT = {
    "bolge_yasagi": 2, "harf_yasagi": 3, "ekstra_hamle_jokeri": 2
}
TOTAL_MINES = sum(MINE_TYPES_COUNT.values())
TOTAL_REWARDS = sum(REWARD_TYPES_COUNT.values())

MINE_POOL = [m for m, count in MINE_TYPES_COUNT.items() for _ in range(count)]
REWARD_POOL = [r for r, count in REWARD_TYPES_COUNT.items() for _ in range(count)]


def generate_letter_pool() -> List[str]:
    pool = []
    for letter, data in LETTER_DISTRIBUTION.items():
        pool.extend([letter] * data["count"])
    random.shuffle(pool)
    logger.debug(f"{len(pool)} harflik yeni havuz oluşturuldu.")
    return pool

def deal_letters(pool: List[str], count: int) -> List[str]:
    drawn = []
    actual_count = min(count, len(pool))
    for _ in range(actual_count):
        if pool:
            drawn.append(pool.pop())
    logger.debug(f"{len(drawn)} harf çekildi. Havuzda kalan: {len(pool)}")
    return [str(letter) for letter in drawn]

def assign_solid_bonuses(board: List[List[Dict]]):
    rows, cols = 15, 15
    bonus_coords = {
        "K3": [(0, 0), (0, 7), (0, 14), (7, 0), (7, 14), (14, 0), (14, 7), (14, 14)],
        "K2": [(1, 1), (2, 2), (3, 3), (4, 4), (1, 13), (2, 12), (3, 11), (4, 10), (10, 4), (11, 3), (12, 2), (13, 1), (10, 10), (11, 11), (12, 12), (13, 13)],
        "H3": [(1, 5), (1, 9), (5, 1), (5, 5), (5, 9), (5, 13), (9, 1), (9, 5), (9, 9), (9, 13), (13, 5), (13, 9)],
        "H2": [(0, 3), (0, 11), (2, 6), (2, 8), (3, 0), (3, 7), (3, 14), (6, 2), (6, 6), (6, 8), (6, 12), (7, 3), (7, 11), (8, 2), (8, 6), (8, 8), (8, 12), (11, 0), (11, 7), (11, 14), (12, 6), (12, 8), (14, 3), (14, 11)],
        "start": [(7, 7)]
    }
    count = 0
    for bonus_type, coords_list in bonus_coords.items():
        for r, c in coords_list:
            if 0 <= r < rows and 0 <= c < cols:
                 if r < len(board) and c < len(board[r]):

                     board[r][c].setdefault("special", None)
                     if board[r][c]["special"] is None:
                         board[r][c]["special"] = bonus_type
                         count += 1



            else: logger.warning(f"Bonus koordinatı tahta dışında (değer): [{r},{c}]")
    logger.info(f"{count} adet sabit bonus kare atandı.")

def assign_mines_and_rewards(board: List[List[Dict]]) -> Tuple[Dict[str, str], Dict[str, str]]:
    rows, cols = 15, 15
    mines_map: Dict[str, str] = {}
    rewards_map: Dict[str, str] = {}


    empty_cells = []
    for r in range(rows):
        for c in range(cols):
            cell = board[r][c]

            if cell.get('letter') is None and cell.get('special') is None:
                empty_cells.append((r, c))

    if not empty_cells:
        logger.warning("Mayın/Ödül atanacak uygun boş kare bulunamadı.")
        return mines_map, rewards_map

    total_items_to_place = TOTAL_MINES + TOTAL_REWARDS

    items_to_place_count = min(len(empty_cells), total_items_to_place)

    selected_cells = random.sample(empty_cells, items_to_place_count)
    logger.info(f"{items_to_place_count} adet mayın/ödül için {len(selected_cells)} kare seçildi.")


    temp_mine_pool = MINE_POOL[:]
    temp_reward_pool = REWARD_POOL[:]
    random.shuffle(temp_mine_pool)
    random.shuffle(temp_reward_pool)

    mines_placed_count = 0
    rewards_placed_count = 0


    can_place_mines = min(TOTAL_MINES, items_to_place_count)
    remaining_cells_count = len(selected_cells)
    for i in range(can_place_mines):
        if not selected_cells or not temp_mine_pool: break
        r, c = selected_cells.pop()
        remaining_cells_count -= 1
        coord_key = f"{r}_{c}"
        mine_type = temp_mine_pool.pop()
        mines_map[coord_key] = mine_type
        mines_placed_count += 1


    can_place_rewards = min(TOTAL_REWARDS, remaining_cells_count)
    for i in range(can_place_rewards):
        if not selected_cells or not temp_reward_pool: break
        r, c = selected_cells.pop()
        coord_key = f"{r}_{c}"
        reward_type = temp_reward_pool.pop()
        rewards_map[coord_key] = reward_type
        rewards_placed_count += 1

    logger.info(f"{mines_placed_count} mayın ve {rewards_placed_count} ödül tahtaya atandı.")
    return mines_map, rewards_map

def touches_existing_letter(board: List[List[Dict]], positions: List[List[int]], is_first_move: bool) -> bool:
    if is_first_move:


        return True

    rows, cols = 15, 15
    pos_set = {tuple(p) for p in positions}

    for r, c in positions:

        for dr, dc in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            nr, nc = r + dr, c + dc

            if 0 <= nr < rows and 0 <= nc < cols:

                if board[nr][nc].get("letter") is not None and tuple([nr, nc]) not in pos_set:
                    return True

    logger.debug("Yerleştirilen harfler mevcut harflere dokunmuyor.")
    return False

def trace_word_in_line(board: List[List[Dict]], start_r: int, start_c: int, dr: int, dc: int) -> List[Dict]:
    word_tiles = []
    rows, cols = 15, 15
    cr, cc = start_r, start_c


    try:
        while 0 <= cr - dr < rows and 0 <= cc - dc < cols and \
              board[cr - dr][cc - dc].get("letter") is not None:
            cr -= dr
            cc -= dc
    except IndexError:

        pass


    try:
        while 0 <= cr < rows and 0 <= cc < cols:
            current_cell = board[cr][cc]
            letter_on_board = current_cell.get("letter")
            if letter_on_board is None:
                break

            word_tiles.append({
                "letter": letter_on_board,
                "original_tile": current_cell.get("original_tile", letter_on_board),
                "row": cr,
                "col": cc,
                "special": current_cell.get("special")
            })
            cr += dr
            cc += dc
    except IndexError:
        pass

    return word_tiles



def find_all_formed_words(board: List[List[Dict]], placed_positions: List[List[int]]) -> Tuple[List[Dict], bool, List[str]]:
    if not placed_positions:
        return [], False, ["Yerleştirilmiş harf yok."]

    placed_coords_set = {tuple(p) for p in placed_positions}
    rows, cols = 15, 15


    min_r, max_r = min(r for r, c in placed_positions), max(r for r, c in placed_positions)
    min_c, max_c = min(c for r, c in placed_positions), max(c for r, c in placed_positions)

    is_horizontal = min_r == max_r
    is_vertical = min_c == max_c
    is_single_tile = len(placed_positions) == 1


    if not is_single_tile and not (is_horizontal or is_vertical):
        logger.warning("Geçersiz yerleştirme: Harfler tek sıra halinde değil.")
        return [], False, ["Geçersiz yerleştirme: Harfler tek sıra halinde (yatay veya dikey) olmalı."]


    potential_words_details: Dict[str, List[Dict]] = {}


    main_axis_dr, main_axis_dc = (0, 1) if is_horizontal else (1, 0)
    if not is_single_tile:

        start_r, start_c = placed_positions[0]
        main_word_tiles = trace_word_in_line(board, start_r, start_c, main_axis_dr, main_axis_dc)

        if len(main_word_tiles) > 1 and any(tuple([t['row'], t['col']]) in placed_coords_set for t in main_word_tiles):
            main_word_str = "".join(tile["letter"] for tile in main_word_tiles if tile.get("letter"))
            potential_words_details[main_word_str] = main_word_tiles

    elif is_single_tile:
        start_r, start_c = placed_positions[0]
        for dr, dc in [(0, 1), (1, 0)]:
            word_tiles = trace_word_in_line(board, start_r, start_c, dr, dc)

            if len(word_tiles) > 1:
                 word_str = "".join(tile["letter"] for tile in word_tiles if tile.get("letter"))
                 potential_words_details[word_str] = word_tiles


    cross_axis_dr, cross_axis_dc = (1, 0) if is_horizontal else (0, 1)
    for r_placed, c_placed in placed_positions:
        cross_word_tiles = trace_word_in_line(board, r_placed, c_placed, cross_axis_dr, cross_axis_dc)

        if len(cross_word_tiles) > 1 and any(t['row'] == r_placed and t['col'] == c_placed for t in cross_word_tiles):
            cross_word_str = "".join(tile["letter"] for tile in cross_word_tiles if tile.get("letter"))
            potential_words_details[cross_word_str] = cross_word_tiles


    is_first_move_on_board = not any(board[r][c].get("letter")
                                     for r in range(rows) for c in range(cols)
                                     if (r, c) not in placed_coords_set)

    if not potential_words_details:

        if is_single_tile and is_first_move_on_board:

             logger.debug("İlk hamle tek harf, kelime oluşmadı (geçerli).")
             return [], True, []
        else:

             logger.warning("Geçerli kelime oluşturulamadı (potansiyel kelime yok).")
             return [], False, ["Geçerli bir kelime oluşturulamadı."]


    valid_formed_word_details = []
    all_words_valid = True
    invalid_words_list = []

    logger.debug(f"Doğrulanacak potansiyel kelimeler: {list(potential_words_details.keys())}")

    for word_str, tiles in potential_words_details.items():
        if not is_valid_word(word_str):
            logger.warning(f"Geçersiz kelime bulundu: '{word_str}'")
            all_words_valid = False
            if word_str not in invalid_words_list:
                invalid_words_list.append(word_str)
        elif all_words_valid:

             valid_formed_word_details.append({
                 "word": word_str,
                 "tiles": tiles
             })


    if not all_words_valid:
        logger.warning(f"Hamle geçersiz, geçersiz kelimeler: {invalid_words_list}")
        return [], False, invalid_words_list


    logger.debug(f"Hamle geçerli, bulunan kelimeler: {[wd['word'] for wd in valid_formed_word_details]}")
    return valid_formed_word_details, True, []


def calculate_word_score(board: List[List[Dict]], word_tiles: List[Dict], placed_coords: Set[Tuple[int, int]]) -> int:
    word_score = 0
    word_multiplier = 1
    word_str = "".join(tile["letter"] for tile in word_tiles)

    for tile in word_tiles:
        r, c = tile["row"], tile["col"]
        original_tile_letter = tile.get("original_tile")
        assigned_letter = tile.get("letter")

        if not original_tile_letter: original_tile_letter = assigned_letter


        letter_point = LETTER_SCORES.get(original_tile_letter.upper(), 0)

        letter_multiplier = 1
        is_newly_placed = tuple([r, c]) in placed_coords


        if is_newly_placed:
            special = tile.get("special")
            if special == "H2": letter_multiplier = 2
            elif special == "H3": letter_multiplier = 3
            elif special == "K2" or special == "start": word_multiplier *= 2
            elif special == "K3": word_multiplier *= 3

        word_score += letter_point * letter_multiplier


    final_score = word_score * word_multiplier
    logger.debug(f"Skor hesaplandı: Kelime='{word_str}', Skor={word_score}, Çarpan={word_multiplier}, Final={final_score}")
    return final_score


def apply_mine_and_reward_effects(
    game_data: Dict, placed_tiles_info: List[Dict], score_gain: int,
    player_key: str, opponent_key: str
) -> Dict:
    updates: Dict[str, Any] = {}
    notifications: List[str] = []
    triggered_events: List[Dict[str, Any]] = []
    final_score = score_gain
    cancel_word = False
    lose_letters = False
    extra_move_earned = False
    extra_move_in_progress = game_data.get("extra_move_in_progress", False)

    current_player_username = game_data.get(f"{player_key}_username")
    opponent_player_username = game_data.get(f"{opponent_key}_username")


    current_scores = game_data.get("scores", {}).copy()
    available_rewards = game_data.get("allAvailableRewards", {}).copy()

    mines_map = game_data.get("internal_mines_on_board", {}).copy()
    rewards_map = game_data.get("internal_rewards_on_board", {}).copy()

    triggered_mines_types = []
    triggered_rewards_types = []
    db_updates_for_triggered_items = {}

    event_timestamp = time.time()


    for tile_info in placed_tiles_info:
        r, c = tile_info["row"], tile_info["col"]
        coord_key = f"{r}_{c}"


        if coord_key in mines_map and mines_map[coord_key]:
            mine_type = mines_map[coord_key]
            triggered_mines_types.append(mine_type)
            effect_desc = f"{mine_type.replace('_', ' ').title()}"
            notifications.append(f"💥 Mayın Tetiklendi [{r},{c}]: {effect_desc}")

            db_updates_for_triggered_items[f"internal_mines_on_board.{coord_key}"] = ""
            mines_map.pop(coord_key, None)

            triggered_events.append({
                "type": "mine_triggered",
                "player": current_player_username,
                "mine_type": mine_type,
                "pos": [r, c],
                "timestamp": event_timestamp
            })


        elif coord_key in rewards_map and rewards_map[coord_key]:
            reward_type = rewards_map[coord_key]
            triggered_rewards_types.append(reward_type)
            effect_desc = f"{reward_type.replace('_', ' ').title()}"
            notifications.append(f"🎁 Ödül Kazanıldı [{r},{c}]: {effect_desc}")

            current_player_rewards = available_rewards.setdefault(player_key, [])
            current_player_rewards.append(reward_type)
            db_updates_for_triggered_items[f"allAvailableRewards.{player_key}"] = current_player_rewards

            db_updates_for_triggered_items[f"internal_rewards_on_board.{coord_key}"] = ""
            rewards_map.pop(coord_key, None)

            if reward_type == "ekstra_hamle_jokeri":
                extra_move_earned = True

            triggered_events.append({
                "type": "reward_earned",
                "player": current_player_username,
                "reward_type": reward_type,
                "pos": [r, c],
                "timestamp": event_timestamp
            })


    mine_effect_descriptions: Dict[str, str] = {}


    if "ekstra_hamle_engeli" in triggered_mines_types:

        effect_msg = "Bonus çarpanları iptal edildi (bu hamle için)."
        notifications.append(f"Ekstra hamle engeli: {effect_msg}")
        mine_effect_descriptions["ekstra_hamle_engeli"] = effect_msg


    if "puan_bolunmesi" in triggered_mines_types:
        original_score = final_score

        final_score = math.ceil(final_score * 0.3)
        effect_msg = f"Puan %70 azaldı! ({original_score} -> {final_score})"
        notifications.append(f"Puan bölünmesi: {effect_msg}")
        mine_effect_descriptions["puan_bolunmesi"] = effect_msg

    if "puan_transferi" in triggered_mines_types:
        opponent_current_score = current_scores.get(opponent_key, 0)
        transfer_amount = final_score

        updates[f"scores.{opponent_key}"] = updates.get(f"scores.{opponent_key}", opponent_current_score) + transfer_amount
        effect_msg = f"{transfer_amount} puan rakibe ({opponent_player_username}) gitti!"
        notifications.append(f"Puan transferi: {effect_msg}")
        mine_effect_descriptions["puan_transferi"] = effect_msg
        final_score = 0

    if "harf_kaybi" in triggered_mines_types:
        lose_letters = True
        effect_msg = "Elinizdeki tüm harfler bu tur sonunda kaybolacak!"
        notifications.append(f"Harf kaybı: {effect_msg}")
        mine_effect_descriptions["harf_kaybi"] = effect_msg

    if "kelime_iptali" in triggered_mines_types:
        final_score = 0
        cancel_word = True
        effect_msg = "Bu hamleden hiç puan alamadınız!"
        notifications.append(f"Kelime iptali: {effect_msg}")
        mine_effect_descriptions["kelime_iptali"] = effect_msg



    for event in triggered_events:
        if event["type"] == "mine_triggered" and event["mine_type"] in mine_effect_descriptions:
            event["effect_description"] = mine_effect_descriptions[event["mine_type"]]


    if final_score < 0: final_score = 0


    if final_score > 0 and not cancel_word and "puan_transferi" not in triggered_mines_types:
         player_current_score = current_scores.get(player_key, 0)

         if f"scores.{player_key}" not in updates:
              updates[f"scores.{player_key}"] = player_current_score + final_score


    updates.update(db_updates_for_triggered_items)


    result = {
        "final_score": final_score,
        "updates": updates,
        "notifications": notifications,
        "cancel_word": cancel_word,
        "lose_letters": lose_letters,
        "extra_move_earned": extra_move_earned,
        "extra_move_in_progress": extra_move_in_progress,
        "triggered_events": triggered_events
    }
    logger.debug(f"Mayın/Ödül etkileri sonucu: {result}")
    return result