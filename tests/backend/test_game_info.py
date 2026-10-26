"""Tests for GameInfo serialization and Lichess NDJSON conversion."""

import json

import pytest

from src.backend.models.game_info import GameInfo


def _ndjson(**overrides):
    payload = {
        "id": "abcd1234",
        "createdAt": 1_700_000_000_000,
        "winner": "white",
        "status": "resign",
        "speed": "blitz",
        "players": {
            "white": {"user": {"name": "Alice"}, "rating": 2100},
            "black": {"user": {"name": "Bob"}, "rating": 2000},
        },
        "opening": {"name": "Sicilian Defense"},
        "pgn": "1. e4 c5 2. Nf3 d6 3. d4 cxd4 1-0",
    }
    payload.update(overrides)
    return json.dumps(payload)


def test_serialization_round_trip_preserves_all_fields():
    original = GameInfo(
        game_id="g1",
        source="lichess",
        white="Alice",
        black="Bob",
        result="1-0",
        date="2024-01-01",
        pgn="1. e4 1-0",
        white_elo="2100",
        black_elo="2000",
        time_class="blitz",
        move_count=42,
        opening="Sicilian Defense",
        cached_at="2024-01-02 03:04:05",
    )

    assert GameInfo.from_dict(original.to_dict()) == original


def test_from_dict_applies_import_defaults():
    info = GameInfo.from_dict({})

    assert (info.game_id, info.source, info.white, info.black) == ("", "", "", "")
    assert (info.result, info.date, info.pgn) == ("*", "", "")
    assert info.move_count is None


def test_from_lichess_ndjson_maps_metadata():
    info = GameInfo.from_lichess_ndjson(_ndjson())

    assert info.source == "lichess"
    assert info.game_id == "abcd1234"
    assert (info.white, info.black) == ("Alice", "Bob")
    assert (info.white_elo, info.black_elo) == ("2100", "2000")
    assert info.result == "1-0"
    assert info.time_class == "blitz"
    assert info.opening == "Sicilian Defense"
    assert info.date.startswith("2023-11-")
    assert info.move_count == 3


@pytest.mark.parametrize(
    ("winner", "status", "expected"),
    [
        ("black", "resign", "0-1"),
        (None, "draw", "1/2-1/2"),
        (None, "stalemate", "1/2-1/2"),
        (None, "threefoldRepetition", "1/2-1/2"),
        (None, "insufficientMaterial", "1/2-1/2"),
        (None, "fiftyMoves", "1/2-1/2"),
        (None, "aborted", "*"),
    ],
)
def test_from_lichess_ndjson_maps_results(winner, status, expected):
    assert GameInfo.from_lichess_ndjson(_ndjson(winner=winner, status=status)).result == expected


def test_from_lichess_ndjson_handles_anonymous_players_and_missing_fields():
    info = GameInfo.from_lichess_ndjson(
        _ndjson(players={}, opening=None, pgn="", createdAt=0)
    )

    assert (info.white, info.black) == ("?", "?")
    assert (info.white_elo, info.black_elo) == (None, None)
    assert info.opening is None
    assert info.move_count is None
    assert info.date == "1970-01-01"


def test_from_lichess_ndjson_recovers_opening_from_pgn_headers():
    pgn = '[Opening "King\'s Pawn Game"]\n\n1. e4 e5 1/2-1/2'
    info = GameInfo.from_lichess_ndjson(_ndjson(opening=None, pgn=pgn))

    assert info.opening == "King's Pawn Game"
    assert info.move_count == 1


def test_from_lichess_ndjson_ignores_malformed_pgn():
    info = GameInfo.from_lichess_ndjson(_ndjson(pgn="not a pgn at all"))

    assert info.move_count == 0


def test_from_lichess_ndjson_survives_pgn_parser_exception(mocker):
    mocker.patch(
        "src.backend.models.game_info.chess.pgn.read_game",
        side_effect=ValueError("corrupt pgn"),
    )

    info = GameInfo.from_lichess_ndjson(_ndjson())

    assert info.move_count is None
