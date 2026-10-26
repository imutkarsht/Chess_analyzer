"""Tests for PGN-header extraction and the API game cache layer."""

import datetime
import hashlib

from src.backend.api.chess_com_api import ChessComAPI
from src.backend.api.lichess_api import LichessAPI
from src.backend.cache.api_cache import ApiGameCache, parse_pgn_headers
from src.backend.models.game_info import GameInfo

FULL_PGN = """[White "Alice"]
[Black "Bob"]
[Result "1-0"]
[Date "2024.05.06"]
[WhiteElo "2100"]
[BlackElo "2000"]
[Event "Rated Blitz game"]
[Opening "Sicilian Defense"]

1. e4 c5 2. Nf3 d6 1-0"""


def test_parse_pgn_headers_prefers_pgn_metadata():
    (
        white,
        black,
        result,
        date_str,
        white_elo,
        black_elo,
        time_class,
        opening,
        move_count,
    ) = parse_pgn_headers(FULL_PGN, default_white="?", default_black="?")

    assert (white, black, result) == ("Alice", "Bob", "1-0")
    assert date_str == "2024-05-06"
    assert (white_elo, black_elo) == ("2100", "2000")
    assert time_class == "Rated Blitz game"
    assert opening == "Sicilian Defense"
    assert move_count == 2


def test_parse_pgn_headers_keeps_defaults_for_missing_metadata():
    result = parse_pgn_headers(
        "1. e4",
        default_white="Default White",
        default_black="Default Black",
        default_result="0-1",
        default_date_str="2024-01-01",
        default_white_elo="1200",
        default_black_elo="1100",
        default_time_class="rapid",
        default_opening="Unknown",
    )

    assert result == (
        "Default White",
        "Default Black",
        "0-1",
        "2024-01-01",
        "1200",
        "1100",
        "rapid",
        "Unknown",
        1,
    )


def test_parse_pgn_headers_ignores_placeholder_values():
    pgn = """[White "?"]
[Black "?"]
[Result "*"]
[Date "????.??.??"]
[WhiteElo "?"]
[BlackElo "?"]
[Event "Lichess Game"]

1. e4"""

    white, black, result, date_str, white_elo, _, time_class, _, _ = parse_pgn_headers(
        pgn, "Default", "Default"
    )

    assert (white, black) == ("Default", "Default")
    assert (result, date_str, white_elo) == ("*", "????-??-??", None)
    assert time_class is None


def test_parse_pgn_headers_survives_malformed_pgn(mocker):
    mocker.patch("src.backend.cache.api_cache.chess.pgn.read_game", side_effect=ValueError)
    result = parse_pgn_headers('[White "unterminated', default_white="Fallback")

    assert result[0] == "Fallback"
    assert result[-1] is None


class TestApiGameCacheById:
    def test_cache_hit_skips_fetch(self, mocker):
        history = mocker.Mock()
        cached = GameInfo("g1", "lichess", "A", "B", "1-0", "2024-01-01", "")
        history.get_cached_game.return_value = cached
        fetch = mocker.Mock()
        cache = ApiGameCache(history)

        assert cache.get_by_id("lichess", "g1", fetch) is cached
        fetch.assert_not_called()

    def test_cache_miss_fetches_and_saves(self, mocker):
        history = mocker.Mock()
        history.get_cached_game.return_value = None
        fetch = mocker.Mock(
            return_value={
                "pgn": FULL_PGN,
                "white": "Fallback",
                "white_rating": 1500,
                "time_class": "blitz",
            }
        )
        cache = ApiGameCache(history)

        info = cache.get_by_id("lichess", "g1", fetch)

        assert info.game_id == "g1"
        assert info.white == "Alice"  # PGN header wins over the fallback
        assert info.white_elo == "2100"
        history.save_cached_game.assert_called_once_with(info)

    def test_missing_pgn_is_not_cached(self, mocker):
        history = mocker.Mock()
        history.get_cached_game.return_value = None
        cache = ApiGameCache(history)

        assert cache.get_by_id("lichess", "g1", mocker.Mock(return_value={})) is None
        history.save_cached_game.assert_not_called()


class TestApiGameCacheByDate:
    def test_cache_hit_returns_saved_games(self, mocker):
        history = mocker.Mock()
        cached = [GameInfo("g1", "lichess", "A", "B", "1-0", "2024-01-01", "pgn")]
        history.get_cached_games_for_date.return_value = cached
        fetch = mocker.Mock()
        cache = ApiGameCache(history)

        games = cache.get_by_date(
            "lichess", "Alice", datetime.date(2024, 1, 1), fetch
        )

        assert games == cached
        fetch.assert_not_called()
        history.get_cached_games_for_date.assert_called_once_with(
            "lichess", "2024-01-01", "Alice"
        )

    def test_fetch_parses_and_bulk_saves(self, mocker):
        history = mocker.Mock()
        history.get_cached_games_for_date.return_value = []
        mocker.patch.object(LichessAPI, "extract_game_id", return_value="abc123")
        raw = [
            {
                "url": "https://lichess.org/abc123",
                "pgn": FULL_PGN,
                "white": {"username": "Alice", "rating": 2100},
                "black": {"username": "Bob", "rating": 2000},
                "time_class": "blitz",
            },
            {"url": "https://lichess.org/no-pgn", "pgn": ""},
        ]
        cache = ApiGameCache(history)

        games = cache.get_by_date(
            "lichess", "Alice", datetime.date(2024, 1, 1), mocker.Mock(return_value=raw)
        )

        assert len(games) == 1
        assert games[0].game_id == "abc123"
        history.save_cached_games_bulk.assert_called_once_with(games)

    def test_chesscom_games_use_chesscom_id_extractor(self, mocker):
        history = mocker.Mock()
        history.get_cached_games_for_date.return_value = []
        extract = mocker.patch.object(ChessComAPI, "extract_game_id", return_value="999")
        raw = [{"url": "https://www.chess.com/game/live/999", "pgn": FULL_PGN}]
        cache = ApiGameCache(history)

        games = cache.get_by_date(
            "chesscom", "Alice", datetime.date(2024, 1, 1), mocker.Mock(return_value=raw)
        )

        extract.assert_called_once_with("https://www.chess.com/game/live/999")
        assert games[0].game_id == "999"
        assert games[0].source == "chesscom"

    def test_missing_url_falls_back_to_pgn_hash(self, mocker):
        history = mocker.Mock()
        history.get_cached_games_for_date.return_value = []
        raw = [{"url": "", "pgn": FULL_PGN}]
        cache = ApiGameCache(history)

        games = cache.get_by_date(
            "chesscom", "Alice", datetime.date(2024, 1, 1), mocker.Mock(return_value=raw)
        )

        assert games[0].game_id == hashlib.md5(FULL_PGN.encode()).hexdigest()

    def test_empty_fetch_returns_empty_list(self, mocker):
        history = mocker.Mock()
        history.get_cached_games_for_date.return_value = []
        cache = ApiGameCache(history)

        assert cache.get_by_date(
            "lichess", "Alice", datetime.date(2024, 1, 1), mocker.Mock(return_value=[])
        ) == []
        history.save_cached_games_bulk.assert_not_called()


class TestApiGameCacheRecent:
    def test_recent_always_fetches_and_saves(self, mocker):
        history = mocker.Mock()
        mocker.patch.object(LichessAPI, "extract_game_id", return_value="recent1")
        fetch = mocker.Mock(
            return_value=[{"url": "https://lichess.org/recent1", "pgn": FULL_PGN}]
        )
        cache = ApiGameCache(history)

        games = cache.get_recent("lichess", "Alice", 10, fetch)

        fetch.assert_called_once()
        assert games[0].game_id == "recent1"
        history.save_cached_games_bulk.assert_called_once_with(games)

    def test_recent_without_fetch_results_returns_empty(self, mocker):
        cache = ApiGameCache(mocker.Mock())

        assert cache.get_recent("lichess", "Alice", 10, mocker.Mock(return_value=None)) == []
