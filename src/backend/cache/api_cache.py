import datetime
import hashlib
import time
from collections.abc import Callable

from src.backend.api.chess_com_api import ChessComAPI
from src.backend.api.lichess_api import LichessAPI
from src.backend.models.game_info import GameInfo
from src.backend.storage.game_history import GameHistoryManager
from src.backend.storage.pgn_metadata import parse_pgn_headers


def _cache_is_fresh(games: list[GameInfo], ttl_seconds: float) -> bool:
    """True when at least one cached row was written within ``ttl_seconds``.

    Today's results change while the day is still running, so a cache hit for
    today must be short-lived. Historical dates are immutable and can stay
    cached indefinitely.
    """
    now = time.time()
    for game in games:
        raw = getattr(game, "cached_at", None)
        if not raw:
            continue
        try:
            written = time.mktime(time.strptime(raw, "%Y-%m-%d %H:%M:%S"))
        except (TypeError, ValueError):
            continue
        if now - written <= ttl_seconds:
            return True
    return False


_TODAY_CACHE_TTL_SECONDS = 5 * 60


def _game_id_from_url(source: str, url: str, pgn: str) -> str:
    if source == "lichess":
        game_id = LichessAPI().extract_game_id(url) or url.split("/")[-1]
    else:
        game_id = ChessComAPI.extract_game_id(url) or url.split("/")[-1]
    if not game_id:
        game_id = hashlib.md5(pgn.encode("utf-8")).hexdigest()
    return game_id


def _to_game_info(
    source: str,
    raw_game: dict,
    default_date: str,
) -> GameInfo | None:
    pgn = raw_game.get("pgn", "")
    if not pgn:
        return None

    url = raw_game.get("url", "")
    game_id = _game_id_from_url(source, url, pgn)
    white_data = raw_game.get("white", {})
    black_data = raw_game.get("black", {})

    default_white = (
        white_data.get("username") if isinstance(white_data, dict) else white_data
    )
    default_black = (
        black_data.get("username") if isinstance(black_data, dict) else black_data
    )
    default_white_elo = (
        str(white_data.get("rating"))
        if isinstance(white_data, dict) and white_data.get("rating")
        else None
    )
    default_black_elo = (
        str(black_data.get("rating"))
        if isinstance(black_data, dict) and black_data.get("rating")
        else None
    )

    (
        white,
        black,
        result,
        game_date,
        white_elo,
        black_elo,
        time_class,
        opening,
        move_count,
    ) = parse_pgn_headers(
        pgn,
        default_white,
        default_black,
        "*",
        default_date,
        default_white_elo,
        default_black_elo,
        raw_game.get("time_class") or raw_game.get("time_control"),
        raw_game.get("opening"),
    )

    if white_elo is not None:
        white_elo = str(white_elo)
    if black_elo is not None:
        black_elo = str(black_elo)

    return GameInfo(
        game_id=game_id,
        source=source,
        white=white or "?",
        black=black or "?",
        result=result,
        date=game_date,
        pgn=pgn,
        white_elo=white_elo,
        black_elo=black_elo,
        time_class=time_class,
        move_count=move_count,
        opening=opening,
    )


class ApiGameCache:
    def __init__(self, history_manager: GameHistoryManager):
        self.history_manager = history_manager

    def get_by_id(self, source: str, game_id: str, fetch_func: Callable) -> GameInfo | None:
        """Check cache first; miss → call fetch_func → save to cache → return"""
        cached = self.history_manager.get_cached_game(game_id, source)
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
            pgn,
            default_white,
            default_black,
            "*",
            "????.??.??",
            default_white_elo,
            default_black_elo,
            default_time_class,
            default_opening,
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
            opening=opening,
        )
        self.history_manager.save_cached_game(info)
        return info

    def get_by_date(
        self,
        source: str,
        username: str,
        date: datetime.date,
        fetch_func: Callable,
    ) -> list[GameInfo]:
        """Check cache first for (source, date, username); miss → call fetch_func → bulk-save → return"""
        date_str = date.strftime("%Y-%m-%d")
        cached_games = self.history_manager.get_cached_games_for_date(source, date_str, username)
        if cached_games and (
            date < datetime.date.today()
            or _cache_is_fresh(cached_games, _TODAY_CACHE_TTL_SECONDS)
        ):
            return cached_games

        raw_games = fetch_func()
        if not raw_games:
            return []

        game_infos = []
        for raw_game in raw_games:
            info = _to_game_info(source, raw_game, date_str)
            if info is not None:
                game_infos.append(info)

        if game_infos:
            self.history_manager.save_cached_games_bulk(game_infos)

        return game_infos

    def get_recent(
        self,
        source: str,
        username: str,
        limit: int,
        fetch_func: Callable,
    ) -> list[GameInfo]:
        """Always fetch fresh. Return list."""
        raw_games = fetch_func()
        if not raw_games:
            return []

        default_date = time.strftime("%Y-%m-%d")
        game_infos = []
        for raw_game in raw_games:
            info = _to_game_info(source, raw_game, default_date)
            if info is not None:
                game_infos.append(info)

        if game_infos:
            self.history_manager.save_cached_games_bulk(game_infos)

        return game_infos
