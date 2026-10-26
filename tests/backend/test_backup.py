"""Backup and restore of the local SQLite store."""

import sqlite3

import pytest

from src.backend.storage.backup import (
    BackupError,
    BackupValidationError,
    create_backup,
    inspect_backup,
    restore_backup,
)
from src.backend.storage.game_history import GameHistoryManager
from src.backend.storage.models import GameAnalysis, GameMetadata
from src.backend.storage.schema_constants import CURRENT_SCHEMA_VERSION


def _game(game_id: str) -> GameAnalysis:
    return GameAnalysis(
        game_id=game_id,
        metadata=GameMetadata(white="White", black="Black", result="1-0"),
        pgn_content="1. e4 e5 1-0",
    )


def _live_db(tmp_path, *game_ids: str) -> str:
    db_path = str(tmp_path / "live.db")
    manager = GameHistoryManager(db_path)
    for game_id in game_ids:
        manager.save_game(_game(game_id), "1. e4 e5 1-0")
    return db_path


def test_backup_round_trip_restores_the_original_rows(tmp_path):
    db_path = _live_db(tmp_path, "game_a")
    backup_path = str(tmp_path / "backup.db")

    created = create_backup(backup_path, db_path)
    assert created.games == 1
    assert created.schema_version == CURRENT_SCHEMA_VERSION

    # Mutate the live database after the snapshot was taken.
    GameHistoryManager(db_path).save_game(_game("game_b"), "1. e4 e5 1-0")
    assert len(GameHistoryManager(db_path).get_all_games()) == 2

    restored = restore_backup(backup_path, db_path)

    assert restored.games == 1
    assert [g["id"] for g in GameHistoryManager(db_path).get_all_games()] == ["game_a"]
    assert (tmp_path / "live.pre-restore.db").is_file(), "restore must keep a safety copy"


def test_backup_refuses_when_there_is_no_local_data(tmp_path):
    with pytest.raises(BackupError, match="no local data"):
        create_backup(str(tmp_path / "backup.db"), str(tmp_path / "missing.db"))


def test_backup_refuses_to_overwrite_the_live_database(tmp_path):
    db_path = _live_db(tmp_path, "game_a")

    with pytest.raises(BackupError, match="different file"):
        create_backup(db_path, db_path)


def test_restore_upgrades_a_backup_written_by_an_older_schema(tmp_path):
    legacy_path = tmp_path / "legacy.db"
    with sqlite3.connect(legacy_path) as conn:
        # The v0 schema predates every cache table and the accuracy columns.
        conn.execute(
            """
            CREATE TABLE games (
                id TEXT PRIMARY KEY,
                white TEXT,
                black TEXT,
                result TEXT,
                date TEXT,
                event TEXT,
                pgn TEXT,
                summary_json TEXT,
                timestamp REAL
            )
            """
        )
        conn.execute(
            "INSERT INTO games (id, white, black, result) VALUES ('old', 'A', 'B', '1-0')"
        )
        conn.commit()

    db_path = str(tmp_path / "live.db")
    GameHistoryManager(db_path)

    restored = restore_backup(str(legacy_path), db_path)

    assert restored.schema_version == CURRENT_SCHEMA_VERSION
    assert GameHistoryManager(db_path).game_exists("old")


@pytest.mark.parametrize(
    ("filename", "contents", "message"),
    [
        ("missing.db", None, "does not exist"),
        ("empty.db", b"", "empty"),
        ("notes.db", b"just some text", "not a SQLite database"),
    ],
)
def test_inspect_rejects_unusable_files(tmp_path, filename, contents, message):
    path = tmp_path / filename
    if contents is not None:
        path.write_bytes(contents)

    with pytest.raises(BackupValidationError, match=message):
        inspect_backup(str(path))


def test_inspect_rejects_a_database_without_game_history(tmp_path):
    path = tmp_path / "other.db"
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE notes (id INTEGER PRIMARY KEY)")
        conn.commit()

    with pytest.raises(BackupValidationError, match="not a Chess Analyzer backup"):
        inspect_backup(str(path))


def test_inspect_rejects_a_games_table_with_foreign_columns(tmp_path):
    """A same-named table from another app must not pass as game history."""
    path = tmp_path / "unrelated.db"
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE games (title TEXT, score INTEGER)")
        conn.commit()

    with pytest.raises(BackupValidationError, match="missing"):
        inspect_backup(str(path))


def test_inspect_rejects_a_backup_from_a_newer_app_version(tmp_path):
    path = tmp_path / "future.db"
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE games (id TEXT PRIMARY KEY)")
        conn.execute(f"PRAGMA user_version = {CURRENT_SCHEMA_VERSION + 1}")
        conn.commit()

    with pytest.raises(BackupValidationError, match="newer version"):
        inspect_backup(str(path))
