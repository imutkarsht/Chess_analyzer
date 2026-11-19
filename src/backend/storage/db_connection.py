"""
Database connection context manager with unified performance pragmas.
"""

import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def get_db_connection(db_path: str) -> Generator[sqlite3.Connection, None, None]:
    """
    Context manager guaranteeing connection closure upon completion or error.
    Standardizes on WAL mode, normal synchronous, and 10-second busy timeout.
    """
    conn = sqlite3.connect(db_path, timeout=10.0)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA busy_timeout=10000")
        yield conn
    finally:
        try:
            conn.close()
        except Exception:
            pass


@contextmanager
def get_readonly_connection(
    db_path: str,
    *,
    timeout: float = 5.0,
) -> Generator[sqlite3.Connection, None, None]:
    """Open an existing database read-only without creating a missing file."""
    uri = f"{Path(db_path).resolve().as_uri()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True, timeout=timeout)
    try:
        conn.execute("PRAGMA busy_timeout=2000")
        yield conn
    finally:
        conn.close()


def count_rows(conn: sqlite3.Connection, table: str) -> int:
    """Count a table, treating a missing table as empty."""
    try:
        return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
    except sqlite3.Error:
        return 0
