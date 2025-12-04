import pytest
from src.backend.chess_com_api import ChessComAPI

def test_get_last_games(mock_requests):
    """Test fetching last games."""
    # Mock response
    mock_response = mock_requests.return_value
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "archives": ["https://api.chess.com/pub/player/user/games/2023/10"],
        "games": [
            {"url": "game1", "end_time": 1000},
            {"url": "game2", "end_time": 2000}
        ]
    }
    
    games = ChessComAPI.get_last_games("user", limit=1)
    assert len(games) == 1
    assert games[0]["url"] == "game2"  # Should be the latest one

def test_get_game_by_id_callback(mock_requests):
    """Test fetching game by ID via callback."""
    mock_response = mock_requests.return_value
    mock_response.status_code = 200
    mock_response.json.return_value = {"game": {"pgn": "test_pgn"}}
    
    game = ChessComAPI.get_game_by_id("123456")
    assert game is not None
    assert game["pgn"] == "test_pgn"
