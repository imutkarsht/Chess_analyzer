"""
Repository for opening explorer cache persistence and pruning.
"""

import sqlite3
import time
from typing import Any

from src.backend.storage.db_connection import get_db_connection
from src.backend.storage.schema_constants import EXPLORER_CACHE_TTL_SECONDS
from src.constants import DEFAULT_EXPLORER_CACHE_TTL_HOURS
from src.utils.logger import logger

# Distinguishes "use the user setting" from an explicit None ("never expire").
_UNSET = object()


class ExplorerCacheRepo:
    """Manages opening explorer cache storage, time-to-live expiration, and pruning."""

    def __init__(self, db_path: str, ttl_seconds: float | None | object = _UNSET):
        self.db_path = db_path
        self._ttl_override = ttl_seconds

    def _get_connection(self):
        return get_db_connection(self.db_path)

    def _ttl_seconds(self) -> float | None:
        """Resolve the TTL: explicit override, else the saved user setting."""
        if self._ttl_override is not _UNSET:
            return self._ttl_override

        from src.utils.config import ConfigManager

        hours = ConfigManager().get(
            "explorer_cache_ttl_hours", DEFAULT_EXPLORER_CACHE_TTL_HOURS
        )
        if hours is None:
            return None
        try:
            return max(1, int(hours)) * 3600.0
        except (TypeError, ValueError):
            return EXPLORER_CACHE_TTL_SECONDS

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
        """Prunes cached opening explorer responses older than the configured TTL."""
        ttl_seconds = self._ttl_seconds()
        if ttl_seconds is None:
            return 0
        try:
            cutoff = time.time() - ttl_seconds

            def _prune(cur: sqlite3.Cursor) -> int:
                # REAL/INTEGER timestamps are safe to compare in SQL.
                cur.execute(
                    "DELETE FROM explorer_cache WHERE "
                    "typeof(cached_at) IN ('integer', 'real') AND cached_at < ?",
                    (cutoff,),
                )
                pruned = cur.rowcount
                # Legacy databases declared cached_at as TEXT, so a numeric
                # epoch can be persisted as a string. Parsing it avoids the
                # lexicographic trap where every fresh "1793…" sorts before
                # an ISO cutoff like "2026…".
                rows = cur.execute(
                    "SELECT fen, cached_at FROM explorer_cache "
                    "WHERE typeof(cached_at) = 'text'"
                ).fetchall()
                expired = [
                    fen
                    for fen, cached_at in rows
                    if self._parse_cached_at_to_epoch(cached_at) < cutoff
                ]
                if expired:
                    cur.executemany(
                        "DELETE FROM explorer_cache WHERE fen = ?",
                        [(fen,) for fen in expired],
                    )
                return pruned + len(expired)

            if cursor is not None:
                return _prune(cursor)

            with self._get_connection() as conn:
                cur = conn.cursor()
                pruned = _prune(cur)
                conn.commit()
                if pruned:
                    logger.debug(
                        "Pruned %d expired explorer cache entries.", pruned
                    )
                return pruned
        except Exception as e:
            logger.debug("Failed to prune explorer cache: %s", e)
            return 0

    def get_explorer_cache(self, fen: str) -> str | None:
        """Retrieves a cached explorer response json by FEN, deleting expired entries."""
        ttl_seconds = self._ttl_seconds()
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT response_json, cached_at FROM explorer_cache WHERE fen = ?", (fen,)
                )
                row = cursor.fetchone()
                if row:
                    response_json, cached_at = row
                    if ttl_seconds is None:
                        return response_json
                    cached_epoch = self._parse_cached_at_to_epoch(cached_at)
                    if time.time() - cached_epoch < ttl_seconds:
                        return response_json
                    else:
                        cursor.execute("DELETE FROM explorer_cache WHERE fen = ?", (fen,))
                        conn.commit()
            return None
        except Exception as e:
            logger.error("Failed to get explorer cache: %s", e)
            return None

    def clear_explorer_cache(self) -> int:
        """Delete every cached explorer response and reclaim the freed space."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM explorer_cache")
                total = int(cursor.fetchone()[0])
                cursor.execute("DELETE FROM explorer_cache")
                conn.commit()
                try:
                    cursor.execute("VACUUM")
                except sqlite3.Error:
                    # The rows are already gone; space reclamation is best-effort.
                    pass
            return total
        except Exception as e:
            logger.error("Failed to clear explorer cache: %s", e)
            return 0

