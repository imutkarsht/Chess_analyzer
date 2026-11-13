# SPDX-License-Identifier: GPL-3.0-only
"""Tests for the per-game tactics report projection."""

from __future__ import annotations

from dataclasses import dataclass

from src.backend.analysis.tactics.report import build_game_tactics_report

START = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
AFTER_E4 = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"
AFTER_E5 = "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2"


@dataclass(frozen=True)
class FakeMove:
    ply: int
    uci: str
    san: str
    move_number: int
    fen_before: str


MOVES = [
    FakeMove(0, "e2e4", "e4", 1, START),
    FakeMove(1, "e7e5", "e5", 1, AFTER_E4),
    FakeMove(2, "g1f3", "Nf3", 2, AFTER_E5),
    FakeMove(3, "b8c6", "Nc6", 2, "rnbqkbnr/pppp1ppp/8/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R b KQkq - 1 2"),
]


def _tactics() -> dict:
    return {
        "tactical_motifs_details": [
            {
                "motif": "fork",
                "role": "executed",
                "ply": 2,
                "uci": "g1f3",
                "san": "Nf3",
                "evidence": "attacks e5 and d4",
                "classification": "Best",
                "eval_before_cp": 20,
                "eval_after_cp": 40,
                "target_square": "e5",
                "target_piece": "pawn",
            },
            {
                "motif": "hanging_piece",
                "role": "executed",
                "ply": 2,
                "uci": "g1f3",
                "san": "Nf3",
                "evidence": "captures a piece that was already hanging",
                "classification": "Best",
            },
            {
                "motif": "pin",
                "role": "allowed",
                "ply": 3,
                "uci": "b8c6",
                "san": "Nc6",
                "blunder_ply": 2,
                "blunder_san": "Nf3",
                "evidence": "line c6-e4-e1",
                "classification": "Mistake",
                "target_square": "e4",
            },
        ],
        "hung_pieces_details": [
            {
                "ply": 2,
                "uci": "g1f3",
                "piece_name": "knight",
                "square": "f3",
                "loss_kind": "punished",
                "punished_by": "Bg5",
                "classification": "Blunder",
                "eval_before_cp": 20,
                "eval_after_cp": -300,
            }
        ],
        "opp_captured_details": [
            {
                "ply": 1,
                "uci": "e7e5",
                "piece_name": "pawn",
                "square": "e5",
                "classification": "Best",
            }
        ],
        "missed_tactics_details": [
            {
                "ply": 2,
                "uci": "g1f3",
                "motif": "hanging_piece",
                "missed_piece": "knight",
                "missed_square": "e5",
                "classification": "Mistake",
            }
        ],
    }


def test_report_projects_all_roles_and_move_indices():
    report = build_game_tactics_report(_tactics(), MOVES, side="white")

    assert report.side == "white"
    assert report.total == 5
    assert report.summary == {
        "executed": 1,
        "allowed": 1,
        "missed": 1,
        "lost": 1,
        "won": 1,
    }

    executed = report.executed[0]
    assert executed.motif == "fork"
    assert executed.move_index == 2
    assert executed.move_label == "2. Nf3"
    assert executed.eval_text == "+0.2 → +0.4"
    assert executed.summary == "attacks e5 and d4"

    allowed = report.allowed[0]
    assert allowed.move_index == 2
    assert allowed.move_label == "2. Nf3"
    assert allowed.summary == "Allowed Nc6"

    missed = report.missed[0]
    assert missed.summary == "Missed knight on e5"

    lost = report.lost[0]
    assert lost.summary == "Knight f3 · Bg5"

    won = report.won[0]
    assert won.summary == "Won pawn e5"


def test_multiple_losses_on_one_move_are_grouped():
    tactics = {
        "hung_pieces_details": [
            {
                "ply": 2,
                "uci": "g1f3",
                "piece_name": "pawn",
                "square": "a5",
                "loss_kind": "immediate",
            },
            {
                "ply": 2,
                "uci": "g1f3",
                "piece_name": "pawn",
                "square": "d5",
                "loss_kind": "punished",
                "punished_by": "Qxd5",
            },
        ]
    }

    report = build_game_tactics_report(tactics, MOVES)

    assert len(report.lost) == 1
    assert report.lost[0].summary == "Pawns a5, d5"
    assert report.lost[0].details == (
        "Pawn a5 · immediate",
        "Pawn d5 · Qxd5",
    )


def test_hanging_piece_is_not_counted_as_an_executed_tactic():
    report = build_game_tactics_report(_tactics(), MOVES, side="white")
    assert all(entry.motif != "hanging_piece" for entry in report.executed)


def test_missing_or_unknown_ply_is_skipped():
    tactics = {
        "tactical_motifs_details": [
            {
                "motif": "fork",
                "role": "executed",
                "ply": 99,
                "uci": "zzzz",
                "evidence": "nowhere",
            }
        ]
    }
    report = build_game_tactics_report(tactics, MOVES)
    assert report.is_empty


def test_empty_report_is_safe():
    report = build_game_tactics_report({}, [], side="black")
    assert report.is_empty
    assert report.side == "black"
    assert report.total == 0


def test_move_label_uses_the_position_turn_not_only_ply_parity():
    # Black to move in a custom start: the label must be 1..., not 1.
    moves = [
        FakeMove(
            0,
            "e7e5",
            "e5",
            1,
            "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR b KQkq - 0 1",
        )
    ]
    report = build_game_tactics_report(
        {
            "tactical_motifs_details": [
                {
                    "motif": "fork",
                    "role": "executed",
                    "ply": 0,
                    "uci": "e7e5",
                    "evidence": "...",
                }
            ]
        },
        moves,
    )
    assert report.executed[0].move_label == "1... e5"
