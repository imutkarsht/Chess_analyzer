from src.backend.api.chess_com_api import ChessComAPI

def test_get_last_games(mock_requests):
    """Test fetching last games."""
    mock_response = mock_requests.return_value
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "archives": ["https://api.chess.com/pub/player/user/games/2023/10"],
        "games": [
            {"url": "https://www.chess.com/game/live/1000", "end_time": 1000},
            {"url": "https://www.chess.com/game/live/2000", "end_time": 2000}
        ]
    }

    games = ChessComAPI.get_last_games("user", limit=1)
    assert len(games) == 1
    assert games[0]["url"] == "https://www.chess.com/game/live/2000"

def test_get_game_by_id_with_username(mock_requests):
    """Test fetching game by ID via user archives."""
    mock_response = mock_requests.return_value
    mock_response.status_code = 200

    def json_side_effect():
        # First call is archives list, second is monthly games
        if mock_response.call_count_json == 1:
            return {"archives": ["https://api.chess.com/pub/player/user/games/2023/10"]}
        return {
            "games": [
                {"url": "https://www.chess.com/game/live/123456", "pgn": "test_pgn"}
            ]
        }

    mock_response.call_count_json = 0
    def mock_json():
        mock_response.call_count_json += 1
        return json_side_effect()

    mock_response.json.side_effect = mock_json

    game = ChessComAPI.get_game_by_id("123456", username="user")
    assert game is not None
    assert game["pgn"] == "test_pgn"
