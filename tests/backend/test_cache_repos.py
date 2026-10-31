"""Tests for cache repository error handling, TTL overrides, and cleanup."""

import sqlite3
import time

import pytest

from src.backend.models.game_info import GameInfo
from src.backend.storage.api_cache_repo import ApiCacheRepo
from src.backend.storage.explorer_cache_repo import ExplorerCacheRepo
from src.backend.storage.game_history import GameHistoryManager
from src.backend.storage.profile_cache_repo import ProfileCacheRepo


@pytest.fixture
def manager(tmp_path):
    return GameHistoryManager(str(tmp_path / "history.db"))


def _game(game_id="g1", source="lichess", white="Alice", black="Bob", date="2024-05-01"):
    return GameInfo(
        game_id=game_id,
        source=source,
        white=white,
        black=black,
        result="1-0",
        date=date,
        pgn="1. e4 1-0",
    )


# ── Explorer cache ──────────────────────────────────────────────────────

class TestExplorerCache:
    def test_clear_removes_all_entries(self, manager):
        manager.save_explorer_cache("fen-1", '{"moves": []}')
        manager.save_explorer_cache("fen-2", '{"moves": [1]}')
        repo = ExplorerCacheRepo(manager.db_path, ttl_seconds=3600)

        assert repo.clear_explorer_cache() == 2
        assert repo.get_explorer_cache("fen-1") is None
        assert repo.clear_explorer_cache() == 0

    def test_prune_accepts_external_cursor(self, manager):
        manager.save_explorer_cache("fen", "{}")
        with sqlite3.connect(manager.db_path) as conn:
            conn.execute(
                "UPDATE explorer_cache SET cached_at = ? WHERE fen = ?",
                (time.time() - 200_000.0, "fen"),
            )
            cursor = conn.cursor()
            repo = ExplorerCacheRepo(manager.db_path, ttl_seconds=3600)

            assert repo.prune_explorer_cache(cursor=cursor) == 1
            conn.commit()

    def test_prune_keeps_fresh_numeric_text_timestamps(self, tmp_path):
        """Legacy TEXT-affinity tables must not lose fresh epoch values.

        SQLite stores ``time.time()`` as a numeric string in a TEXT column, and
        comparing that string against an ISO cutoff sorts every fresh entry
        before the cutoff. Pruning now parses the timestamp instead.
        """
        db_path = str(tmp_path / "legacy-explorer.db")
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                """
                CREATE TABLE explorer_cache (
                    fen TEXT PRIMARY KEY,
                    response_json TEXT NOT NULL,
                    cached_at TEXT NOT NULL
                )
                """
            )
            conn.commit()

        manager = GameHistoryManager(db_path)
        manager.save_explorer_cache("fen", "{}")
        with sqlite3.connect(db_path) as conn:
            stored = conn.execute(
                "SELECT cached_at FROM explorer_cache WHERE fen = 'fen'"
            ).fetchone()[0]
        assert isinstance(stored, str)

        # A fresh manager runs the startup prune; the entry must survive.
        assert GameHistoryManager(db_path).get_explorer_cache("fen") == "{}"

        # An old numeric string is still expired normally.
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                "UPDATE explorer_cache SET cached_at = ? WHERE fen = ?",
                (str(time.time() - 200_000.0), "fen"),
            )
            conn.commit()
        repo = ExplorerCacheRepo(db_path, ttl_seconds=3600)
        assert repo.prune_explorer_cache() == 1

    def test_configured_ttl_none_never_expires(self, manager, mocker):
        manager.save_explorer_cache("fen", "{}")
        with sqlite3.connect(manager.db_path) as conn:
            conn.execute(
                "UPDATE explorer_cache SET cached_at = ? WHERE fen = ?",
                (time.time() - 10 * 365 * 86400, "fen"),
            )
            conn.commit()
        mocker.patch("src.utils.config.ConfigManager.get", return_value=None)
        repo = ExplorerCacheRepo(manager.db_path)

        assert repo.get_explorer_cache("fen") == "{}"

    @pytest.mark.parametrize("configured", ["not-a-number", 0])
    def test_configured_ttl_falls_back_to_default(self, manager, mocker, configured):
        manager.save_explorer_cache("fen", "{}")
        mocker.patch("src.utils.config.ConfigManager.get", return_value=configured)
        repo = ExplorerCacheRepo(manager.db_path)

        assert repo.get_explorer_cache("fen") == "{}"

    def test_storage_failures_are_swallowed(self, tmp_path):
        invalid_db = str(tmp_path)  # a directory, not a database file
        repo = ExplorerCacheRepo(invalid_db, ttl_seconds=60)

        repo.save_explorer_cache("fen", "{}")

        assert repo.get_explorer_cache("fen") is None
        assert repo.prune_explorer_cache() == 0
        assert repo.clear_explorer_cache() == 0


# ── Profile cache ───────────────────────────────────────────────────────

class TestProfileCacheDefensivePaths:
    def test_blank_username_is_ignored(self, manager):
        repo = ProfileCacheRepo(manager.db_path, ttl_seconds=None)

        repo.save_profile("lichess", "   ", {"username": "ghost"})

        assert repo.get_profile("lichess", "   ") is None

    def test_corrupt_payload_is_discarded(self, manager):
        repo = ProfileCacheRepo(manager.db_path, ttl_seconds=None)
        repo.save_profile("lichess", "Alice", {"username": "Alice"})
        with sqlite3.connect(manager.db_path) as conn:
            conn.execute(
                "UPDATE api_profile_cache SET payload_json = 'not json' WHERE username_key = 'alice'"
            )
            conn.commit()

        assert repo.get_profile("lichess", "Alice") is None

    def test_non_object_payload_is_discarded(self, manager):
        repo = ProfileCacheRepo(manager.db_path, ttl_seconds=None)
        repo.save_profile("lichess", "Alice", {"username": "Alice"})
        with sqlite3.connect(manager.db_path) as conn:
            conn.execute(
                "UPDATE api_profile_cache SET payload_json = '[1, 2]' WHERE username_key = 'alice'"
            )
            conn.commit()

        assert repo.get_profile("lichess", "Alice") is None

    def test_invalid_fetched_at_is_treated_as_epoch(self, manager):
        repo = ProfileCacheRepo(manager.db_path, ttl_seconds=3600)
        repo.save_profile("lichess", "Alice", {"username": "Alice"})
        with sqlite3.connect(manager.db_path) as conn:
            conn.execute(
                "UPDATE api_profile_cache SET fetched_at = 'broken' WHERE username_key = 'alice'"
            )
            conn.commit()

        cached = repo.get_profile("lichess", "Alice")

        assert cached.fetched_at == 0.0
        assert cached.is_stale is True

    def test_unserializable_profile_is_not_saved(self, manager):
        repo = ProfileCacheRepo(manager.db_path, ttl_seconds=None)

        repo.save_profile("lichess", "Alice", {"bad": object()})

        assert repo.get_profile("lichess", "Alice") is None

    def test_configured_ttl_none_never_marks_stale(self, manager, mocker):
        repo = ProfileCacheRepo(manager.db_path, ttl_seconds=1)
        repo.save_profile("lichess", "Alice", {"username": "Alice"})
        with sqlite3.connect(manager.db_path) as conn:
            conn.execute("UPDATE api_profile_cache SET fetched_at = 0")
            conn.commit()
        mocker.patch("src.utils.config.ConfigManager.get", return_value=None)

        cached = ProfileCacheRepo(manager.db_path).get_profile("lichess", "Alice")

        assert cached.is_stale is False

    @pytest.mark.parametrize("configured", ["broken", 0])
    def test_invalid_configured_ttl_uses_default(self, manager, mocker, configured):
        repo = ProfileCacheRepo(manager.db_path, ttl_seconds=1)
        repo.save_profile("lichess", "Alice", {"username": "Alice"})
        mocker.patch("src.utils.config.ConfigManager.get", return_value=configured)

        assert ProfileCacheRepo(manager.db_path).get_profile("lichess", "Alice") is not None

    def test_prune_and_clear_failures_return_zero(self, tmp_path):
        repo = ProfileCacheRepo(str(tmp_path), ttl_seconds=None)

        assert repo.get_profile("lichess", "Alice") is None
        assert repo.prune_profile_cache() == 0
        assert repo.clear_profile_cache() == 0
        repo.save_profile("lichess", "Alice", {"username": "Alice"})

    def test_auto_prune_is_throttled(self, manager, mocker):
        repo = ProfileCacheRepo(manager.db_path, ttl_seconds=None)
        prune = mocker.patch.object(repo, "prune_profile_cache")
        mocker.patch.object(ProfileCacheRepo, "_last_prune", time.time())

        repo.save_profile("lichess", "Alice", {"username": "Alice"})
        prune.assert_not_called()

        mocker.patch.object(ProfileCacheRepo, "_last_prune", 0.0)
        repo.save_profile("lichess", "Bob", {"username": "Bob"})
        prune.assert_called_once()


# ── API game cache ──────────────────────────────────────────────────────

class TestApiCacheRepo:
    def test_round_trip_single_game(self, manager):
        repo = ApiCacheRepo(manager.db_path)
        game = _game()

        repo.save_cached_game(game)

        cached = repo.get_cached_game("g1")
        assert cached.game_id == game.game_id
        assert cached.white == "Alice"
        assert cached.cached_at

    def test_bulk_save_and_date_lookup(self, manager):
        repo = ApiCacheRepo(manager.db_path)
        repo.save_cached_games_bulk(
            [
                _game("g1", white="Alice", black="Bob"),
                _game("g2", white="Carol", black="ALICE"),
                _game("g3", source="chesscom", white="Alice", black="Bob"),
                _game("g4", date="2024-05-02", white="Alice", black="Bob"),
            ]
        )

        games = repo.get_cached_games_for_date("lichess", "2024-05-01", "alice")

        assert {game.game_id for game in games} == {"g1", "g2"}

    def test_missing_game_returns_none(self, manager):
        assert ApiCacheRepo(manager.db_path).get_cached_game("missing") is None

    def test_clear_removes_every_row(self, manager):
        repo = ApiCacheRepo(manager.db_path)
        repo.save_cached_game(_game())

        repo.clear_api_cache()

        assert repo.get_cached_game("g1") is None

    def test_empty_bulk_save_is_noop(self, manager):
        ApiCacheRepo(manager.db_path).save_cached_games_bulk([])

    def test_database_failures_are_swallowed(self, tmp_path):
        repo = ApiCacheRepo(str(tmp_path))
        game = _game()

        repo.save_cached_game(game)

        assert repo.get_cached_game("g1") is None
        assert repo.get_cached_games_for_date("lichess", "2024-05-01", "alice") == []
        repo.clear_api_cache()
