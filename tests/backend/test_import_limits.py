"""Tests for the Lichess import cap shared by settings and fetch workers."""

import pytest

from src.backend.api.import_limits import (
    MAX_GAMES_ANONYMOUS,
    MAX_GAMES_WITH_TOKEN,
    clamp_games_limit,
    current_token,
    max_games_limit,
)


@pytest.mark.parametrize("token", [None, "", "   ", "lip_token"])
def test_max_games_limit_is_50_for_every_request(token):
    assert max_games_limit(token) == 50


@pytest.mark.parametrize(
    ("value", "token", "expected"),
    [
        ("25", "lip_token", 25),
        (25, "lip_token", 25),
        (29.9, "lip_token", 29),
        (999, "lip_token", MAX_GAMES_WITH_TOKEN),
        (999, None, MAX_GAMES_ANONYMOUS),
        (0, None, 1),
        (-5, "lip_token", 1),
        ("abc", None, MAX_GAMES_ANONYMOUS),
        (None, None, MAX_GAMES_ANONYMOUS),
        ({}, "lip_token", MAX_GAMES_ANONYMOUS),
    ],
)
def test_clamp_games_limit_bounds_arbitrary_input(value, token, expected):
    assert clamp_games_limit(value, token) == expected


class _Config:
    def __init__(self, token: str = "", broken: bool = False):
        self._token = token
        self._broken = broken

    @property
    def lichess_token(self) -> str:
        if self._broken:
            raise RuntimeError("config unavailable")
        return self._token


def test_current_token_prefers_config():
    assert current_token(_Config("  lip_config  ")) == "lip_config"


def test_current_token_falls_back_to_environment(monkeypatch):
    monkeypatch.setenv("LICHESS_TOKEN", "lip_env")
    assert current_token(_Config("")) == "lip_env"


def test_current_token_ignores_broken_config(monkeypatch):
    monkeypatch.setenv("LICHESS_TOKEN", "lip_env")
    assert current_token(_Config(broken=True)) == "lip_env"
