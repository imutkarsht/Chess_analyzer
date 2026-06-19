from src.backend.api.chess_com_api import ChessComAPI

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

def test_get_game_via_daily_callback(mock_requests):
    """Test direct daily callback function."""
    mock_response = mock_requests.return_value
    mock_response.status_code = 200
    mock_response.json.return_value = {"game": {"pgn": "daily_pgn"}}
    
    game = ChessComAPI._get_game_via_daily_callback("daily123")
    assert game is not None
    assert game["pgn"] == "daily_pgn"
    # Verify the requested URL matches the daily callback endpoint
    mock_requests.assert_called_with(
        "https://www.chess.com/callback/daily/game/daily123",
        headers=ChessComAPI.HEADERS
    )

def test_get_game_by_id_daily_url(mock_requests):
    """Test that daily URL prioritizes daily callback."""
    mock_response = mock_requests.return_value
    mock_response.status_code = 200
    mock_response.json.return_value = {"game": {"pgn": "daily_pgn"}}
    
    game = ChessComAPI.get_game_by_id("daily123", url="https://www.chess.com/game/daily/123")
    assert game is not None
    assert game["pgn"] == "daily_pgn"
    # Verify the first call tried the daily callback
    mock_requests.assert_called_with(
        "https://www.chess.com/callback/daily/game/daily123",
        headers=ChessComAPI.HEADERS
    )

def test_get_game_by_id_daily_fallback(mocker):
    """Test that daily URL falls back to live callback if daily fails."""
    # We want to mock requests.get to return a failure status first, then success.
    # We can use mocker.patch with a side_effect.
    mock_get = mocker.patch("requests.get")
    
    resp_fail = mocker.Mock()
    resp_fail.status_code = 404
    
    resp_success = mocker.Mock()
    resp_success.status_code = 200
    resp_success.json.return_value = {"game": {"pgn": "live_pgn"}}
    
    mock_get.side_effect = [resp_fail, resp_success]
    
    game = ChessComAPI.get_game_by_id("daily123", url="https://www.chess.com/game/daily/123")
    assert game is not None
    assert game["pgn"] == "live_pgn"
    
    # We expect 2 calls: first daily callback, second live callback.
    assert mock_get.call_count == 2
    mock_get.assert_any_call(
        "https://www.chess.com/callback/daily/game/daily123",
        headers=ChessComAPI.HEADERS
    )
    mock_get.assert_any_call(
        "https://www.chess.com/callback/live/game/daily123",
        headers=ChessComAPI.HEADERS
    )

