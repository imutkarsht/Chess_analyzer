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


def _game(
    pgn: str | None = None, moves: list[MoveAnalysis] | None = None
) -> GameAnalysis:
    return GameAnalysis(
        game_id="export-test",
        metadata=GameMetadata(headers={}),
        moves=moves or [],
        pgn_content=pgn if pgn is not None else (_TWO_MOVES_PGN if not moves else None),
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
        ("Miss", 6),
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
    pgn = _TWO_MOVES_PGN.replace(
        "1. e4 e5 *",
        f"1. e4 {{{'review note ' * 8}[%clk 0:09:56.1]}} e5 *",
    )

    exported = AnnotatedPGNExporter.export_game(_game(pgn, moves))
    parsed = _read_game(exported)
    first, second = list(parsed.mainline())

    assert "[%eval +0.34]" in first.comment
    assert "[%depth 18]" in first.comment
    assert first.comment.count("[%clk") == 1
    assert "[%clk 0:09:56.1]" in first.comment
    assert "[%clk 0:09:56.1]" in exported
    assert "[%eval #-3]" in second.comment


def test_annotations_follow_stored_move_identity_and_reject_misalignment():
    move = _move(
        0,
        "d4",
        "d2d4",
        chess.STARTING_FEN,
        classification="Blunder",
        eval_after_cp=-500,
    )

    with pytest.raises(ValueError, match="does not match the PGN mainline"):
        AnnotatedPGNExporter.export_game(
            _game('[Event "Training"]\n[Result "*"]\n\n1. e4 *', [move])
        )


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


def test_shared_pv_prefixes_merge_at_the_divergence_and_pvs_are_bounded():
    board = chess.Board()
    move = _move(
        0,
        "e4",
        "e2e4",
        board.fen(),
        multi_pvs=[
            {"pv": ["e2e4", "c7c5", "g1f3"], "depth": 18},
            {"pv": ["e2e4", "c7c5", "b1c3"], "depth": 17},
        ],
    )
    board.push_uci("e2e4")
    e5 = _move(1, "e5", "e7e5", board.fen())
    long_move = _move(
        0,
        "e4",
        "e2e4",
        chess.STARTING_FEN,
        pv=[
            "d2d4", "d7d5", "c2c4", "e7e6", "b1c3", "g8f6",
            "c1g5", "f8e7", "e2e3", "e8g8", "g1f3", "b8d7", "f1d3",
        ],
    )

    parsed = _read_game(
        AnnotatedPGNExporter.export_game(_game(_TWO_MOVES_PGN, [move, e5]))
    )
    e4 = parsed.variation(0)
    c5 = next(child for child in e4.variations if child.move.uci() == "c7c5")
    assert {child.move.uci() for child in c5.variations} == {"g1f3", "b1c3"}

    bounded = _read_game(
        AnnotatedPGNExporter.export_game(_game(_TWO_MOVES_PGN, [long_move, e5]))
    )
    alternative = bounded.variations[1]
    assert 1 + len(list(alternative.mainline_moves())) == 12


def test_null_pv_fields_and_best_line_depth_are_safe():
    move = _move(0, "e4", "e2e4", chess.STARTING_FEN)
    move.multi_pvs = None
    move.pv = None

    assert len(
        list(
            _read_game(
                AnnotatedPGNExporter.export_game(_game(moves=[move]))
            ).mainline_moves()
        )
    ) == 1

    move.multi_pvs = [
        {"pv": ["d2d4"], "depth": 18},
        {"pv": ["c2c4"], "depth": 40},
    ]
    parsed = _read_game(AnnotatedPGNExporter.export_game(_game(moves=[move])))
    assert "[%depth 18]" in parsed.variation(0).comment
    assert "[%depth 40]" not in parsed.variation(0).comment


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


@pytest.mark.parametrize(
    ("content", "move_count"),
    [
        ("nonsense", None),
        ('[Event "Broken"]\n\n1. not-a-move *', 1),
    ],
)
def test_corrupt_pgn_is_rejected(content, move_count):
    game = _game(content)
    game.metadata.move_count = move_count

    with pytest.raises(ValueError, match="(no PGN headers or moves|invalid PGN|expected)"):
        AnnotatedPGNExporter.export_game(game)


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
