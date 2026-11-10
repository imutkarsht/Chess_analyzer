import io

import chess
import chess.pgn
import pytest

from src.backend.storage.annotated_pgn import AnnotatedPGNExporter
from src.backend.storage.models import GameAnalysis, GameMetadata, MoveAnalysis

_TWO_MOVES_PGN = """\
[Event "Training"]
[Site "Local"]
[Date "2026.01.02"]
[Round "1"]
[White "Alice"]
[Black "Bob"]
[Result "*"]
[TimeControl "600"]

1. e4 e5 *
"""


def _move(
    ply: int,
    san: str,
    uci: str,
    fen_before: str,
    **kwargs,
) -> MoveAnalysis:
    return MoveAnalysis(
        move_number=ply // 2 + 1,
        ply=ply,
        san=san,
        uci=uci,
        fen_before=fen_before,
        **kwargs,
    )


def _game(pgn: str = _TWO_MOVES_PGN, moves: list[MoveAnalysis] | None = None) -> GameAnalysis:
    return GameAnalysis(
        game_id="export-test",
        metadata=GameMetadata(headers={}),
        moves=moves or [],
        pgn_content=pgn,
    )


def _read_game(pgn: str) -> chess.pgn.Game:
    parsed = chess.pgn.read_game(io.StringIO(pgn))
    assert parsed is not None
    assert not parsed.errors
    return parsed


@pytest.mark.parametrize(
    ("classification", "expected_nag"),
    [
        ("Brilliant", 3),
        ("Great", 1),
        ("Best", None),
        ("Excellent", None),
        ("Good", None),
        ("Book", None),
        ("Inaccuracy", 6),
        ("Mistake", 2),
        ("Blunder", 4),
        ("Miss", 5),
    ],
)
def test_classifications_map_to_standard_nags(classification, expected_nag):
    move = _move(0, "e4", "e2e4", chess.STARTING_FEN, classification=classification)

    exported = AnnotatedPGNExporter.export_game(_game(moves=[move]))
    parsed = _read_game(exported)
    nags = parsed.variation(0).nags

    if expected_nag is None:
        assert not nags
    else:
        assert nags == {expected_nag}


def test_annotations_use_white_evaluation_and_preserve_existing_clock_tag():
    board = chess.Board()
    e4 = board.parse_san("e4")
    board.push(e4)
    moves = [
        _move(
            0,
            "e4",
            "e2e4",
            chess.STARTING_FEN,
            eval_after_cp=34,
            raw_clk="0:09:55.5",
            multi_pvs=[{"pv": ["e2e4", "e7e5"], "depth": 18}],
        ),
        _move(1, "e5", "e7e5", board.fen(), eval_after_mate=-3),
    ]
    pgn = _TWO_MOVES_PGN.replace("1. e4 e5 *", "1. e4 {[%clk 0:09:56.1]} e5 *")

    exported = AnnotatedPGNExporter.export_game(_game(pgn, moves))
    parsed = _read_game(exported)
    first, second = list(parsed.mainline())

    assert "[%eval +0.34]" in first.comment
    assert "[%depth 18]" in first.comment
    assert first.comment.count("[%clk") == 1
    assert "[%clk 0:09:56.1]" in first.comment
    assert "[%eval #-3]" in second.comment


def test_clock_is_added_from_seconds_when_raw_tag_is_missing():
    move = _move(0, "e4", "e2e4", chess.STARTING_FEN, time_left=596.5)

    parsed = _read_game(AnnotatedPGNExporter.export_game(_game(moves=[move])))

    assert "[%clk 0:09:56.5]" in parsed.variation(0).comment


def test_engine_pvs_are_added_as_legal_variations_and_illegal_tail_is_truncated():
    move = _move(
        0,
        "e4",
        "e2e4",
        chess.STARTING_FEN,
        multi_pvs=[
            {"pv": ["d2d4", "d7d5", "not-a-move"], "depth": 20},
            {"pv": ["c2c4", "e7e5"], "depth": 19},
        ],
    )

    parsed = _read_game(AnnotatedPGNExporter.export_game(_game(moves=[move])))
    root_moves = [variation.move.uci() for variation in parsed.variations]

    assert root_moves == ["e2e4", "d2d4", "c2c4"]
    assert [move.uci() for move in parsed.variations[1].mainline_moves()] == ["d7d5"]


def test_stored_best_pv_is_added_when_multpv_is_empty():
    move = _move(0, "e4", "e2e4", chess.STARTING_FEN, pv=["d2d4", "d7d5"])

    parsed = _read_game(AnnotatedPGNExporter.export_game(_game(moves=[move])))

    assert [variation.move.uci() for variation in parsed.variations] == ["e2e4", "d2d4"]


def test_unanalyzed_game_and_custom_headers_round_trip():
    game = _game()
    game.metadata.headers = {"ECO": "C20", "Annotator": "Local"}

    parsed = _read_game(AnnotatedPGNExporter.export_game(game))

    assert parsed.headers["White"] == "Alice"
    assert parsed.headers["ECO"] == "C20"
    assert parsed.headers["Annotator"] == "Local"
    assert len(list(parsed.mainline_moves())) == 2
    assert all(not node.nags for node in parsed.mainline())


def test_nonstandard_fen_and_chess960_setup_are_preserved():
    fen = "4k3/8/8/8/8/8/8/4K2R w K - 0 1"
    nonstandard = GameAnalysis(
        game_id="fen",
        metadata=GameMetadata(starting_fen=fen, headers={}),
    )
    fen_game = _read_game(AnnotatedPGNExporter.export_game(nonstandard))
    assert fen_game.headers["SetUp"] == "1"
    assert fen_game.headers["FEN"] == fen

    chess960_board = chess.Board.from_chess960_pos(42)
    chess960 = GameAnalysis(
        game_id="chess960",
        metadata=GameMetadata(
            starting_fen=chess960_board.fen(),
            chess960=True,
            headers={},
        ),
    )
    chess960_game = _read_game(AnnotatedPGNExporter.export_game(chess960))
    assert chess960_game.headers["Variant"] == "Chess960"
    assert chess960_game.board().chess960
    assert chess960_game.headers["FEN"] == chess960_board.fen()


def test_chess960_pgn_without_variant_header_uses_stored_variant_metadata():
    board = chess.Board.from_chess960_pos(42)
    fen = board.fen()
    pgn = f'[Event "Chess960"]\n[SetUp "1"]\n[FEN "{fen}"]\n\n*'
    game = GameAnalysis(
        game_id="chess960-source-pgn",
        metadata=GameMetadata(starting_fen=fen, chess960=True, headers={}),
        pgn_content=pgn,
    )

    parsed = _read_game(AnnotatedPGNExporter.export_game(game))

    assert parsed.headers["Variant"] == "Chess960"
    assert parsed.board().chess960


def test_batch_export_round_trips_as_multiple_games():
    exported = AnnotatedPGNExporter.export_games([_game(), _game()])
    pgn_stream = io.StringIO(exported)

    assert chess.pgn.read_game(pgn_stream) is not None
    assert chess.pgn.read_game(pgn_stream) is not None
    assert chess.pgn.read_game(pgn_stream) is None
    assert AnnotatedPGNExporter.export_games([]) == ""
