"""EngineLine: White-perspective normalization and PV stability."""

import chess
import chess.engine

from src.backend.analysis.engine_line import (
    EngineLine,
    line_from_cached,
    line_from_engine_info,
)

AFTER_E4 = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"


def test_engine_info_is_converted_to_white_perspective():
    board = chess.Board(AFTER_E4)
    info = {
        "score": chess.engine.PovScore(chess.engine.Cp(120), chess.BLACK),
        "depth": 16,
        "multipv": 2,
        "pv": [chess.Move.from_uci("e7e5"), chess.Move.from_uci("g1f3")],
    }

    line = line_from_engine_info(info, board)

    # Black is to move and +1.20 for Black, so White is -1.20.
    assert (line.rank, line.depth, line.cp, line.mate) == (2, 16, -120, None)
    assert line.first_move == "e7e5"
    assert line.pv_san == "1...e5 2. Nf3"
    assert line.score_text == "-1.20"
    assert line.score_tone == -1


def test_mate_scores_keep_their_sign():
    board = chess.Board(AFTER_E4)
    info = {
        "score": chess.engine.PovScore(chess.engine.Mate(3), chess.BLACK),
        "pv": [chess.Move.from_uci("e7e5")],
    }

    line = line_from_engine_info(info, board)

    assert line.mate == -3
    assert line.cp is None
    assert line.score_text == "-M3"


def test_cached_scores_flip_once_for_black_to_move():
    board = chess.Board(AFTER_E4)
    cached = {"cp": 20, "depth": 18, "pv_uci": ["e7e5"]}

    line = line_from_cached(cached, chess.BLACK, rank=1, board=board)

    assert line.cp == -20
    assert line.pv_san == "1...e5"
    assert line.depth == 18


def test_legacy_score_text_is_recovered():
    line = line_from_cached({"score_value": "M4", "pv": []}, chess.WHITE)
    assert line.mate == 4
    assert line.cp is None

    numeric = line_from_cached({"score_value": "+0.54", "pv": []}, chess.WHITE)
    assert numeric.cp == 54


def test_truncated_reemission_keeps_the_longer_continuation():
    previous = EngineLine(rank=1, depth=17, cp=104, pv_uci=("b3b4", "a7a5", "c2c4"))
    truncated = EngineLine(rank=1, depth=18, cp=110, pv_uci=("b3b4", "a7a5"))

    merged = truncated.with_longer_pv(previous)

    assert merged.pv_uci == previous.pv_uci
    assert merged.cp == 110  # the newer score still wins
    assert merged.depth == 18


def test_diverging_or_equal_pvs_are_not_merged():
    previous = EngineLine(rank=1, pv_uci=("e2e4", "e7e5", "g1f3"))
    diverging = EngineLine(rank=1, pv_uci=("e2e4", "c7c5"))
    equal = EngineLine(rank=1, pv_uci=previous.pv_uci)

    assert diverging.with_longer_pv(previous) is diverging
    assert equal.with_longer_pv(previous) is equal
