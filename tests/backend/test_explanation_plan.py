"""Claim selection for the Coach explanation pipeline.

The Bxh7+ fixture is a real engine line from a DecodeChess example position:
13.Bxh7+ Kxh7 14.Qh5+ Kg8 15.Ne4 g6 16.Nxc5. It is useful because the move is
a sound sacrifice, the second-best move loses the advantage, and a naive fact
sheet would call the offered bishop "undefended".
"""

from __future__ import annotations

import chess

from src.backend.analysis.tactics.explanation import (
    build_explanation_plan,
    format_plan_offline,
)
from src.backend.analysis.tactics.insight import (
    build_move_insight,
    format_move_insight_offline,
)
from src.backend.storage.models import GameMetadata, MoveAnalysis

BRILLIANT_FEN = "r4rk1/pp1b1ppp/2n1p3/2qp4/8/2PBP3/PP1N1PPP/R2QK2R w KQ - 0 13"
BRILLIANT_LINE = [
    "d3h7",
    "g8h7",
    "d1h5",
    "h7g8",
    "d2e4",
    "g7g6",
    "e4c5",
    "g6h5",
    "c5d7",
    "f8c8",
    "d7f6",
]
SECOND_LINE = ["e1g1", "h7h6", "a2a4", "c6e5", "d3c2", "c5b6"]
PUNISHED_LINE = ["g8h7", "d1h5", "h7g8", "d2e4", "g7g6", "e4c5", "g6h5", "c5d7"]


def _brilliant_insight():
    board = chess.Board(BRILLIANT_FEN)
    after = board.copy()
    after.push_uci("d3h7")
    played = MoveAnalysis(
        move_number=13,
        ply=24,
        san="Bxh7+",
        uci="d3h7",
        fen_before=BRILLIANT_FEN,
        classification="Brilliant",
        eval_before_cp=275,
        eval_after_cp=275,
        best_move="d3h7",
        multi_pvs=[
            {"pv": BRILLIANT_LINE, "cp": 275, "mate": None},
            {"pv": SECOND_LINE, "cp": -4, "mate": None},
        ],
        win_chance_before=0.60,
        win_chance_after=0.60,
    )
    reply = MoveAnalysis(
        move_number=13,
        ply=25,
        san="Kxh7",
        uci="g8h7",
        fen_before=after.fen(),
        classification="Best",
        multi_pvs=[{"pv": PUNISHED_LINE, "cp": 275, "mate": None}],
    )
    return build_move_insight(
        [played, reply],
        0,
        metadata=GameMetadata(white="W", black="B", white_elo="1434", black_elo="1311"),
    )


def test_brilliant_sacrifice_plan_names_the_offer_and_numbered_line():
    insight = _brilliant_insight()
    plan = build_explanation_plan(insight)

    assert plan.kind == "sacrifice"
    assert "bishop on h7" in plan.verdict
    assert "14. Qh5+" in plan.line
    assert "O-O" in " ".join(plan.evidence)
    assert "-0.04" in " ".join(plan.evidence)

    text = format_plan_offline(plan).lower()
    assert "sacrifice" in text
    assert "undefended" not in text
    assert "at risk" not in text


def test_brilliant_sacrifice_offline_text_quotes_the_real_continuation():
    text = format_move_insight_offline(_brilliant_insight())

    assert "13.Bxh7+" in text
    assert "Kxh7 14. Qh5+" in text
    assert "Ne4" in text


def test_preexisting_loose_piece_is_not_blamed_on_the_move():
    fen = "3r2k1/8/8/8/8/8/3Q4/6K1 w - - 0 1"
    board = chess.Board(fen)
    played = MoveAnalysis(
        move_number=1,
        ply=0,
        san="Kh1",
        uci=board.parse_san("Kh1").uci(),
        fen_before=fen,
        classification="Inaccuracy",
        win_chance_before=0.5,
        win_chance_after=0.45,
    )

    insight = build_move_insight([played], 0, metadata=GameMetadata())
    plan = build_explanation_plan(insight)
    text = format_plan_offline(plan).lower()

    assert insight.new_hung_pieces == []
    assert "newly" not in text
    assert "d2" not in text


def test_error_plan_names_the_punishment_line():
    fen = "3r2k1/8/8/8/8/8/3Q4/6K1 w - - 0 1"
    board = chess.Board(fen)
    after = board.copy()
    after.push_san("Kh1")
    played = MoveAnalysis(
        move_number=1,
        ply=0,
        san="Kh1",
        uci=board.parse_san("Kh1").uci(),
        fen_before=fen,
        classification="Blunder",
        win_chance_before=0.5,
        win_chance_after=0.05,
    )
    reply = MoveAnalysis(
        move_number=1,
        ply=1,
        san="Rxd2",
        uci="d8d2",
        fen_before=after.fen(),
        classification="Best",
        multi_pvs=[{"pv": ["d8d2"], "cp": 900, "mate": None}],
    )

    insight = build_move_insight([played, reply], 0, metadata=GameMetadata())
    plan = build_explanation_plan(insight)
    text = format_plan_offline(plan).lower()

    assert plan.kind == "error"
    assert "1...Rxd2" in plan.line
    assert "about 9.0 pawns" in text
    assert "newly" not in text
