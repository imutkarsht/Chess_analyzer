from src.backend.storage.termination_detector import TerminationDetector
from src.backend.storage.pgn_parser import PGNParser


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
    pgn = """[Event "Test"]
[White "Player1"]
[Black "Player2"]
[Result "1/2-1/2"]
[FEN "k7/8/1Q6/8/8/8/8/K7 b - - 0 1"]

1... h5 1/2-1/2"""
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
