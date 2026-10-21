"""
Tests for the full-game fact sheet that grounds the AI summary.

Only the domain behaviour matters here: sign normalisation (``summary`` stores
per-side evaluations, the app is White-perspective), the cap/chronology of key
moments, and the graceful "not analysed yet" fallback.
"""

from __future__ import annotations

from src.backend.analysis.game_report import build_game_report
from src.backend.storage.models import GameAnalysis, GameMetadata


def _blunder(ply: int, san: str, drop: int, *, before: int, after: int) -> dict:
    return {
        "ply": ply,
        "move_number": ply // 2 + 1,
        "san": san,
        "classification": "Blunder",
        "eval_before_cp": before,
        "eval_after_cp": after,
        "eval_drop": drop,
    }


def _summary() -> dict:
    return {
        "white": {
            "accuracy": 78.4,
            "acpl": 42.5,
            "move_count": 30,
            "Best": 10,
            "Good": 5,
            "Inaccuracy": 2,
            "Blunder": 1,
            "Book": 4,
            "tactics": {
                "phase_accuracies": {"opening": 95.0, "middlegame": 60.0},
                "phase_move_counts": {"opening": 8, "middlegame": 12, "endgame": 0},
                "phase_blunders": {"opening": 0, "middlegame": 1, "endgame": 0},
                "advantage_metrics": {
                    "had_winning_advantage": True,
                    "converted_advantage": False,
                    "peak_eval_cp": 320,
                },
                "hanging_metrics": {
                    "total_hung": 1,
                    "by_piece": {"knight": 1},
                    "hanging_blunders": 1,
                    "opponent_hanging_missed": 2,
                },
                "tactical_themes": {"fork": 1, "pin": 0},
                "brilliancies": [{"move_number": 12, "san": "Nd5", "classification": "Brilliant"}],
                "blunders_details": [
                    _blunder(20, "Qh5", 325, before=45, after=-280),
                ],
            },
        },
        "black": {
            "accuracy": 71.2,
            "acpl": 55.0,
            "move_count": 29,
            "Best": 4,
            "Mistake": 1,
            "tactics": {
                "blunders_details": [
                    # Stored from Black's view: -30 means Black is better.
                    _blunder(31, "Nxe5", 280, before=-30, after=250),
                ],
            },
        },
    }


def _game(summary: dict | None = None) -> GameAnalysis:
    metadata = GameMetadata(
        white="Alice",
        black="Bob",
        white_elo="1800",
        black_elo="1750",
        result="1-0",
        speed_category="Rapid",
        opening="Sicilian Defense",
        eco="B20",
    )
    return GameAnalysis(game_id="report", metadata=metadata, summary=summary or {})


def test_an_unanalysed_game_produces_no_fact_sheet():
    assert build_game_report(_game()) == ""


def test_move_moments_are_reported_from_white_perspective():
    report = build_game_report(_game(_summary()))

    # White's own blunder keeps its sign...
    assert "11.Qh5 (white, Blunder): +0.45 -> -2.80, 3.25 pawns lost." in report
    # ...while Black's stored evaluation is flipped: -0.30 means Black was 0.3
    # better, i.e. +0.30 for White, and after the error Black is 2.5 down.
    assert "16...Nxe5 (black, Blunder): +0.30 -> -2.50, 2.80 pawns lost." in report


def test_the_fact_sheet_carries_the_numbers_the_summary_must_cite():
    report = build_game_report(_game(_summary()), user_side="black")

    assert "Alice (1800) (White) vs Bob (1750) (Black)" in report
    assert "accuracy 78.4%" in report and "average centipawn loss 42" in report
    assert "Move quality: Best 10, Good 5, Book 4, Inaccuracy 2, Blunder 1." in report
    assert "middlegame 60.0% (12 moves, 1 blunder)" in report
    assert "peak +3.20" in report and "did not convert it" in report
    assert "hung 1 piece(s) (knight 1)" in report and "missed 2 free piece(s)" in report
    assert "12.Nd5 (Brilliant)" in report
    assert "The report is for Bob, who played black" in report


def test_a_mate_score_is_not_reported_as_a_thousand_pawns():
    """Mate arrives as ±99999 cp from Stockfish; quoting that as a pawn count
    makes the model repeat a nonsense "999 pawns lost" swing."""
    summary = {
        "white": {
            "tactics": {
                "blunders_details": [_blunder(24, "Nge7", 99_983, before=16, after=99_999)],
                "advantage_metrics": {"had_winning_advantage": True, "peak_eval_cp": 99_999},
            }
        },
        "black": {"tactics": {}},
    }

    report = build_game_report(_game(summary))

    assert "mate for White" in report
    assert "999" not in report


def test_only_the_biggest_moments_survive_and_stay_chronological():
    summary = {
        "white": {"tactics": {"blunders_details": []}},
        "black": {"tactics": {"blunders_details": []}},
    }
    # Eight errors, alternating sides, with a monotonic drop so the survivors
    # are unambiguous.
    for index in range(8):
        side = "white" if index % 2 == 0 else "black"
        ply = index * 4 + (0 if side == "white" else 1)
        summary[side]["tactics"]["blunders_details"].append(
            _blunder(ply, f"M{index}", (index + 1) * 100, before=0, after=-(index + 1) * 100)
        )

    report = build_game_report(_game(summary))
    moments = [line for line in report.splitlines() if "(white," in line or "(black," in line]

    assert len(moments) == 6  # capped
    assert "M0" not in report and "M1" not in report  # the two smallest swings
    move_numbers = [int(line.split(".")[0]) for line in moments]
    assert move_numbers == sorted(move_numbers)
