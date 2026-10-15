from src.backend.api.chess_com_api import ChessComAPI


def test_get_last_games(mock_requests):
    """Test fetching last games."""
    mock_response = mock_requests.return_value
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "archives": ["https://api.chess.com/pub/player/user/games/2023/10"],
        "games": [
            {"url": "https://www.chess.com/game/live/1000", "end_time": 1000},
            {"url": "https://www.chess.com/game/live/2000", "end_time": 2000},
        ],
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
        return {"games": [{"url": "https://www.chess.com/game/live/123456", "pgn": "test_pgn"}]}

    mock_response.call_count_json = 0

    def mock_json():
        mock_response.call_count_json += 1
        return json_side_effect()

    mock_response.json.side_effect = mock_json

    game = ChessComAPI.get_game_by_id("123456", username="user")
    assert game is not None
    assert game["pgn"] == "test_pgn"


def test_get_user_profile(mock_requests):
    """Test fetching user profile and stats."""
    mock_response = mock_requests.return_value
    mock_response.status_code = 200

    def json_side_effect():
        if mock_response.call_count_json == 1:
            return {
                "username": "hikaru",
                "title": "GM",
                "avatar": "https://example.com/avatar.jpg",
                "country": "https://api.chess.com/pub/country/US",
                "joined": 123456789,
                "url": "https://www.chess.com/member/hikaru",
            }
        return {
            "chess_bullet": {
                "last": {"rating": 3200},
                "best": {"rating": 3350},
                "record": {"win": 500, "loss": 100, "draw": 50},
            },
            "chess_blitz": {
                "last": {"rating": 3150},
                "best": {"rating": 3220},
                "record": {"win": 400, "loss": 80, "draw": 40},
            },
            "tactics": {
                "highest": {"rating": 3400},
            },
        }

    mock_response.call_count_json = 0

    def mock_json():
        mock_response.call_count_json += 1
        return json_side_effect()

    mock_response.json.side_effect = mock_json

    prof = ChessComAPI.get_user_profile("hikaru")
    assert prof is not None
    assert prof["platform"] == "chesscom"
    assert prof["username"] == "hikaru"
    assert prof["title"] == "GM"
    assert prof["bullet"]["rating"] == 3200
    assert prof["bullet"]["peak"] == 3350
    assert prof["blitz"]["rating"] == 3150
    assert prof["puzzle"]["rating"] == 3400
    assert prof["total_games"] == 650 + 520
