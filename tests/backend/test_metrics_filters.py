"""Tests for game filtering by player color, format, source, and date."""

import datetime

import pytest

from src.backend.analysis.metrics.filters import (
    extract_game_timestamp,
    filter_games,
    get_user_color,
    matches_filters,
)

NOW = datetime.datetime(2024, 6, 15, 12, 0, tzinfo=datetime.timezone.utc).timestamp()


@pytest.mark.parametrize(
    ("game", "expected"),
    [
        ({"timestamp": 1_700_000_000}, 1_700_000_000.0),
        ({"timestamp": "1700000000"}, 1_700_000_000.0),
        ({"date": "2024-05-01"}, 1_714_521_600.0),
        ({"date": "2024.05.01"}, 1_714_521_600.0),
        ({"date": "2023"}, 1_672_531_200.0),
        ({"timestamp": "not-a-number", "date": "2024-05-01"}, 1_714_521_600.0),
        ({"date": "not-a-date"}, None),
        ({}, None),
    ],
)
def test_extract_game_timestamp_handles_supported_formats(game, expected):
    result = extract_game_timestamp(game)
    if expected is None:
        assert result is None
    else:
        assert result == expected


def test_get_user_color_is_case_insensitive():
    usernames = {"alice", "bob"}

    assert get_user_color({"white": "ALICE", "black": "Carol"}, usernames) == "white"
    assert get_user_color({"white": "Carol", "black": "Bob"}, usernames) == "black"
    assert get_user_color({"white": "Carol", "black": "Dave"}, usernames) is None
    assert get_user_color({}, usernames) is None


def test_matches_filters_rejects_missing_user_identity():
    assert matches_filters({}, None) is False
    assert matches_filters({}, "spectator") is False


def test_matches_filters_color_selection():
    game = {"white": "Alice", "black": "Bob"}

    assert matches_filters(game, "white", color_filter="White") is True
    assert matches_filters(game, "white", color_filter="Black") is False
    assert matches_filters(game, "black", color_filter="All Colors") is True


class TestFormatFilter:
    def test_chess960_only_matches_freestyle(self):
        game = {"chess960": 1}

        assert matches_filters(game, "white", format_filter="Freestyle (Chess960)") is True
        assert matches_filters(game, "white", format_filter="Blitz") is False
        assert matches_filters(game, "white", format_filter="All Formats") is True

    def test_non_960_does_not_match_freestyle(self):
        assert (
            matches_filters({"chess960": 0}, "white", format_filter="Freestyle (Chess960)")
            is False
        )

    def test_uses_speed_category_when_present(self):
        game = {"speed_category": "Rapid", "time_control": "60"}

        assert matches_filters(game, "white", format_filter="rapid") is True
        assert matches_filters(game, "white", format_filter="Blitz") is False

    def test_falls_back_to_time_control_detection(self):
        game = {"time_control": "180+2"}

        assert matches_filters(game, "white", format_filter="Blitz") is True


class TestSourceFilter:
    @pytest.mark.parametrize(
        ("source", "source_filter", "expected"),
        [
            ("chesscom", "Chess.com", True),
            ("lichess", "Chess.com", False),
            ("file", "Chess.com", False),
            ("lichess", "Lichess", True),
            ("chesscom", "Lichess", False),
            ("file", "Local Files", True),
            ("pgn", "Local Files", True),
            ("lichess", "Local Files", False),
            ("anything", "All Sources", True),
        ],
    )
    def test_source_matching(self, source, source_filter, expected):
        game = {"source": source}
        assert matches_filters(game, "white", source_filter=source_filter) is expected


class TestDateFilter:
    def test_all_time_never_rejects(self):
        assert matches_filters({}, "white", date_filter="All Time", now=NOW) is True

    @pytest.mark.parametrize(
        ("age_seconds", "date_filter", "expected"),
        [
            (3600, "Last 24 Hours", True),
            (2 * 86400, "Last 24 Hours", False),
            (2 * 86400, "Last 7 Days", True),
            (8 * 86400, "Last 7 Days", False),
            (10 * 86400, "Last 30 Days", True),
            (40 * 86400, "Last 90 Days", True),
            (100 * 86400, "Last 90 Days", False),
        ],
    )
    def test_relative_windows(self, age_seconds, date_filter, expected):
        game = {"timestamp": NOW - age_seconds}

        assert matches_filters(game, "white", date_filter=date_filter, now=NOW) is expected

    def test_this_year(self):
        this_year = datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc).timestamp()
        last_year = datetime.datetime(2023, 12, 31, tzinfo=datetime.timezone.utc).timestamp()

        assert matches_filters(
            {"timestamp": this_year}, "white", date_filter="This Year", now=NOW
        ) is True
        assert matches_filters(
            {"timestamp": last_year}, "white", date_filter="This Year", now=NOW
        ) is False

    def test_missing_timestamp_is_rejected_for_bounded_filters(self):
        assert (
            matches_filters({}, "white", date_filter="Last 7 Days", now=NOW) is False
        )

    def test_unknown_date_filter_is_rejected(self):
        assert matches_filters({}, "white", date_filter="Yesterday", now=NOW) is False


def test_filter_games_returns_user_color_tuples():
    games = [
        {"white": "Alice", "black": "Bob", "source": "chesscom"},
        {"white": "Carol", "black": "Dave", "source": "lichess"},
        {"white": "Bob", "black": "Alice", "source": "lichess"},
    ]

    matched = filter_games(games, ["alice"], color_filter="White")

    assert len(matched) == 1
    assert matched[0][0] is games[0]
    assert matched[0][1] == "white"


def test_filter_games_applies_combined_filters():
    games = [
        {"white": "Alice", "black": "Bob", "source": "chesscom", "speed_category": "Blitz"},
        {"white": "Alice", "black": "Bob", "source": "lichess", "speed_category": "Blitz"},
    ]

    matched = filter_games(games, ["Alice"], source_filter="Chess.com", format_filter="Blitz")

    assert [game for game, _ in matched] == [games[0]]
