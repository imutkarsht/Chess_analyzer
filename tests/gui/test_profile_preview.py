"""Cache-first behaviour and formatting helpers for profile previews."""

import base64
import time

import pytest

from src.backend.api.base_api import ProfileResult
from src.backend.storage.profile_cache_repo import CachedProfile
from src.gui.views.settings import profile_preview
from src.gui.views.settings.profile_preview import (
    AVATAR_SIZE,
    country_flag,
    format_cache_age,
    initials_for,
    load_profile,
)

# 1x1 transparent PNG; enough to exercise the QPainter avatar path.
_PNG_PIXEL = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8"
    "z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


class FakeHistory:
    """Minimal cache surface used by load_profile."""

    def __init__(self, cached=None):
        self.cached = cached
        self.saved = []

    def get_cached_profile(self, platform, username):
        return self.cached

    def save_cached_profile(self, platform, username, profile, **kwargs):
        self.saved.append((platform, username, profile, kwargs))


@pytest.mark.parametrize(
    ("age_seconds", "expected"),
    [
        (10, "just now"),
        (300, "5 min ago"),
        (7200, "2 hrs ago"),
        (172800, "2 days ago"),
    ],
)
def test_format_cache_age(age_seconds, expected):
    now = 1_000_000

    assert format_cache_age(now - age_seconds, now=now) == expected


def test_format_cache_age_is_empty_without_timestamp():
    assert format_cache_age(0) == ""


@pytest.mark.parametrize(
    ("code", "expected"),
    [("no", "🇳🇴"), ("US", "🇺🇸"), ("", ""), ("USA", ""), (None, "")],
)
def test_country_flag(code, expected):
    assert country_flag(code) == expected


@pytest.mark.parametrize(
    ("name", "expected"),
    [("MagnusCarlsen", "MA"), ("dr_nykterstein", "DN"), ("  ", "?")],
)
def test_initials_for(name, expected):
    assert initials_for(name) == expected


def test_circular_avatar_renders_uploaded_bytes(qapp):
    pixmap = profile_preview._circular_avatar(_PNG_PIXEL)

    assert pixmap is not None
    assert not pixmap.isNull()
    assert (pixmap.width(), pixmap.height()) == (AVATAR_SIZE, AVATAR_SIZE)


def test_circular_avatar_rejects_invalid_bytes(qapp):
    assert profile_preview._circular_avatar(b"not an image") is None


def test_load_profile_short_circuits_on_fresh_cache(monkeypatch):
    cached = CachedProfile(
        profile={"username": "MagnusCarlsen"},
        fetched_at=time.time(),
        is_stale=False,
    )
    history = FakeHistory(cached)

    def fail_if_called(_username):
        raise AssertionError("fresh cache must not hit the network")

    monkeypatch.setattr(
        profile_preview.ChessComAPI,
        "get_user_profile_result",
        staticmethod(fail_if_called),
    )

    load = load_profile("chesscom", "MagnusCarlsen", history=history)

    assert load.status == "ok"
    assert load.from_cache is True
    assert load.is_stale is False
    assert load.profile == {"username": "MagnusCarlsen"}


def test_load_profile_falls_back_to_stale_cache_when_offline(monkeypatch):
    cached = CachedProfile(
        profile={"username": "MagnusCarlsen", "total_games": 42},
        fetched_at=time.time() - 86_400,
        is_stale=True,
        avatar_bytes=b"cached-avatar",
        avatar_mime="image/png",
    )
    history = FakeHistory(cached)
    monkeypatch.setattr(
        profile_preview.ChessComAPI,
        "get_user_profile_result",
        staticmethod(lambda _username: ProfileResult(None, "offline")),
    )

    load = load_profile("chesscom", "MagnusCarlsen", history=history)

    assert load.status == "offline"
    assert load.from_cache is True
    assert load.is_stale is True
    assert load.profile["total_games"] == 42
    assert load.avatar_bytes == b"cached-avatar"
    assert history.saved == []
