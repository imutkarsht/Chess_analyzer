import hashlib
import json
import sqlite3
import threading
import time
from typing import Any, Final

from src.constants import DEFAULT_MULTI_PV, EXPLANATION_CACHE_TTL_DAYS
from src.utils.logger import logger
from src.utils.path_utils import get_user_data_dir

# Single source of truth for the move_explanations schema: the DDL and the
# INSERT statement below are both derived from it, so they cannot drift apart.
_EXPLANATION_SCHEMA: Final[dict[str, str]] = {
    "id": "TEXT PRIMARY KEY",
    "fen_before": "TEXT",
    "move_uci": "TEXT",
    "model_name": "TEXT",
    "lang_code": "TEXT",
    "prompt_version": "TEXT",
    "explanation": "TEXT",
    "feedback": "INTEGER",
    "created_at": "INTEGER",
}
_EXPLANATION_INSERT: Final[str] = (
    f"INSERT OR REPLACE INTO move_explanations ({', '.join(_EXPLANATION_SCHEMA)}) "
    f"VALUES ({', '.join(':' + column for column in _EXPLANATION_SCHEMA)})"
)


class AnalysisCache:
    def __init__(self, db_path: str | None = None):
        if db_path is None:
            import os

            self.db_path = os.path.join(get_user_data_dir(), "analysis_cache.db")
        else:
            self.db_path = db_path
        self.conn = None
        self._lock = threading.Lock()
        self._ensure_connection()
        self._init_db()

    def _ensure_connection(self):
        if not hasattr(self, "conn") or self.conn is None:
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False, timeout=10.0)
            self.conn.execute("PRAGMA journal_mode=WAL")
            self.conn.execute("PRAGMA synchronous=NORMAL")
            self.conn.execute("PRAGMA busy_timeout=5000")

    def close(self):
        """Explicitly closes the database connection."""
        with self._lock:
            if hasattr(self, "conn") and self.conn is not None:
                try:
                    self.conn.close()
                except Exception:
                    pass
                self.conn = None

    def __enter__(self):
        self._ensure_connection()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def __del__(self):
        self.close()

    def _init_db(self):
        self._ensure_connection()
        cursor = self.conn.cursor()
        # Create table with depth column for depth-aware caching
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS analysis (
                id TEXT PRIMARY KEY,
                fen TEXT,
                engine_params TEXT,
                depth INTEGER DEFAULT 0,
                result TEXT
            )
        """)
        # Add depth column if it doesn't exist (migration for existing DBs)
        try:
            cursor.execute("ALTER TABLE analysis ADD COLUMN depth INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass  # Column already exists

        # Coach explanations live in the same DB but are never invalidated by
        # analysis changes, so they get their own table.
        columns = ", ".join(f"{name} {sql_type}" for name, sql_type in _EXPLANATION_SCHEMA.items())
        cursor.execute(f"CREATE TABLE IF NOT EXISTS move_explanations ({columns})")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_explanations_created ON move_explanations(created_at)"
        )
        self.conn.commit()

    def _generate_key(self, fen: str, multi_pv: int) -> str:
        """Generate cache key based on FEN and multi_pv only (not depth)."""
        key_str = f"{fen}|multipv:{multi_pv}"
        return hashlib.sha256(key_str.encode("utf-8")).hexdigest()

    def get_analysis(self, fen: str, engine_params: dict[str, Any]) -> Any | None:
        """
        Get cached analysis if it exists at sufficient depth.
        Returns cached result only if cached_depth >= requested_depth.
        """
        with self._lock:
            self._ensure_connection()
            requested_depth = engine_params.get("depth", 0) or 0
            multi_pv = engine_params.get("multi_pv", DEFAULT_MULTI_PV)
            key = self._generate_key(fen, multi_pv)

            cursor = self.conn.cursor()
            cursor.execute("SELECT result, depth FROM analysis WHERE id = ?", (key,))
            row = cursor.fetchone()

            if row:
                cached_result, cached_depth = row[0], row[1] or 0
                # Only return cached result if it was analyzed at equal or higher depth
                if cached_depth >= requested_depth:
                    return json.loads(cached_result)
            return None

    def save_analysis(self, fen: str, engine_params: dict[str, Any], result: Any):
        """
        Save analysis to cache. Overwrites if new depth is higher than cached depth.
        """
        with self._lock:
            self._ensure_connection()
            new_depth = engine_params.get("depth", 0) or 0
            multi_pv = engine_params.get("multi_pv", DEFAULT_MULTI_PV)
            key = self._generate_key(fen, multi_pv)

            cursor = self.conn.cursor()

            # Check existing depth
            cursor.execute("SELECT depth FROM analysis WHERE id = ?", (key,))
            row = cursor.fetchone()

            should_save = True
            if row:
                cached_depth = row[0] or 0
                # Only overwrite if new analysis is at higher depth
                if new_depth <= cached_depth:
                    should_save = False

            if should_save:
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO analysis (id, fen, engine_params, depth, result)
                    VALUES (?, ?, ?, ?, ?)
                """,
                    (
                        key,
                        fen,
                        json.dumps(engine_params, sort_keys=True),
                        new_depth,
                        json.dumps(result),
                    ),
                )
                self.conn.commit()

    # ------------------------------------------------------------------
    # Coach move explanations (Phase 1)
    # ------------------------------------------------------------------

    def _generate_explanation_key(
        self, fen: str, uci: str, model: str, lang_code: str, prompt_version: str | int
    ) -> str:
        """
        Cache key for an explanation (D7).

        Model and language are part of the key: a different model or a different
        UI language produces different prose for the same position.
        """
        key_str = f"{fen}|{uci}|{model}|{lang_code}|{prompt_version}"
        return hashlib.sha256(key_str.encode("utf-8")).hexdigest()

    def get_explanation(
        self,
        fen: str,
        uci: str,
        model: str,
        lang_code: str,
        prompt_version: str | int,
        max_age_days: int | None = EXPLANATION_CACHE_TTL_DAYS,
    ) -> str | None:
        """
        Return a cached explanation, or ``None`` on a miss.

        ``max_age_days=None`` disables the age check; ``0`` treats every entry as
        stale (equivalent to no caching).
        """
        key = self._generate_explanation_key(fen, uci, model, lang_code, prompt_version)
        try:
            with self._lock:
                self._ensure_connection()
                cursor = self.conn.cursor()
                cursor.execute(
                    "SELECT explanation, created_at FROM move_explanations WHERE id = ?", (key,)
                )
                row = cursor.fetchone()
                if not row:
                    return None
                explanation, created_at = row[0], row[1]
                if (
                    max_age_days is not None
                    and created_at is not None
                    and time.time() - created_at > max_age_days * 86400
                ):
                    cursor.execute("DELETE FROM move_explanations WHERE id = ?", (key,))
                    self.conn.commit()
                    return None
                return explanation or None
        except Exception as e:
            logger.debug(f"Failed to read cached explanation: {e}")
            return None

    def set_explanation(
        self,
        fen: str,
        uci: str,
        model: str,
        lang_code: str,
        prompt_version: str | int,
        explanation: str,
        max_age_days: int | None = EXPLANATION_CACHE_TTL_DAYS,
    ) -> None:
        """Store an explanation, pruning expired rows opportunistically first."""
        if not explanation:
            return
        self.prune_explanations(max_age_days)
        key = self._generate_explanation_key(fen, uci, model, lang_code, prompt_version)
        try:
            with self._lock:
                self._ensure_connection()
                cursor = self.conn.cursor()
                cursor.execute(
                    _EXPLANATION_INSERT,
                    {
                        "id": key,
                        "fen_before": fen,
                        "move_uci": uci,
                        "model_name": model,
                        "lang_code": lang_code,
                        "prompt_version": str(prompt_version),
                        "explanation": explanation,
                        "feedback": None,
                        "created_at": int(time.time()),
                    },
                )
                self.conn.commit()
        except Exception as e:
            logger.debug(f"Failed to cache explanation: {e}")

    def get_explanation_feedback(
        self,
        fen: str,
        uci: str,
        model: str,
        lang_code: str,
        prompt_version: str | int,
    ) -> int | None:
        """Return the stored 👍 (+1) / 👎 (-1) for an explanation, if any."""
        key = self._generate_explanation_key(fen, uci, model, lang_code, prompt_version)
        try:
            with self._lock:
                self._ensure_connection()
                cursor = self.conn.cursor()
                cursor.execute("SELECT feedback FROM move_explanations WHERE id = ?", (key,))
                row = cursor.fetchone()
                return row[0] if row else None
        except Exception as e:
            logger.debug(f"Failed to read explanation feedback: {e}")
            return None

    def set_explanation_feedback(
        self,
        fen: str,
        uci: str,
        model: str,
        lang_code: str,
        prompt_version: str | int,
        value: int | None,
    ) -> bool:
        """
        Record 👍 (+1) / 👎 (-1), or clear with ``None``.

        Returns ``True`` when an explanation row existed and was updated.
        """
        key = self._generate_explanation_key(fen, uci, model, lang_code, prompt_version)
        try:
            with self._lock:
                self._ensure_connection()
                cursor = self.conn.cursor()
                cursor.execute(
                    "UPDATE move_explanations SET feedback = ? WHERE id = ?", (value, key)
                )
                self.conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.debug(f"Failed to store explanation feedback: {e}")
            return False

    def prune_explanations(self, max_age_days: int | None = EXPLANATION_CACHE_TTL_DAYS) -> int:
        """Delete explanations older than ``max_age_days``; returns rows removed."""
        if max_age_days is None:
            return 0
        try:
            cutoff = int(time.time()) - max_age_days * 86400
            with self._lock:
                self._ensure_connection()
                cursor = self.conn.cursor()
                cursor.execute(
                    "DELETE FROM move_explanations WHERE created_at IS NOT NULL AND created_at < ?",
                    (cutoff,),
                )
                deleted = cursor.rowcount or 0
                self.conn.commit()
            if deleted > 0:
                logger.debug("Pruned %d expired move explanations.", deleted)
            return deleted
        except Exception as e:
            logger.debug(f"Failed to prune explanation cache: {e}")
            return 0

    def prune_cache(self, max_entries: int = 250_000) -> int:
        """Prunes oldest entries if analysis table exceeds max_entries."""
        try:
            with self._lock:
                self._ensure_connection()
                cursor = self.conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM analysis")
                total = cursor.fetchone()[0]
                if total > max_entries:
                    to_delete = total - max_entries
                    cursor.execute(
                        "DELETE FROM analysis WHERE rowid IN (SELECT rowid FROM analysis ORDER BY rowid ASC LIMIT ?)",
                        (to_delete,),
                    )
                    self.conn.commit()
                    logger.debug("Pruned %d excess analysis cache entries.", to_delete)
                    return to_delete
                return 0
        except Exception as e:
            logger.debug(f"Failed to prune analysis cache: {e}")
            return 0

    def clear_cache(self):
        """Clears all cached analysis and reclaims disk space via VACUUM."""
        try:
            with self._lock:
                self._ensure_connection()
                cursor = self.conn.cursor()
                cursor.execute("DELETE FROM analysis")
                cursor.execute("DELETE FROM move_explanations")
                self.conn.commit()
                try:
                    cursor.execute("VACUUM")
                except Exception:
                    pass
                logger.info("Analysis cache cleared and vacuumed")
        except Exception as e:
            logger.error(f"Failed to clear cache: {e}")
