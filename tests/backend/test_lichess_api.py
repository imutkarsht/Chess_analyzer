"""
Tests for Lichess API - URL parsing, game ID extraction.
"""
import pytest
from src.backend.lichess_api import LichessAPI


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
                "black": {"user": {"name": "Player2"}, "rating": 1400}
            }
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
