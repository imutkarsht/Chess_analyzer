import datetime
import time
import io
import chess.pgn
from typing import Callable, List, Optional
from src.backend.models.game_info import GameInfo
from src.backend.storage.game_history import GameHistoryManager

def parse_pgn_headers(pgn: str, default_white="?", default_black="?", default_result="*", default_date_str="????.??.??", default_white_elo=None, default_black_elo=None, default_time_class=None, default_opening=None):
    white = default_white
    black = default_black
    result = default_result
    date_str = default_date_str
    white_elo = default_white_elo
    black_elo = default_black_elo
    time_class = default_time_class
    opening = default_opening
    move_count = None
    
    try:
        game = chess.pgn.read_game(io.StringIO(pgn))
        if game:
            h = game.headers
            h_white = h.get("White")
            if h_white and h_white != "?":
                white = h_white
                
            h_black = h.get("Black")
            if h_black and h_black != "?":
                black = h_black
                
            h_result = h.get("Result")
            if h_result and h_result != "*":
                result = h_result
                
            h_date = h.get("Date")
            if h_date and h_date != "????.??.??":
                date_str = h_date
            if date_str and "." in date_str:
                date_str = date_str.replace(".", "-")
                
            h_w_elo = h.get("WhiteElo")
            if h_w_elo and h_w_elo != "?":
                white_elo = h_w_elo
                
            h_b_elo = h.get("BlackElo")
            if h_b_elo and h_b_elo != "?":
                black_elo = h_b_elo
                
            h_event = h.get("Event")
            if h_event and h_event not in ["?", "Lichess Game", "Chess.com Game"]:
                time_class = h_event
                
            h_opening = h.get("Opening")
            if h_opening and h_opening != "?":
                opening = h_opening

            node = game
            cnt = 0
            while node.variations:
                node = node.variation(0)
                cnt += 1
            move_count = (cnt + 1) // 2
    except Exception:
        pass
        
    return white, black, result, date_str, white_elo, black_elo, time_class, opening, move_count


class ApiGameCache:
    def __init__(self, history_manager: GameHistoryManager):
        self.history_manager = history_manager

    def get_by_id(self, source: str, game_id: str, fetch_func: Callable) -> Optional[GameInfo]:
        """Check cache first; miss → call fetch_func → save to cache → return"""
        cached = self.history_manager.get_cached_game(game_id)
        if cached:
            return cached

        raw_result = fetch_func()
        if not raw_result or "pgn" not in raw_result:
            return None

        pgn = raw_result.get("pgn", "")
        default_white = raw_result.get("white") or "?"
        default_black = raw_result.get("black") or "?"
        default_white_elo = raw_result.get("white_rating") or raw_result.get("white_elo")
        default_black_elo = raw_result.get("black_rating") or raw_result.get("black_elo")
        default_time_class = raw_result.get("time_class") or raw_result.get("time_control")
        default_opening = raw_result.get("opening")

        white, black, result, date_str, white_elo, black_elo, time_class, opening, move_count = parse_pgn_headers(
            pgn, default_white, default_black, "*", "????.??.??",
            default_white_elo, default_black_elo, default_time_class, default_opening
        )

        if white_elo is not None:
            white_elo = str(white_elo)
        if black_elo is not None:
            black_elo = str(black_elo)

        info = GameInfo(
            game_id=game_id,
            source=source,
            white=white,
            black=black,
            result=result,
            date=date_str,
            pgn=pgn,
            white_elo=white_elo,
            black_elo=black_elo,
            time_class=time_class,
            move_count=move_count,
            opening=opening
        )
        self.history_manager.save_cached_game(info)
        return info

    def get_by_date(self, source: str, username: str, date: datetime.date,
                    fetch_func: Callable) -> List[GameInfo]:
        """Check cache first for (source, date, username); miss → call fetch_func → bulk-save → return"""
        date_str = date.strftime("%Y-%m-%d")
        cached_games = self.history_manager.get_cached_games_for_date(source, date_str, username)
        if cached_games:
            return cached_games

        raw_games = fetch_func()
        if not raw_games:
            return []

        game_infos = []

        for g in raw_games:
            pgn = g.get("pgn", "")
            if not pgn:
                continue

            url = g.get("url", "")
            game_id = ""
            if source == "lichess":
                from src.backend.api.lichess_api import LichessAPI
                game_id = LichessAPI().extract_game_id(url) or url.split("/")[-1]
            else:
                from src.backend.api.chess_com_api import ChessComAPI
                game_id = ChessComAPI.extract_game_id(url) or url.split("/")[-1]

            if not game_id:
                import hashlib
                game_id = hashlib.md5(pgn.encode("utf-8")).hexdigest()

            w_data = g.get("white", {})
            b_data = g.get("black", {})

            default_white = w_data.get("username") if isinstance(w_data, dict) else w_data
            default_black = b_data.get("username") if isinstance(b_data, dict) else b_data
            default_white_elo = str(w_data.get("rating")) if isinstance(w_data, dict) and w_data.get("rating") else None
            default_black_elo = str(b_data.get("rating")) if isinstance(b_data, dict) and b_data.get("rating") else None
            default_time_class = g.get("time_class") or g.get("time_control")
            default_opening = g.get("opening")

            white, black, result, g_date, white_elo, black_elo, time_class, opening, move_count = parse_pgn_headers(
                pgn, default_white, default_black, "*", date_str,
                default_white_elo, default_black_elo, default_time_class, default_opening
            )

            if white_elo is not None:
                white_elo = str(white_elo)
            if black_elo is not None:
                black_elo = str(black_elo)

            info = GameInfo(
                game_id=game_id,
                source=source,
                white=white or "?",
                black=black or "?",
                result=result,
                date=g_date,
                pgn=pgn,
                white_elo=white_elo,
                black_elo=black_elo,
                time_class=time_class,
                move_count=move_count,
                opening=opening
            )
            game_infos.append(info)

        if game_infos:
            self.history_manager.save_cached_games_bulk(game_infos)

        return game_infos

    def get_recent(self, source: str, username: str, limit: int,
                   fetch_func: Callable) -> List[GameInfo]:
        """Always fetch fresh. Return list."""
        raw_games = fetch_func()
        if not raw_games:
            return []

        game_infos = []

        for g in raw_games:
            pgn = g.get("pgn", "")
            if not pgn:
                continue

            url = g.get("url", "")
            game_id = ""
            if source == "lichess":
                from src.backend.api.lichess_api import LichessAPI
                game_id = LichessAPI().extract_game_id(url) or url.split("/")[-1]
            else:
                from src.backend.api.chess_com_api import ChessComAPI
                game_id = ChessComAPI.extract_game_id(url) or url.split("/")[-1]

            if not game_id:
                import hashlib
                game_id = hashlib.md5(pgn.encode("utf-8")).hexdigest()

            w_data = g.get("white", {})
            b_data = g.get("black", {})

            default_white = w_data.get("username") if isinstance(w_data, dict) else w_data
            default_black = b_data.get("username") if isinstance(b_data, dict) else b_data
            default_white_elo = str(w_data.get("rating")) if isinstance(w_data, dict) and w_data.get("rating") else None
            default_black_elo = str(b_data.get("rating")) if isinstance(b_data, dict) and b_data.get("rating") else None
            default_time_class = g.get("time_class") or g.get("time_control")
            default_opening = g.get("opening")
            default_date = time.strftime("%Y-%m-%d")

            white, black, result, g_date, white_elo, black_elo, time_class, opening, move_count = parse_pgn_headers(
                pgn, default_white, default_black, "*", default_date,
                default_white_elo, default_black_elo, default_time_class, default_opening
            )

            if white_elo is not None:
                white_elo = str(white_elo)
            if black_elo is not None:
                black_elo = str(black_elo)

            info = GameInfo(
                game_id=game_id,
                source=source,
                white=white or "?",
                black=black or "?",
                result=result,
                date=g_date,
                pgn=pgn,
                white_elo=white_elo,
                black_elo=black_elo,
                time_class=time_class,
                move_count=move_count,
                opening=opening
            )
            game_infos.append(info)

        if game_infos:
            self.history_manager.save_cached_games_bulk(game_infos)

        return game_infos
