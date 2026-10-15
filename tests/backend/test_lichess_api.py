"""
Tests for Lichess API - URL parsing, game ID extraction.
"""

from src.backend.api.lichess_api import LichessAPI


class TestGameIdExtraction:
    """Tests for extracting game IDs from Lichess URLs."""

    def test_extract_from_standard_url(self):
        """Test extracting ID from standard game URL."""
        api = LichessAPI()
        url = "https://lichess.org/abcd1234"
        game_id = api.extract_game_id(url)
        assert game_id == "abcd1234"

    def test_extract_from_url_with_color(self):
        """Test extracting ID from URL with color suffix."""
        api = LichessAPI()
        url = "https://lichess.org/abcd1234/white"
        game_id = api.extract_game_id(url)
        assert game_id == "abcd1234"

    def test_extract_from_url_with_black(self):
        """Test extracting ID from URL with black suffix."""
        api = LichessAPI()
        url = "https://lichess.org/abcd1234/black"
        game_id = api.extract_game_id(url)
        assert game_id == "abcd1234"

    def test_extract_from_12char_id(self):
        """Test extracting 12-character game ID (truncated to 8)."""
        api = LichessAPI()
        url = "https://lichess.org/abcd1234efgh"
        game_id = api.extract_game_id(url)
        # API truncates to first 8 chars
        assert game_id == "abcd1234"

    def test_extract_returns_empty_for_short_id(self):
        """Test short URL segment returns empty string."""
        api = LichessAPI()
        url = "https://lichess.org/abc"  # Too short (less than 8)
        game_id = api.extract_game_id(url)
        assert game_id == ""

    def test_extract_returns_empty_for_empty_path(self):
        """Test invalid domain returns empty string."""
        api = LichessAPI()
        # pathological URL that after parsing doesn't have valid segment
        url = ""
        game_id = api.extract_game_id(url)
        assert game_id == ""


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
