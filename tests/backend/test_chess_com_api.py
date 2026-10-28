import datetime
from unittest.mock import MagicMock

import pytest
import requests

from src.backend.api.chess_com_api import ChessComAPI


def _json_response(payload):
    response = MagicMock()
    response.status_code = 200
    response.ok = True
    response.json.return_value = payload
    return response


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
    assert prof["country"] == "US"
    assert prof["bullet"]["rating"] == 3200
    assert prof["bullet"]["peak"] == 3350
    assert prof["blitz"]["rating"] == 3150
    assert prof["puzzle"]["rating"] == 3400
    assert prof["total_games"] == 650 + 520


def test_get_user_profile_classifies_missing_user(mock_requests):
    mock_requests.return_value.status_code = 404

    result = ChessComAPI.get_user_profile_result("nobody")

    assert result.profile is None
    assert result.status == "not_found"


@pytest.mark.parametrize(
    ("content_type", "expected_bytes"),
    [("image/png", b"avatar-bytes"), ("application/json", None)],
)
def test_get_user_profile_accepts_only_image_avatars(
    mock_requests, content_type, expected_bytes
):
    avatar = MagicMock()
    avatar.status_code = 200
    avatar.headers = {"Content-Type": content_type}
    avatar.iter_content.return_value = [b"avatar-bytes"]
    avatar.__enter__.return_value = avatar
    mock_requests.side_effect = [
        _json_response(
            {
                "username": "hikaru",
                "avatar": "https://example.com/avatar.png",
                "country": "https://api.chess.com/pub/country/US",
            }
        ),
        _json_response({}),
        avatar,
    ]

    result = ChessComAPI.get_user_profile_result("hikaru")

    assert result.status == "ok"
    assert result.avatar_bytes == expected_bytes
    assert result.avatar_mime == (content_type if expected_bytes else None)


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://www.chess.com/game/live/123456", "123456"),
        ("https://www.chess.com/live/game/98765", "98765"),
        ("https://www.chess.com/game/daily/42", "42"),
        ("https://www.chess.com/member/hikaru", None),
        ("", None),
    ],
)
def test_extract_game_id(url, expected):
    assert ChessComAPI.extract_game_id(url) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("https://api.chess.com/pub/country/US", "US"),
        ("https://api.chess.com/pub/country/us/", "US"),
        (None, None),
        ("", None),
    ],
)
def test_country_code(value, expected):
    assert ChessComAPI._country_code(value) == expected


def test_get_user_games_by_date_filters_to_requested_day(mock_requests):
    date = datetime.date(2024, 5, 1)
    start = datetime.datetime.combine(date, datetime.time.min).timestamp()
    mock_requests.return_value = _json_response(
        {
            "games": [
                {"end_time": int(start) + 60, "url": "in-day"},
                {"end_time": int(start) - 60, "url": "previous-day"},
                {"end_time": None, "url": "unknown"},
            ]
        }
    )

    games = ChessComAPI.get_user_games_by_date("alice", date)

    assert [game["url"] for game in games] == ["in-day"]


def test_get_user_games_by_date_returns_empty_on_network_failure(mock_requests):
    mock_requests.side_effect = requests.exceptions.ConnectionError()

    assert ChessComAPI.get_user_games_by_date("alice", datetime.date(2024, 5, 1)) == []


def test_get_game_by_id_without_username_or_url_returns_none(mock_requests):
    assert ChessComAPI.get_game_by_id("123") is None
    mock_requests.assert_not_called()


@pytest.mark.parametrize(
    "html",
    [
        '<script>{"username":"alice"}</script>',
        '<meta name="description" content="alice (1500) vs bob (1400)">',
    ],
)
def test_get_game_by_id_scrapes_username_from_html(
    mock_requests, mocker, html
):
    mock_requests.return_value.text = html
    find = mocker.patch.object(
        ChessComAPI, "_find_game_in_archives", return_value={"pgn": "1. e4"}
    )

    game = ChessComAPI.get_game_by_id("123", url="https://example.com/game/123")

    assert game == {"pgn": "1. e4"}
    find.assert_called_once_with("alice", "123")


def test_find_game_in_archives_requires_successful_archive_list(mock_requests):
    mock_requests.return_value.status_code = 503

    assert ChessComAPI._find_game_in_archives("alice", "123") is None


def test_find_game_in_archives_returns_matching_game(mock_requests):
    archives = MagicMock()
    archives.status_code = 200
    archives.json.return_value = {"archives": ["https://example.com/2024/05"]}
    monthly = MagicMock()
    monthly.status_code = 200
    monthly.json.return_value = {
        "games": [
            {"url": "https://www.chess.com/game/live/111", "pgn": "other"},
            {"url": "https://www.chess.com/game/live/123", "pgn": "target"},
        ]
    }
    mock_requests.side_effect = [archives, monthly]

    game = ChessComAPI._find_game_in_archives("alice", "123")

    assert game["pgn"] == "target"


def test_find_game_in_archives_swallows_errors(mock_requests):
    mock_requests.side_effect = RuntimeError("network down")

    assert ChessComAPI._find_game_in_archives("alice", "123") is None


def test_profile_survives_stats_failure(mock_requests):
    mock_requests.side_effect = [
        _json_response({"username": "alice", "country": None}),
        MagicMock(status_code=500, ok=False),
    ]

    result = ChessComAPI.get_user_profile_result("alice")

    assert result.status == "ok"
    assert result.profile["username"] == "alice"
    assert result.profile["total_games"] == 0
    assert result.profile["win_rate"] == 0.0


def test_profile_rejects_non_object_payload(mock_requests):
    mock_requests.return_value = _json_response(["not", "a", "profile"])

    result = ChessComAPI.get_user_profile_result("alice")

    assert result.profile is None
    assert result.status == "error"


def test_profile_empty_username_is_not_found(mock_requests):
    result = ChessComAPI.get_user_profile_result("   ")

    assert result.profile is None
    assert result.status == "not_found"
    mock_requests.assert_not_called()
