"""
Repository for caching games fetched from external chess APIs (Chess.com, Lichess).
"""

import sqlite3
import time
from typing import Any

from src.backend.storage.db_connection import get_db_connection
from src.backend.storage.schema_constants import INSERT_API_CACHE_SQL
from src.utils.logger import logger


def _info_to_cache_row(info: Any, default_cached_at: str | None = None) -> tuple:
    cached_at = (
        getattr(info, "cached_at", None) or default_cached_at or time.strftime("%Y-%m-%d %H:%M:%S")
    )
    return (
        getattr(info, "game_id", ""),
        getattr(info, "source", ""),
        getattr(info, "white", ""),
        getattr(info, "black", ""),
        getattr(info, "result", "*"),
        getattr(info, "date", ""),
        getattr(info, "pgn", ""),
        getattr(info, "white_elo", None),
        getattr(info, "black_elo", None),
        getattr(info, "time_class", None),
        getattr(info, "move_count", None),
        getattr(info, "opening", None),
        cached_at,
    )


def _row_to_game_info(d: dict[str, Any]) -> Any:
    from src.backend.models.game_info import GameInfo

    return GameInfo(
        game_id=d["id"],
        source=d["source"],
        white=d["white"],
        black=d["black"],
        result=d["result"],
        date=d["date"],
        pgn=d["pgn"],
        white_elo=d.get("white_elo"),
        black_elo=d.get("black_elo"),
        time_class=d.get("time_class"),
        move_count=d.get("move_count"),
        opening=d.get("opening"),
        cached_at=d.get("cached_at"),
    )


class ApiCacheRepo:
    """Manages local caching of API-imported games to prevent redundant network fetches."""

    def __init__(self, db_path: str):
        self.db_path = db_path

    def _get_connection(self):
        return get_db_connection(self.db_path)

    def save_cached_game(self, info: Any) -> None:
        """Saves a single GameInfo to the api_game_cache table."""
        self.save_cached_games_bulk([info])

    def save_cached_games_bulk(self, games: list[Any]) -> None:
        """Saves multiple GameInfo objects inside a single database transaction."""
        if not games:
            return
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                now_str = time.strftime("%Y-%m-%d %H:%M:%S")
                rows = [_info_to_cache_row(g, default_cached_at=now_str) for g in games]
                cursor.executemany(INSERT_API_CACHE_SQL, rows)
                conn.commit()
            logger.debug("Saved %d games to API cache", len(games))
        except Exception as e:
            logger.error("Failed to save cached games bulk: %s", e)

    def get_cached_game(self, game_id: str) -> Any | None:
        """Retrieves a single GameInfo object from cache by its ID."""
        try:
            with self._get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM api_game_cache WHERE id = ?", (game_id,))
                row = cursor.fetchone()
                if row:
                    return _row_to_game_info(dict(row))
            return None
        except Exception as e:
            logger.error("Failed to get cached game %s: %s", game_id, e)
            return None

    def get_cached_games_for_date(self, source: str, date: str, username: str) -> list[Any]:
        """Retrieves cached games matching source, date, and containing username (case-insensitive)."""
        try:
            with self._get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT * FROM api_game_cache
                    WHERE source = ? AND date = ?
                      AND (LOWER(white) = ? OR LOWER(black) = ?)
                    """,
                    (source, date, username.lower(), username.lower()),
                )
                return [_row_to_game_info(dict(r)) for r in cursor.fetchall()]
        except Exception as e:
            logger.error("Failed to get cached games for date %s: %s", date, e)
            return []

    def clear_api_cache(self) -> None:
        """Clears all games from the API cache and reclaims disk space via VACUUM."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM api_game_cache")
                conn.commit()
                cursor.execute("VACUUM")
            logger.info("API game cache cleared and database vacuumed.")
        except Exception as e:
            logger.error("Failed to clear API game cache: %s", e)

