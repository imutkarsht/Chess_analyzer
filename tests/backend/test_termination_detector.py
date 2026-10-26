import pytest

from src.backend.storage.models import MoveAnalysis
from src.backend.storage.pgn_parser import PGNParser
from src.backend.storage.termination_detector import TerminationDetector


def test_detect_checkmate_via_board():
    pgn = """[Event "Test"]
[White "Player1"]
[Black "Player2"]
[Result "1-0"]

1. f3 e5 2. g4 Qh4# 0-1"""
    games = PGNParser.parse_pgn_text(pgn)
    assert len(games) == 1
    meta = games[0].metadata
    assert meta.termination_mode == "checkmate"
    assert "won by checkmate" in meta.termination_description


def test_detect_stalemate_via_board():
    # Note: 1... h5 from that FEN is stalemate if illegal or no moves; let's test a clean stalemate FEN setup
    headers = {"Result": "1/2-1/2", "White": "Player1", "Black": "Player2"}
    # FEN where black has no moves and is not in check
    mode, desc = TerminationDetector.detect_termination(headers, [], starting_fen="k7/1R6/1K6/8/8/8/8/8 b - - 0 1")
    assert mode == "stalemate"
    assert desc == "Drawn by stalemate"


def test_detect_chesscom_resignation_header():
    headers = {
        "Result": "1-0",
        "White": "Alice",
        "Black": "Bob",
        "Termination": "Alice won by resignation"
    }
    mode, desc = TerminationDetector.detect_termination(headers, [])
    assert mode == "resignation"
    assert desc == "Alice won by resignation"


def test_detect_lichess_time_forfeit():
    headers = {
        "Result": "0-1",
        "White": "Alice",
        "Black": "Bob",
        "Termination": "Time forfeit"
    }
    mode, desc = TerminationDetector.detect_termination(headers, [])
    assert mode == "timeout"
    assert desc == "Bob won on time"


def test_detect_abandonment():
    headers = {
        "Result": "1-0",
        "White": "Alice",
        "Black": "Bob",
        "Termination": "Alice won - game abandoned"
    }
    mode, desc = TerminationDetector.detect_termination(headers, [])
    assert mode == "abandonment"
    assert desc == "Alice won - game abandoned"


def test_detect_headerless_resignation_fallback():
    headers = {
        "Result": "1-0",
        "White": "Alice",
        "Black": "Bob"
    }
    mode, desc = TerminationDetector.detect_termination(headers, [])
    assert mode == "resignation"
    assert desc == "Alice won by resignation"


def test_detect_headerless_agreed_draw_fallback():
    headers = {
        "Result": "1/2-1/2",
        "White": "Alice",
        "Black": "Bob"
    }
    mode, desc = TerminationDetector.detect_termination(headers, [])
    assert mode == "agreed_draw"
    assert desc == "Drawn by agreement"


@pytest.mark.parametrize(
    ("termination", "result", "expected_mode", "expected_desc"),
    [
        ("Rules infraction", "1-0", "rules_violation", "Alice won by rules violation"),
        ("Disqualified for cheating", "0-1", "rules_violation", "Bob won by rules violation"),
        ("Cheating", "*", "rules_violation", "Game won by rules violation"),
        ("Time forfeit", "1/2-1/2", "timeout_insufficient", "Drawn on time (insufficient material)"),
        ("Draw by repetition", "1/2-1/2", "threefold_repetition", "Drawn by repetition"),
        ("Draw by 50-move rule", "1/2-1/2", "fifty_moves", "Drawn by 50-move rule"),
        ("Draw by insufficient material", "1/2-1/2", "insufficient_material", "Drawn by insufficient material"),
        ("Game drawn by mutual agreement", "1/2-1/2", "agreed_draw", "Drawn by agreement"),
    ],
)
def test_termination_header_keywords(
    termination, result, expected_mode, expected_desc
):
    headers = {
        "Result": result,
        "White": "Alice",
        "Black": "Bob",
        "Termination": termination,
    }

    assert TerminationDetector.detect_termination(headers, []) == (
        expected_mode,
        expected_desc,
    )


def test_insufficient_material_is_detected_from_the_board():
    headers = {"Result": "1/2-1/2", "White": "Alice", "Black": "Bob"}

    mode, desc = TerminationDetector.detect_termination(
        headers, [], starting_fen="k7/8/8/8/8/8/8/K6k w - - 0 1"
    )

    assert (mode, desc) == ("insufficient_material", "Drawn by insufficient material")


def test_threefold_repetition_is_detected_from_replayed_moves():
    pgn = (
        '[Event "Test"]\n[White "A"]\n[Black "B"]\n[Result "1/2-1/2"]\n\n'
        "1. Nf3 Nf6 2. Ng1 Ng8 3. Nf3 Nf6 4. Ng1 Ng8 1/2-1/2"
    )

    game = PGNParser.parse_pgn_text(pgn)[0]

    assert game.metadata.termination_mode == "threefold_repetition"


def test_fifty_move_claim_is_detected_from_the_halfmove_clock():
    pgn = (
        '[Event "Test"]\n[White "A"]\n[Black "B"]\n[Result "1/2-1/2"]\n'
        '[FEN "k7/8/8/8/8/8/R7/K7 w - - 99 60"]\n[SetUp "1"]\n\n60. Rb2 1/2-1/2'
    )

    game = PGNParser.parse_pgn_text(pgn)[0]

    assert game.metadata.termination_mode == "fifty_moves"


@pytest.mark.parametrize(
    ("result", "ply", "winner"),
    [("1-0", 2, "Alice"), ("0-1", 1, "Bob")],
)
def test_zero_clock_fallback_detects_timeout(result, ply, winner):
    headers = {"Result": result, "White": "Alice", "Black": "Bob"}
    moves = [
        MoveAnalysis(
            move_number=1,
            ply=ply,
            san="e4" if ply == 1 else "e5",
            uci="e2e4" if ply == 1 else "e7e5",
            fen_before="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
            time_left=0,
        )
    ]

    mode, desc = TerminationDetector.detect_termination(headers, moves)

    assert mode == "timeout"
    assert desc == f"{winner} won on time"
