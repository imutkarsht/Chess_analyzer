"""
Repository for caching games fetched from external chess APIs (Chess.com, Lichess).
"""

import sqlite3
from typing import Any

from src.backend.storage.cache_time import now_iso
from src.backend.storage.db_connection import get_db_connection
from src.backend.storage.schema_constants import (
    API_CACHE_COLUMNS,
    INSERT_API_CACHE_SQL,
)
from src.utils.logger import logger


def _info_to_cache_row(info: Any, default_cached_at: str | None = None) -> tuple:
    row = info.to_dict()
    row["id"] = row.pop("game_id")
    row["cached_at"] = row.get("cached_at") or default_cached_at or now_iso()
    return tuple(row[column] for column in API_CACHE_COLUMNS)


def _row_to_game_info(d: dict[str, Any]) -> Any:
    from src.backend.models.game_info import GameInfo

    row = dict(d)
    row["game_id"] = row.get("id", "")
    return GameInfo.from_dict(row)


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
                now_str = now_iso()
                rows = [_info_to_cache_row(g, default_cached_at=now_str) for g in games]
                cursor.executemany(INSERT_API_CACHE_SQL, rows)
                conn.commit()
            logger.debug("Saved %d games to API cache", len(games))
        except Exception as e:
            logger.error("Failed to save cached games bulk: %s", e)

    def get_cached_game(self, game_id: str, source: str | None = None) -> Any | None:
        """Retrieves a single GameInfo object from cache by its ID.

        ``source`` distinguishes platforms that could theoretically share an ID.
        """
        try:
            with self._get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                if source:
                    cursor.execute(
                        "SELECT * FROM api_game_cache WHERE id = ? AND source = ?",
                        (game_id, source),
                    )
                else:
                    cursor.execute(
                        "SELECT * FROM api_game_cache WHERE id = ?", (game_id,)
                    )
                row = cursor.fetchone()
                if row:
                    return _row_to_game_info(dict(row))
            return None
        except Exception as e:
            logger.error("Failed to get cached game %s: %s", game_id, e)
            return None

    def get_cached_games_for_date(self, source: str, date: str, username: str) -> list[Any]:
        """Retrieves cached games matching source, date, and containing username.

        ``rowid`` preserves the order the API returned the games in when they
        were cached; the table has no separate played-time column.
        """
        try:
            with self._get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT * FROM api_game_cache
                    WHERE source = ? AND date = ?
                      AND (LOWER(white) = ? OR LOWER(black) = ?)
                    ORDER BY rowid ASC
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

