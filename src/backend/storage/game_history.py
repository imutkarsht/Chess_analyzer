"""
Unified storage facade for chess game history, API cache, and explorer responses.
Maintains 100% backward-compatible public & private API while delegating to focused repos.
"""

import os
import sqlite3
from typing import Any

from src.backend.storage import migrations
from src.backend.storage.api_cache_repo import (
    ApiCacheRepo,
    _info_to_cache_row,
    _row_to_game_info,
)
from src.backend.storage.db_connection import get_db_connection
from src.backend.storage.explorer_cache_repo import ExplorerCacheRepo
from src.backend.storage.games_repo import (
    GamesRepo,
    _enrich_summary_with_tactics,
    _make_game_id,
    _to_float,
    _to_int,
    _to_int_or_none,
)
from src.backend.storage.models import GameAnalysis
from src.backend.storage.profile_cache_repo import (
    CachedProfile,
    ProfileCacheRepo,
)
from src.backend.storage.schema_constants import (
    CURRENT_SCHEMA_VERSION,
    DATA_TABLES,
    EXPLORER_CACHE_TTL_SECONDS,
    GAME_COLUMNS,
    GAME_CSV_COLUMNS,
    LIGHT_GAME_COLUMNS,
)
from src.utils.logger import logger
from src.utils.path_utils import get_user_data_dir

# Re-exports for backwards compatibility
__all__ = [
    "CURRENT_SCHEMA_VERSION",
    "EXPLORER_CACHE_TTL_SECONDS",
    "GAME_COLUMNS",
    "GAME_CSV_COLUMNS",
    "LIGHT_GAME_COLUMNS",
    "GameHistoryManager",
    "_to_float",
    "_to_int",
    "_to_int_or_none",
    "_make_game_id",
    "_enrich_summary_with_tactics",
    "_info_to_cache_row",
    "_row_to_game_info",
]


class GameHistoryManager:
    """
    Unified manager facade for games history, API caching, and opening explorer persistence.
    Internally delegates to GamesRepo, ApiCacheRepo, ExplorerCacheRepo, and migrations.
    """

    def __init__(self, db_path: str | None = None):
        if db_path is None:
            self.db_path = os.path.join(get_user_data_dir(), "analysis_cache.db")
        else:
            self.db_path = db_path

        self._games_repo = GamesRepo(self.db_path)
        self._api_cache_repo = ApiCacheRepo(self.db_path)
        self._explorer_cache_repo = ExplorerCacheRepo(self.db_path)
        self._profile_cache_repo = ProfileCacheRepo(self.db_path)

        self._init_db()

    def _get_connection(self):
        """Context manager guaranteeing connection closure with unified performance pragmas."""
        return get_db_connection(self.db_path)

    def checkpoint(self) -> None:
        """Executes a WAL checkpoint to truncate sidecar WAL/SHM files into the main DB file."""
        try:
            with self._get_connection() as conn:
                conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            logger.debug("Database WAL checkpoint (TRUNCATE) completed.")
        except Exception as e:
            logger.debug("Failed to execute WAL checkpoint: %s", e)

    def vacuum(self) -> None:
        """Reclaims unused disk space from deleted rows."""
        try:
            with self._get_connection() as conn:
                conn.execute("VACUUM")
            logger.info("Database vacuum completed.")
        except Exception as e:
            logger.error("Database vacuum failed: %s", e)

    def close(self) -> None:
        """Closes any active database resources and checkpoints WAL."""
        self.checkpoint()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def _init_db(self) -> None:
        """Initializes tables, schema migrations, and prunes expired explorer cache entries."""
        migrations.init_db(self.db_path)
        self.prune_explorer_cache()

    # --- Games Repository Methods ---

    def save_game(
        self,
        game_analysis: GameAnalysis,
        pgn_content: str,
        force_overwrite: bool = False,
    ) -> None:
        """Saves a completed or partial game analysis to the history."""
        self._games_repo.save_game(game_analysis, pgn_content, force_overwrite=force_overwrite)

    def save_ai_summary(self, game_id: str, text: str) -> None:
        """Stores the generated full-game AI report so it survives reloading."""
        self._games_repo.save_ai_summary(game_id, text)

    def save_games_bulk(self, items: list[Any], force_overwrite: bool = False) -> int:
        """Saves multiple game analyses or game dictionaries inside a single transaction."""
        return self._games_repo.save_games_bulk(items, force_overwrite=force_overwrite)

    def get_all_game_ids(self) -> set[str]:
        """Returns a set of all game IDs currently in the database."""
        return self._games_repo.get_all_game_ids()

    def get_all_games(self, limit: int | None = None) -> list[dict[str, Any]]:
        """Returns a list of all games (metadata + summary) sorted by timestamp desc."""
        return self._games_repo.get_all_games(limit=limit)

    def get_game_summaries(self, limit: int | None = None) -> list[dict[str, Any]]:
        """Returns lightweight game projections (excluding heavy pgn and moves_json)."""
        return self._games_repo.get_game_summaries(limit=limit)

    def get_games_for_users(
        self,
        usernames: list[str],
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """Returns games where either white or black player matches one of the usernames."""
        return self._games_repo.get_games_for_users(usernames, limit=limit)

    def get_games_for_stats(
        self,
        usernames: list[str],
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """Retrieves user games with full payload for statistics aggregation."""
        return self._games_repo.get_games_for_stats(usernames, limit=limit)

    def delete_game(self, game_id: str) -> None:
        """Deletes a game from history."""
        self._games_repo.delete_game(game_id)

    def get_game(self, game_id: str) -> dict[str, Any] | None:
        """Retrieves a single game record."""
        return self._games_repo.get_game(game_id)

    def get_game_analysis(self, game_id: str) -> GameAnalysis | None:
        """Retrieves a single game record as a fully-hydrated GameAnalysis object."""
        return self._games_repo.get_game_analysis(game_id)

    def row_to_game_analysis(self, g_dict: dict[str, Any]) -> GameAnalysis:
        """Hydrates a GameAnalysis object from a database row dictionary."""
        return self._games_repo.row_to_game_analysis(g_dict)

    _row_to_game_analysis = row_to_game_analysis

    def game_exists(self, game_id: str) -> bool:
        """Checks if a game with the given ID already exists."""
        return self._games_repo.game_exists(game_id)

    def clear_history(self) -> None:
        """Clears all games from history and reclaims disk space via VACUUM."""
        self._games_repo.clear_history()

    def _prepare_game_analysis_row(
        self,
        game_analysis: GameAnalysis,
        pgn_content: str,
        timestamp: float | None = None,
    ) -> dict[str, Any]:
        return self._games_repo._prepare_game_analysis_row(
            game_analysis, pgn_content, timestamp=timestamp
        )

    def _prepare_game_analysis_params(
        self,
        game_analysis: GameAnalysis,
        pgn_content: str,
        timestamp: float | None = None,
    ) -> tuple:
        return self._games_repo._prepare_game_analysis_params(
            game_analysis, pgn_content, timestamp=timestamp
        )

    def _prepare_game_dict_row(self, d: dict[str, Any]) -> dict[str, Any]:
        return self._games_repo._prepare_game_dict_row(d)

    def _prepare_game_dict_params(self, d: dict[str, Any]) -> tuple:
        return self._games_repo._prepare_game_dict_params(d)

    @staticmethod
    def _row_to_legacy_tuple(row: dict[str, Any]) -> tuple:
        return GamesRepo._row_to_legacy_tuple(row)

    # --- API Cache Methods ---

    def save_cached_game(self, info: Any) -> None:
        """Saves a single GameInfo to the api_game_cache table."""
        self._api_cache_repo.save_cached_game(info)

    def save_cached_games_bulk(self, games: list[Any]) -> None:
        """Saves multiple GameInfo objects inside a single database transaction."""
        self._api_cache_repo.save_cached_games_bulk(games)

    def get_cached_game(self, game_id: str, source: str | None = None) -> Any | None:
        """Retrieves a single GameInfo object from cache by its ID and source."""
        return self._api_cache_repo.get_cached_game(game_id, source)

    def get_cached_games_for_date(self, source: str, date: str, username: str) -> list[Any]:
        """Retrieves cached games matching source, date, and containing username."""
        return self._api_cache_repo.get_cached_games_for_date(source, date, username)

    def clear_api_cache(self) -> None:
        """Clears all games from the API cache and reclaims disk space via VACUUM."""
        self._api_cache_repo.clear_api_cache()

    # --- Explorer Cache Methods ---

    def save_explorer_cache(self, fen: str, response_json: str) -> None:
        """Saves a Lichess explorer response json for a given FEN."""
        self._explorer_cache_repo.save_explorer_cache(fen, response_json)

    def prune_explorer_cache(self, cursor: sqlite3.Cursor | None = None) -> int:
        """Prunes cached opening explorer responses older than EXPLORER_CACHE_TTL_SECONDS."""
        return self._explorer_cache_repo.prune_explorer_cache(cursor=cursor)

    def get_explorer_cache(self, fen: str) -> str | None:
        """Retrieves a cached explorer response json by FEN, deleting expired entries."""
        return self._explorer_cache_repo.get_explorer_cache(fen)

    def clear_explorer_cache(self) -> int:
        """Deletes every cached explorer response; returns the removed row count."""
        return self._explorer_cache_repo.clear_explorer_cache()

    # --- Profile Cache Methods ---

    def get_cached_profile(self, platform: str, username: str) -> CachedProfile | None:
        """Retrieves a cached public profile (possibly stale) for offline display."""
        return self._profile_cache_repo.get_profile(platform, username)

    def save_cached_profile(
        self,
        platform: str,
        username: str,
        profile: dict[str, Any],
        avatar_bytes: bytes | None = None,
        avatar_mime: str | None = None,
        avatar_url: str | None = None,
    ) -> None:
        """Stores a fetched profile and avatar for the settings preview."""
        self._profile_cache_repo.save_profile(
            platform,
            username,
            profile,
            avatar_bytes=avatar_bytes,
            avatar_mime=avatar_mime,
            avatar_url=avatar_url,
        )

    def prune_profile_cache(self, max_age_days: int | None = None) -> int:
        """Removes profiles older than the offline grace period."""
        return self._profile_cache_repo.prune_profile_cache(max_age_days=max_age_days)

    def clear_profile_cache(self) -> int:
        """Deletes every cached profile; returns the removed row count."""
        return self._profile_cache_repo.clear_profile_cache()

    # --- Whole-store operations ---

    def clear_all_data(self) -> None:
        """Delete games and every cache table, then reclaim disk space.

        Used by the reset action. Raises on failure so the caller can report it
        instead of showing a false success message.
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                for table in DATA_TABLES:
                    cursor.execute(f"DELETE FROM {table}")
                conn.commit()
                cursor.execute("VACUUM")
            logger.info("All local game and cache data cleared.")
        except Exception as e:
            logger.error("Failed to clear all data: %s", e)
            raise

    @staticmethod
    def _parse_cached_at_to_epoch(cached_at: Any) -> float:
        return ExplorerCacheRepo._parse_cached_at_to_epoch(cached_at)
