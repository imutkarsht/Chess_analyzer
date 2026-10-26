"""
Tests for Lichess API - URL parsing, game ID extraction.
"""

import pytest

from src.backend.api.lichess_api import LichessAPI, _result_for_side


class TestGameIdExtraction:
    """Tests for extracting game IDs from Lichess URLs."""

    @pytest.mark.parametrize(
        ("url", "expected"),
        [
            ("https://lichess.org/abcd1234", "abcd1234"),
            ("https://lichess.org/abcd1234/white", "abcd1234"),
            ("https://lichess.org/abcd1234/black", "abcd1234"),
            # A 12-character ID is truncated to the canonical 8.
            ("https://lichess.org/abcd1234efgh", "abcd1234"),
            # Too short (less than 8) and pathological empty URLs yield nothing.
            ("https://lichess.org/abc", ""),
            ("", ""),
        ],
    )
    def test_extract_game_id(self, url, expected):
        assert LichessAPI().extract_game_id(url) == expected


class TestGetGameById:
    """Tests for fetching game by ID with mocked HTTP."""

    def test_get_game_success(self, mock_requests):
        """Test successful game fetch returns expected data."""
        mock_response = mock_requests.return_value
        mock_response.status_code = 200
        mock_response.raise_for_status = lambda: None
        mock_response.json.return_value = {
            "id": "testid12",
            "pgn": "1. e4 e5 1-0",
            "players": {
                "white": {"user": {"name": "Player1"}, "rating": 1500},
                "black": {"user": {"name": "Player2"}, "rating": 1400},
            },
        }

        api = LichessAPI()
        result = api.get_game_by_id("testid12")

        assert result is not None
        assert "pgn" in result
        assert result["pgn"] == "1. e4 e5 1-0"

    def test_get_game_returns_empty_dict_on_error(self, mock_requests):
        """Test error returns empty dict."""
        mock_requests.side_effect = Exception("Network error")

        api = LichessAPI()
        result = api.get_game_by_id("nonexistent")

        assert result == {}


class TestGetUserGames:
    """Tests for fetching user games."""

    def test_get_user_games_success(self, mock_requests):
        """Test successful user games fetch with clocks parameter."""
        mock_response = mock_requests.return_value
        mock_response.status_code = 200
        mock_response.raise_for_status = lambda: None
        mock_response.iter_lines.return_value = [
            b'{"id": "game1", "players": {"white": {"user": {"name": "UserW"}, "rating": 1800}, "black": {"user": {"name": "UserB"}, "rating": 1700}}, "winner": "white", "status": "mate", "pgn": "1. e4 e5"}'
        ]

        api = LichessAPI()
        games = api.get_user_games("UserW", max_games=5)

        assert len(games) == 1
        assert games[0]["white"]["username"] == "UserW"
        assert games[0]["black"]["username"] == "UserB"
        assert games[0]["pgn"] == "1. e4 e5"

        # Verify requests.get was called with 'clocks': 'true'
        mock_requests.assert_called_once()
        args, kwargs = mock_requests.call_args
        assert kwargs["params"]["clocks"] == "true"
        assert kwargs["params"]["max"] == 5


class TestGetUserProfile:
    """Tests for fetching Lichess user profile & ratings."""

    def test_get_user_profile_success(self, mock_requests):
        mock_response = mock_requests.return_value
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "magnus",
            "username": "MagnusCarlsen",
            "title": "GM",
            "createdAt": 1300000000000,
            "url": "https://lichess.org/@/MagnusCarlsen",
            "perfs": {
                "bullet": {"rating": 2900, "games": 500},
                "blitz": {"rating": 3050, "games": 2000},
                "rapid": {"rating": 2800, "games": 100},
                "classical": {"rating": 2750, "games": 20},
                "puzzle": {"rating": 2600, "games": 400},
            },
            "count": {
                "all": 3020,
                "win": 2100,
                "loss": 620,
                "draw": 300,
            },
            "profile": {
                "country": "NO",
            },
        }

        api = LichessAPI()
        prof = api.get_user_profile("MagnusCarlsen")
        assert prof is not None
        assert prof["platform"] == "lichess"
        assert prof["username"] == "MagnusCarlsen"
        assert prof["title"] == "GM"
        assert prof["bullet"]["rating"] == 2900
        assert prof["blitz"]["rating"] == 3050
        assert prof["puzzle"]["rating"] == 2600
        assert prof["total_games"] == 3020
        assert prof["country"] == "NO"


class TestPublicProfileAndToken:
    """The public preview must work anonymously and classify failures."""

    def test_public_profile_never_sends_the_saved_token(self, mock_requests, monkeypatch):
        api = LichessAPI()
        monkeypatch.setattr(
            api.config_manager,
            "get",
            lambda key, default=None: "lip_secret" if key == "lichess_token" else default,
        )
        mock_requests.return_value.status_code = 200
        mock_requests.return_value.json.return_value = {
            "username": "MagnusCarlsen",
            "perfs": {},
            "count": {},
        }

        result = api.get_user_profile_result("MagnusCarlsen")

        assert result.status == "ok"
        assert "Authorization" not in mock_requests.call_args.kwargs["headers"]

    @pytest.mark.parametrize(
        ("status_code", "expected"),
        [(404, "not_found"), (429, "rate_limited"), (401, "unauthorized")],
    )
    def test_profile_status_classification(
        self, mock_requests, status_code, expected
    ):
        mock_requests.return_value.status_code = status_code

        result = LichessAPI().get_user_profile_result("nobody")

        assert result.profile is None
        assert result.status == expected

    def test_account_check_uses_explicit_token(self, mock_requests):
        mock_requests.return_value.status_code = 200
        mock_requests.return_value.json.return_value = {"username": "MagnusCarlsen"}

        data, status = LichessAPI().get_account("lip_typed")

        assert status == "ok"
        assert data["username"] == "MagnusCarlsen"
        assert (
            mock_requests.call_args.kwargs["headers"]["Authorization"]
            == "Bearer lip_typed"
        )

    def test_account_check_without_token_is_unauthorized(self, mock_requests, monkeypatch):
        api = LichessAPI()
        monkeypatch.delenv("LICHESS_TOKEN", raising=False)
        monkeypatch.setattr(
            api.config_manager, "get", lambda key, default=None: default
        )

        assert api.get_account() == (None, "unauthorized")
        mock_requests.assert_not_called()

    @pytest.mark.parametrize(
        ("token", "requested", "expected_max"),
        [("", 50, 20), ("lip_secret", 50, 30), ("", 5, 5)],
    )
    def test_fetch_time_import_clamp(
        self, mock_requests, monkeypatch, token, requested, expected_max
    ):
        api = LichessAPI()
        monkeypatch.delenv("LICHESS_TOKEN", raising=False)
        monkeypatch.setattr(
            api.config_manager,
            "get",
            lambda key, default=None: token if key == "lichess_token" else default,
        )
        mock_requests.return_value.iter_lines.return_value = [
            b'{"id": "abcd1234", "players": {}, "pgn": "1. e4"}'
        ]

        api.get_user_games("magnus", requested)

        assert mock_requests.call_args.kwargs["params"]["max"] == expected_max


@pytest.mark.parametrize(
    ("game_data", "side", "expected"),
    [
        ({"winner": "white"}, "white", "win"),
        ({"winner": "black"}, "black", "win"),
        ({"status": "resign"}, "white", "resigned"),
        ({"status": "outoftime"}, "white", "timeout"),
        ({"status": "timeout"}, "black", "timeout"),
        ({"status": "mate"}, "black", "checkmated"),
        ({"status": "stalemate"}, "white", "stalemate"),
        ({"status": "draw"}, "white", "agreed"),
        ({}, "black", "agreed"),
    ],
)
def test_result_for_side_maps_loss_reasons(game_data, side, expected):
    assert _result_for_side(game_data, side) == expected


class TestGetUserGamesEdgeCases:
    def test_malformed_lines_are_skipped(self, mock_requests):
        mock_requests.return_value.iter_lines.return_value = [
            b"",
            b"   ",
            b"not json",
            b'{"id": "abcd1234", "players": {}, "pgn": "1. e4"}',
        ]

        games = LichessAPI().get_user_games("magnus")

        assert len(games) == 1
        assert games[0]["white"] == {"username": "?", "rating": "?", "result": "agreed"}
        assert games[0]["url"] == "https://lichess.org/abcd1234"

    def test_transport_failure_returns_empty_list(self, mocker):
        import requests

        mocker.patch(
            "requests.get", side_effect=requests.exceptions.ConnectionError("offline")
        )

        assert LichessAPI().get_user_games("magnus") == []


class TestGetUserGamesByDate:
    def test_success_uses_date_window(self, mock_requests, mocker):
        import datetime

        mock_requests.return_value.iter_lines.return_value = [
            b"broken",
            b'{"id": "abcd1234", "players": {"white": {"user": {"name": "W"}, "rating": 2000}}, "pgn": "1. e4", "speed": "blitz", "createdAt": 1700000000000}',
        ]

        games = LichessAPI().get_user_games_by_date("W", datetime.date(2024, 5, 1))

        assert len(games) == 1
        assert games[0]["white"]["username"] == "W"
        assert games[0]["black"]["username"] == "?"
        assert games[0]["time_class"] == "blitz"
        assert games[0]["end_time"] == 1_700_000_000
        params = mock_requests.call_args.kwargs["params"]
        assert params["since"] < params["until"]
        assert params["max"] == 100

    def test_transport_failure_returns_empty_list(self, mocker):
        import datetime

        import requests

        mocker.patch(
            "requests.get", side_effect=requests.exceptions.ConnectionError("offline")
        )

        assert LichessAPI().get_user_games_by_date("W", datetime.date(2024, 5, 1)) == []


class TestLichessProfileEdges:
    def test_blank_username_is_not_found(self, mock_requests):
        result = LichessAPI().get_user_profile_result("   ")

        assert result.profile is None
        assert result.status == "not_found"
        mock_requests.assert_not_called()

    def test_non_object_payload_is_an_error(self, mock_requests):
        mock_requests.return_value.status_code = 200
        mock_requests.return_value.json.return_value = ["not", "a", "profile"]

        result = LichessAPI().get_user_profile_result("magnus")

        assert result.profile is None
        assert result.status == "error"

    def test_flag_is_used_for_country_and_empty_counts_are_safe(self, mock_requests):
        mock_requests.return_value.status_code = 200
        mock_requests.return_value.json.return_value = {
            "username": "magnus",
            "perfs": {},
            "count": {},
            "profile": {"flag": "NO"},
        }

        profile = LichessAPI().get_user_profile("magnus")

        assert profile["country"] == "NO"
        assert profile["total_games"] == 0
        assert profile["win_rate"] == 0.0
        assert profile["record"] == {"win": 0, "loss": 0, "draw": 0}
