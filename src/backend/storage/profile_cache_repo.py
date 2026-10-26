"""Repository for cached public player profiles and avatars."""

import json
import time
from dataclasses import dataclass
from typing import Any

from src.backend.storage.db_connection import get_db_connection
from src.constants import DEFAULT_PROFILE_CACHE_TTL_HOURS, PROFILE_CACHE_MAX_AGE_DAYS
from src.utils.logger import logger

# Distinguishes "use the user setting" from an explicit None ("never stale").
_UNSET = object()


@dataclass(frozen=True)
class CachedProfile:
    """A cached profile plus the metadata the preview needs."""

    profile: dict
    fetched_at: float
    is_stale: bool
    avatar_bytes: bytes | None = None
    avatar_mime: str | None = None
    avatar_url: str | None = None


class ProfileCacheRepo:
    """Stores public profiles keyed by platform and case-folded username.

    Expired rows are intentionally still returned as stale data so the preview
    can keep working offline; the TTL only decides when a refresh is due.
    """

    _last_prune: float = 0.0
    _PRUNE_INTERVAL_SECONDS = 3600.0

    def __init__(
        self,
        db_path: str,
        ttl_seconds: float | None | object = _UNSET,
        max_age_days: int = PROFILE_CACHE_MAX_AGE_DAYS,
    ):
        self.db_path = db_path
        self._ttl_override = ttl_seconds
        self._max_age_days = max_age_days

    def _get_connection(self):
        return get_db_connection(self.db_path)

    def _ttl_seconds(self) -> float | None:
        if self._ttl_override is not _UNSET:
            return self._ttl_override  # type: ignore[return-value]

        from src.utils.config import ConfigManager

        hours = ConfigManager().get(
            "profile_cache_ttl_hours", DEFAULT_PROFILE_CACHE_TTL_HOURS
        )
        if hours is None:
            return None
        try:
            return max(1, int(hours)) * 3600.0
        except (TypeError, ValueError):
            return DEFAULT_PROFILE_CACHE_TTL_HOURS * 3600.0

    @staticmethod
    def _key(platform: str, username: str) -> tuple[str, str]:
        return platform.strip().lower(), username.strip().casefold()

    def get_profile(self, platform: str, username: str) -> CachedProfile | None:
        """Return the cached profile, marking it stale when the TTL has passed."""
        platform_key, username_key = self._key(platform, username)
        if not username_key:
            return None

        try:
            with self._get_connection() as conn:
                row = conn.execute(
                    """
                    SELECT payload_json, avatar_url, avatar_blob, avatar_mime, fetched_at
                    FROM api_profile_cache
                    WHERE platform = ? AND username_key = ?
                    """,
                    (platform_key, username_key),
                ).fetchone()
        except Exception as e:
            logger.debug("Could not read cached profile: %s", e)
            return None

        if not row:
            return None

        try:
            profile = json.loads(row[0])
        except (TypeError, ValueError):
            logger.warning("Discarding corrupt cached profile for %s/%s", platform, username)
            return None
        if not isinstance(profile, dict):
            return None

        try:
            fetched_at = float(row[4])
        except (TypeError, ValueError):
            fetched_at = 0.0

        ttl_seconds = self._ttl_seconds()
        is_stale = ttl_seconds is not None and (time.time() - fetched_at) > ttl_seconds
        return CachedProfile(
            profile=profile,
            fetched_at=fetched_at,
            is_stale=is_stale,
            avatar_bytes=row[2],
            avatar_mime=row[3],
            avatar_url=row[1],
        )

    def save_profile(
        self,
        platform: str,
        username: str,
        profile: dict[str, Any],
        avatar_bytes: bytes | None = None,
        avatar_mime: str | None = None,
        avatar_url: str | None = None,
    ) -> None:
        """Upsert a profile, preserving the old avatar when a refresh lacks one."""
        platform_key, username_key = self._key(platform, username)
        if not username_key:
            return

        try:
            payload = json.dumps(profile, ensure_ascii=False)
        except (TypeError, ValueError) as e:
            logger.error("Could not serialize profile for %s/%s: %s", platform, username, e)
            return

        now = time.time()
        try:
            with self._get_connection() as conn:
                if avatar_bytes:
                    conn.execute(
                        """
                        INSERT INTO api_profile_cache (
                            platform, username_key, username, payload_json,
                            avatar_url, avatar_blob, avatar_mime, fetched_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(platform, username_key) DO UPDATE SET
                            username = excluded.username,
                            payload_json = excluded.payload_json,
                            avatar_url = excluded.avatar_url,
                            avatar_blob = excluded.avatar_blob,
                            avatar_mime = excluded.avatar_mime,
                            fetched_at = excluded.fetched_at
                        """,
                        (
                            platform_key,
                            username_key,
                            username.strip(),
                            payload,
                            avatar_url,
                            avatar_bytes,
                            avatar_mime,
                            now,
                        ),
                    )
                else:
                    # A failed/absent avatar must not erase a previously cached one.
                    conn.execute(
                        """
                        INSERT INTO api_profile_cache (
                            platform, username_key, username, payload_json,
                            avatar_url, avatar_blob, avatar_mime, fetched_at
                        ) VALUES (?, ?, ?, ?, NULL, NULL, NULL, ?)
                        ON CONFLICT(platform, username_key) DO UPDATE SET
                            username = excluded.username,
                            payload_json = excluded.payload_json,
                            fetched_at = excluded.fetched_at
                        """,
                        (platform_key, username_key, username.strip(), payload, now),
                    )
                conn.commit()
        except Exception as e:
            logger.error("Failed to cache profile for %s/%s: %s", platform, username, e)
            return

        self._maybe_prune()

    def prune_profile_cache(self, max_age_days: int | None = None) -> int:
        """Delete profiles older than the offline grace period."""
        days = self._max_age_days if max_age_days is None else max_age_days
        cutoff = time.time() - (max(0, days) * 86400)
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    "DELETE FROM api_profile_cache WHERE fetched_at < ?", (cutoff,)
                )
                conn.commit()
                return cursor.rowcount or 0
        except Exception as e:
            logger.error("Failed to prune profile cache: %s", e)
            return 0

    def clear_profile_cache(self) -> int:
        """Delete every cached profile and return the removed row count."""
        try:
            with self._get_connection() as conn:
                count = conn.execute(
                    "SELECT COUNT(*) FROM api_profile_cache"
                ).fetchone()[0]
                conn.execute("DELETE FROM api_profile_cache")
                conn.commit()
                return int(count)
        except Exception as e:
            logger.error("Failed to clear profile cache: %s", e)
            return 0

    def _maybe_prune(self) -> None:
        now = time.time()
        if now - self._last_prune < self._PRUNE_INTERVAL_SECONDS:
            return
        type(self)._last_prune = now
        self.prune_profile_cache()
