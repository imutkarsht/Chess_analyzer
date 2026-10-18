"""
Repository for opening explorer cache persistence and pruning.
"""

import sqlite3
import time
from typing import Any

from src.backend.storage.db_connection import get_db_connection
from src.backend.storage.schema_constants import EXPLORER_CACHE_TTL_SECONDS
from src.utils.logger import logger


class ExplorerCacheRepo:
    """Manages opening explorer cache storage, time-to-live expiration, and pruning."""

    def __init__(self, db_path: str):
        self.db_path = db_path

    def _get_connection(self):
        return get_db_connection(self.db_path)

    @staticmethod
    def _parse_cached_at_to_epoch(cached_at: Any) -> float:
        if isinstance(cached_at, (int, float)):
            return float(cached_at)
        try:
            return float(cached_at)
        except (ValueError, TypeError):
            pass
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
            try:
                return time.mktime(time.strptime(str(cached_at), fmt))
            except Exception:
                pass
        return 0.0

    def save_explorer_cache(self, fen: str, response_json: str) -> None:
        """Saves a Lichess explorer response json for a given FEN."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO explorer_cache (fen, response_json, cached_at)
                    VALUES (?, ?, ?)
                    """,
                    (fen, response_json, time.time()),
                )
                conn.commit()
        except Exception as e:
            logger.error("Failed to save explorer cache: %s", e)

    def prune_explorer_cache(self, cursor: sqlite3.Cursor | None = None) -> int:
        """Prunes cached opening explorer responses older than EXPLORER_CACHE_TTL_SECONDS."""
        try:
            cutoff = time.time() - EXPLORER_CACHE_TTL_SECONDS
            cutoff_iso = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(cutoff))
            prune_sql = (
                "DELETE FROM explorer_cache WHERE "
                "(typeof(cached_at) IN ('integer', 'real') AND cached_at < ?) "
                "OR (typeof(cached_at) = 'text' AND cached_at < ?)"
            )
            if cursor is not None:
                cursor.execute(prune_sql, (cutoff, cutoff_iso))
                return cursor.rowcount
            with self._get_connection() as conn:
                cur = conn.cursor()
                cur.execute(prune_sql, (cutoff, cutoff_iso))
                pruned = cur.rowcount
                conn.commit()
                if pruned > 0:
                    logger.debug("Pruned %d expired explorer cache entries.", pruned)
                return pruned
        except Exception as e:
            logger.debug("Failed to prune explorer cache: %s", e)
            return 0

    def get_explorer_cache(self, fen: str) -> str | None:
        """Retrieves a cached explorer response json by FEN, deleting expired entries."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT response_json, cached_at FROM explorer_cache WHERE fen = ?", (fen,)
                )
                row = cursor.fetchone()
                if row:
                    response_json, cached_at = row
                    cached_epoch = self._parse_cached_at_to_epoch(cached_at)
                    if time.time() - cached_epoch < EXPLORER_CACHE_TTL_SECONDS:
                        return response_json
                    else:
                        cursor.execute("DELETE FROM explorer_cache WHERE fen = ?", (fen,))
                        conn.commit()
            return None
        except Exception as e:
            logger.error("Failed to get explorer cache: %s", e)
            return None

