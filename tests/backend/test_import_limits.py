"""Tests for the Lichess import cap shared by settings and fetch workers."""

import pytest

from src.backend.api.import_limits import (
    MAX_GAMES_ANONYMOUS,
    MAX_GAMES_WITH_TOKEN,
    clamp_games_limit,
    current_token,
    max_games_limit,
)


@pytest.mark.parametrize(
    ("token", "expected"),
    [
        (None, MAX_GAMES_ANONYMOUS),
        ("", MAX_GAMES_ANONYMOUS),
        ("   ", MAX_GAMES_ANONYMOUS),
        ("lip_token", MAX_GAMES_WITH_TOKEN),
    ],
)
def test_max_games_limit_depends_on_token_presence(token, expected):
    assert max_games_limit(token) == expected


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


def test_current_token_prefers_config(mocker):
    config = mocker.Mock()
    config.get.return_value = "  lip_config  "

    assert current_token(config) == "lip_config"
    config.get.assert_called_once_with("lichess_token", "")


def test_current_token_falls_back_to_environment(mocker, monkeypatch):
    monkeypatch.setenv("LICHESS_TOKEN", "lip_env")
    config = mocker.Mock()
    config.get.return_value = ""

    assert current_token(config) == "lip_env"


def test_current_token_ignores_broken_config(mocker, monkeypatch):
    monkeypatch.setenv("LICHESS_TOKEN", "lip_env")
    config = mocker.Mock()
    config.get.side_effect = RuntimeError("config unavailable")

    assert current_token(config) == "lip_env"
