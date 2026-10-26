"""Backup and restore of the local SQLite database.

Backups are consistent snapshots taken with SQLite's online backup API, so a
running WAL writer cannot produce a half-written file. Restores validate the
source first and always leave a pre-restore safety copy behind.
"""

from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from src.backend.storage import migrations
from src.backend.storage.schema_constants import CURRENT_SCHEMA_VERSION
from src.utils.logger import logger
from src.utils.path_utils import get_user_data_dir

_SQLITE_HEADER = b"SQLite format 3\x00"
# A valid restore must contain the game history; cache tables are optional
# because older backups predate some of them.
_REQUIRED_TABLE = "games"
# Guards against accepting an unrelated SQLite file that happens to have a
# "games" table. Every released schema has had these columns.
_REQUIRED_GAME_COLUMNS = ("id", "white", "black", "result")


class BackupError(Exception):
    """A backup could not be written, or a restore could not be completed."""


class BackupValidationError(BackupError):
    """The selected file is not a usable Chess Analyzer backup."""


@dataclass(frozen=True)
class BackupSummary:
    """Metadata shown in the UI before and after backup/restore."""

    path: str
    size_bytes: int
    games: int
    analyses: int
    explanations: int
    schema_version: int
    created_at: float


def default_db_path() -> str:
    return os.path.join(get_user_data_dir(), "analysis_cache.db")


def default_backup_name() -> str:
    return f"chess-analyzer-backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}.db"


def _default_backup_dir() -> str:
    """Start the save dialog in Documents when it exists, else the home folder."""
    documents = os.path.join(os.path.expanduser("~"), "Documents")
    return documents if os.path.isdir(documents) else os.path.expanduser("~")


def default_backup_path() -> str:
    return os.path.join(_default_backup_dir(), default_backup_name())


def _readonly_connection(path: str) -> sqlite3.Connection:
    uri = f"{Path(path).resolve().as_uri()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True, timeout=5.0)
    conn.execute("PRAGMA busy_timeout=2000")
    return conn


def _count(conn: sqlite3.Connection, table: str) -> int:
    try:
        return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
    except sqlite3.Error:
        return 0


def _validate_game_history(conn: sqlite3.Connection) -> None:
    """Require a real game-history table, not just a same-named one."""
    try:
        rows = conn.execute(f"PRAGMA table_info({_REQUIRED_TABLE})").fetchall()
    except sqlite3.Error as e:
        raise BackupValidationError(
            "The selected file is not a Chess Analyzer backup (no game history found)."
        ) from e
    columns = {row[1] for row in rows}
    if not columns:
        raise BackupValidationError(
            "The selected file is not a Chess Analyzer backup (no game history found)."
        )
    missing = [column for column in _REQUIRED_GAME_COLUMNS if column not in columns]
    if missing:
        raise BackupValidationError(
            "The selected file is not a Chess Analyzer backup "
            f"(game history is missing {', '.join(missing)})."
        )


def inspect_backup(path: str) -> BackupSummary:
    """Validate a backup file and return its contents.

    Raises :class:`BackupValidationError` with a user-facing message when the
    file cannot safely be restored.
    """
    if not path or not os.path.isfile(path):
        raise BackupValidationError("The selected file does not exist.")
    size = os.path.getsize(path)
    if size == 0:
        raise BackupValidationError("The selected file is empty.")

    try:
        with open(path, "rb") as handle:
            header = handle.read(len(_SQLITE_HEADER))
    except OSError as e:
        raise BackupValidationError(f"The selected file cannot be read: {e}") from e
    if header != _SQLITE_HEADER:
        raise BackupValidationError("The selected file is not a SQLite database.")

    try:
        conn = _readonly_connection(path)
        try:
            integrity = conn.execute("PRAGMA integrity_check").fetchone()
            if not integrity or integrity[0] != "ok":
                reason = integrity[0] if integrity else "unknown error"
                raise BackupValidationError(f"The backup is damaged: {reason}")

            schema_version = int(conn.execute("PRAGMA user_version").fetchone()[0])
            if schema_version > CURRENT_SCHEMA_VERSION:
                raise BackupValidationError(
                    "This backup was created by a newer version of Chess Analyzer. "
                    "Update the app before restoring it."
                )

            try:
                conn.execute(f"SELECT 1 FROM {_REQUIRED_TABLE} LIMIT 1")
            except sqlite3.Error as e:
                raise BackupValidationError(
                    "The selected file is not a Chess Analyzer backup "
                    "(no game history found)."
                ) from e
            _validate_game_history(conn)

            games = _count(conn, "games")
            analyses = _count(conn, "analysis")
            explanations = _count(conn, "move_explanations")
        finally:
            conn.close()
    except BackupValidationError:
        raise
    except sqlite3.Error as e:
        raise BackupValidationError(f"The selected file is not a valid backup: {e}") from e

    return BackupSummary(
        path=os.path.abspath(path),
        size_bytes=size,
        games=games,
        analyses=analyses,
        explanations=explanations,
        schema_version=schema_version,
        created_at=os.path.getmtime(path),
    )


def _copy_database(source_path: str, destination_path: str) -> None:
    """Copy a database atomically-enough through SQLite's backup API."""
    source = sqlite3.connect(source_path, timeout=10.0)
    try:
        destination = sqlite3.connect(destination_path, timeout=10.0)
        try:
            source.backup(destination)
            # Fold the restored pages back into the main file so a stale
            # sidecar WAL cannot resurrect pre-restore data.
            destination.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            destination.commit()
        finally:
            destination.close()
    finally:
        source.close()


def create_backup(destination: str, db_path: str | None = None) -> BackupSummary:
    """Write a consistent snapshot of the local database to ``destination``."""
    db_path = db_path or default_db_path()
    if not os.path.exists(db_path) or os.path.getsize(db_path) == 0:
        raise BackupError("There is no local data to back up yet.")

    destination = os.path.abspath(destination)
    if os.path.abspath(db_path) == destination:
        raise BackupError("Choose a different file; the backup cannot replace the live database.")
    if not os.path.isdir(os.path.dirname(destination)):
        raise BackupError("The selected folder does not exist.")

    try:
        _copy_database(db_path, destination)
    except (OSError, sqlite3.Error) as e:
        logger.error(f"Backup failed: {e}")
        raise BackupError(f"Backup failed: {e}") from e

    summary = inspect_backup(destination)
    logger.info(
        f"Backup written to {summary.path} ({summary.games} games, {summary.size_bytes} bytes)."
    )
    return summary


def restore_backup(source: str, db_path: str | None = None) -> BackupSummary:
    """Replace the live database with ``source`` after validating it."""
    db_path = db_path or default_db_path()
    if os.path.abspath(source) == os.path.abspath(db_path):
        raise BackupValidationError("The selected file is the live database.")

    # Validate immediately before use: the file may have changed since the
    # confirmation dialog was shown.
    inspect_backup(source)

    if os.path.exists(db_path) and os.path.getsize(db_path) > 0:
        safety_path = os.path.splitext(db_path)[0] + ".pre-restore.db"
        try:
            _copy_database(db_path, safety_path)
            logger.info(f"Pre-restore safety copy written to {safety_path}")
        except (OSError, sqlite3.Error) as e:
            logger.warning(f"Could not write pre-restore safety copy: {e}")

    try:
        _copy_database(source, db_path)
    except (OSError, sqlite3.Error) as e:
        logger.error(f"Restore failed: {e}")
        raise BackupError(f"Restore failed: {e}") from e

    # Older backups are upgraded in place so the app can read them.
    migrations.init_db(db_path)
    try:
        summary = inspect_backup(db_path)
    except BackupValidationError as e:
        raise BackupError(
            f"The restored database could not be upgraded: {e} "
            "Your previous data is still available in the pre-restore safety copy."
        ) from e
    if summary.schema_version != CURRENT_SCHEMA_VERSION:
        raise BackupError(
            "The restored database could not be upgraded to the current schema. "
            "Your previous data is still available in the pre-restore safety copy."
        )
    logger.info(f"Database restored from {summary.path} ({summary.games} games).")
    return summary
