"""Read-only report of what the local database actually holds.

The Data & Storage page shows these numbers before a user wipes anything, so
the report must never create or mutate the database it inspects.
"""

from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from src.backend.storage.schema_constants import DATA_TABLES
from src.utils.logger import logger
from src.utils.path_utils import get_user_data_dir


@dataclass(frozen=True)
class StorageStats:
    """Byte sizes and row counts for the local data stores."""

    db_bytes: int
    wal_bytes: int
    openings_bytes: int
    games: int
    analyses: int
    explanations: int
    api_cached_games: int
    explorer_positions: int


def _default_db_path() -> str:
    return os.path.join(get_user_data_dir(), "analysis_cache.db")


def _default_openings_path() -> str:
    return os.path.join(get_user_data_dir(), "openings.db")


def _file_size(path: str) -> int:
    try:
        return os.path.getsize(path)
    except OSError:
        return 0


def _count_rows(conn: sqlite3.Connection, table: str) -> int:
    """Count a table, treating a missing table as empty.

    Older databases predate some cache tables, so a missing table must not
    turn the whole report into an error.
    """
    try:
        cursor = conn.execute(f"SELECT COUNT(*) FROM {table}")
        return int(cursor.fetchone()[0])
    except sqlite3.Error:
        return 0


def collect_storage_stats(
    db_path: str | None = None,
    openings_path: str | None = None,
) -> StorageStats:
    """Build a storage report without creating the database if it is absent."""
    db_path = db_path or _default_db_path()
    openings_path = openings_path or _default_openings_path()

    if not os.path.exists(db_path):
        return StorageStats(0, 0, _file_size(openings_path), 0, 0, 0, 0, 0)

    counts = dict.fromkeys(DATA_TABLES, 0)
    try:
        # Read-only URI: opening a missing file must not create an empty DB.
        uri = f"{Path(db_path).resolve().as_uri()}?mode=ro"
        conn = sqlite3.connect(uri, uri=True, timeout=5.0)
        try:
            # WAL readers need a shared lock; this keeps a concurrent analysis
            # from blocking the page for long.
            conn.execute("PRAGMA busy_timeout=2000")
            for table in DATA_TABLES:
                counts[table] = _count_rows(conn, table)
        finally:
            conn.close()
    except sqlite3.Error as e:
        logger.debug(f"Could not read storage stats: {e}")

    return StorageStats(
        db_bytes=_file_size(db_path),
        wal_bytes=_file_size(f"{db_path}-wal"),
        openings_bytes=_file_size(openings_path),
        games=counts["games"],
        analyses=counts["analysis"],
        explanations=counts["move_explanations"],
        api_cached_games=counts["api_game_cache"],
        explorer_positions=counts["explorer_cache"],
    )
