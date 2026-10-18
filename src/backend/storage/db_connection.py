"""
Database connection context manager with unified performance pragmas.
"""

import sqlite3
from collections.abc import Generator
from contextlib import contextmanager


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
