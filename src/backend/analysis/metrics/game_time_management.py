# SPDX-License-Identifier: GPL-3.0-only
"""Per-game clock summaries shared by Analysis and time-management metrics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.backend.storage.models import MoveAnalysis

LOW_CLOCK_SECONDS = 30.0
STARTING_CLOCK_FRACTION = 0.30


@dataclass(frozen=True)
class GameTimeManagement:
    average_think_time: float | None
    blunder_think_time: float | None
    best_think_time: float | None
    time_trouble_blunders: int


def starting_clock_seconds(time_control: str | None) -> float | None:
    """Parse initial seconds from PGN TimeControl notation."""
    if not time_control or time_control in ("-", "?"):
        return None
    first_period = time_control.split(":", 1)[0].split("+", 1)[0]
    seconds = first_period.rsplit("/", 1)[-1]
    try:
        value = float(seconds)
    except ValueError:
        return None
    return value if value > 0 else None


def has_clock_data(moves: list[MoveAnalysis]) -> bool:
    return any(move.time_left is not None or bool(move.raw_clk) for move in moves)


def is_time_trouble(move: MoveAnalysis) -> bool:
    return move.time_left is not None and move.time_left < LOW_CLOCK_SECONDS


def is_disproportionate(move: MoveAnalysis, starting_clock: float | None) -> bool:
    return bool(
        starting_clock
        and move.time_spent is not None
        and move.time_spent > starting_clock * STARTING_CLOCK_FRACTION
    )


def summarize_game_time(
    moves: list[MoveAnalysis],
    clock_metrics: list[dict[str, Any]] | None = None,
) -> GameTimeManagement:
    """Summarize stored Metrics clock data, falling back to move annotations."""
    if clock_metrics:
        timed_moves = sum(item.get("total_timed_moves", 0) for item in clock_metrics)
        quality_time = {
            key: sum(
                item.get("quality_time_spent", {}).get(key, 0.0)
                for item in clock_metrics
            )
            for key in ("best", "blunder")
        }
        quality_moves = {
            key: sum(
                item.get("quality_timed_moves", {}).get(key, 0)
                for item in clock_metrics
            )
            for key in ("best", "blunder")
        }
        return GameTimeManagement(
            average_think_time=(
                sum(item.get("total_time_spent", 0.0) for item in clock_metrics)
                / timed_moves
                if timed_moves
                else None
            ),
            blunder_think_time=(
                quality_time["blunder"] / quality_moves["blunder"]
                if quality_moves["blunder"]
                else None
            ),
            best_think_time=(
                quality_time["best"] / quality_moves["best"]
                if quality_moves["best"]
                else None
            ),
            time_trouble_blunders=sum(
                item.get("trouble_blunders", 0) for item in clock_metrics
            ),
        )

    timed = [move for move in moves if move.time_spent is not None]

    def average_for(classification: str) -> float | None:
        values = [
            move.time_spent
            for move in timed
            if (move.classification or "").strip().lower() == classification
        ]
        return sum(values) / len(values) if values else None

    return GameTimeManagement(
        average_think_time=(
            sum(move.time_spent for move in timed) / len(timed) if timed else None
        ),
        blunder_think_time=average_for("blunder"),
        best_think_time=average_for("best"),
        time_trouble_blunders=sum(
            1
            for move in moves
            if (move.classification or "").strip().lower() == "blunder"
            and is_time_trouble(move)
        ),
    )
