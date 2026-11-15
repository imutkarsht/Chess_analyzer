"""
Mutable accumulators for one game's tactical analysis.

Keeping the state separate from the recorders makes the data model easy to
inspect and keeps ``game.py`` focused on orchestration.

Zero Qt dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.backend.analysis.tactics.constants import (
    MAX_REASONABLE_TIME_SECONDS,
    PHASES,
    PIECE_NAMES_ORDERED,
    MoveQualityBucket,
    TacticalTheme,
    TacticRole,
)


@dataclass
class ClockStats:
    """Aggregates clock timing, time-trouble, and quality stats."""

    total_timed_moves: int = 0
    total_time_spent: float = 0.0
    normal_moves: int = 0
    normal_blunders: int = 0
    trouble_moves: int = 0
    trouble_blunders: int = 0
    phase_time_spent: dict[str, float] = field(
        default_factory=lambda: dict.fromkeys(PHASES, 0.0)
    )
    phase_timed_moves: dict[str, int] = field(
        default_factory=lambda: dict.fromkeys(PHASES, 0)
    )
    quality_time_spent: dict[str, float] = field(
        default_factory=lambda: {
            MoveQualityBucket.BEST.value: 0.0,
            MoveQualityBucket.BLUNDER.value: 0.0,
            MoveQualityBucket.OTHER.value: 0.0,
        }
    )
    quality_timed_moves: dict[str, int] = field(
        default_factory=lambda: {
            MoveQualityBucket.BEST.value: 0,
            MoveQualityBucket.BLUNDER.value: 0,
            MoveQualityBucket.OTHER.value: 0,
        }
    )

    def record(
        self,
        time_spent: float | None,
        time_left: float | None,
        phase: str,
        classification: str,
        trouble_threshold: float,
    ) -> None:
        if time_spent is not None and 0.0 <= time_spent < MAX_REASONABLE_TIME_SECONDS:
            self.total_timed_moves += 1
            self.total_time_spent += time_spent
            if phase in self.phase_time_spent:
                self.phase_time_spent[phase] += time_spent
                self.phase_timed_moves[phase] += 1

            if classification in ("Brilliant", "Great", "Best"):
                quality_bucket = MoveQualityBucket.BEST.value
            elif classification in ("Blunder", "Mistake"):
                quality_bucket = MoveQualityBucket.BLUNDER.value
            else:
                quality_bucket = MoveQualityBucket.OTHER.value
            self.quality_time_spent[quality_bucket] += time_spent
            self.quality_timed_moves[quality_bucket] += 1

        if time_left is not None and time_left >= 0.0:
            is_blunder_or_mistake = classification in ("Blunder", "Mistake")
            if time_left <= trouble_threshold:
                self.trouble_moves += 1
                if is_blunder_or_mistake:
                    self.trouble_blunders += 1
            else:
                self.normal_moves += 1
                if is_blunder_or_mistake:
                    self.normal_blunders += 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_timed_moves": self.total_timed_moves,
            "total_time_spent": round(self.total_time_spent, 1),
            "phase_time_spent": {
                key: round(value, 1) for key, value in self.phase_time_spent.items()
            },
            "phase_timed_moves": dict(self.phase_timed_moves),
            "quality_time_spent": {
                key: round(value, 1) for key, value in self.quality_time_spent.items()
            },
            "quality_timed_moves": dict(self.quality_timed_moves),
            "normal_moves": self.normal_moves,
            "normal_blunders": self.normal_blunders,
            "trouble_moves": self.trouble_moves,
            "trouble_blunders": self.trouble_blunders,
        }


@dataclass
class TacticsState:
    """Accumulates tactical tracking state across a full game analysis."""

    phase_accuracies: dict[str, list[float]] = field(
        default_factory=lambda: {phase: [] for phase in PHASES}
    )
    phase_win_percents: dict[str, list[float]] = field(
        default_factory=lambda: {phase: [] for phase in PHASES}
    )
    phase_blunders: dict[str, int] = field(
        default_factory=lambda: dict.fromkeys(PHASES, 0)
    )
    phase_move_counts: dict[str, int] = field(
        default_factory=lambda: dict.fromkeys(PHASES, 0)
    )
    pieces_hung_by_type: dict[str, int] = field(
        default_factory=lambda: dict.fromkeys(PIECE_NAMES_ORDERED, 0)
    )
    captured_by_piece: dict[str, int] = field(
        default_factory=lambda: dict.fromkeys(PIECE_NAMES_ORDERED, 0)
    )
    tactical_themes: dict[str, int] = field(
        default_factory=lambda: {theme.value: 0 for theme in TacticalTheme}
    )
    tactical_roles: dict[str, dict[str, int]] = field(
        default_factory=lambda: {
            theme.value: {
                TacticRole.EXECUTED.value: 0,
                TacticRole.ALLOWED.value: 0,
                TacticRole.MISSED.value: 0,
            }
            for theme in TacticalTheme
        }
    )

    brilliancies: list[dict[str, Any]] = field(default_factory=list)
    hung_pieces_details: list[dict[str, Any]] = field(default_factory=list)
    opp_captured_details: list[dict[str, Any]] = field(default_factory=list)
    tactical_motifs_details: list[dict[str, Any]] = field(default_factory=list)
    blunders_details: list[dict[str, Any]] = field(default_factory=list)
    missed_tactics_details: list[dict[str, Any]] = field(default_factory=list)
    tactic_facts: list[dict[str, Any]] = field(default_factory=list)

    had_winning_advantage: bool = False
    converted_advantage: bool = False
    choked_advantage: bool = False
    thrown_losses: bool = False
    squandered_draws: bool = False
    had_losing_position: bool = False
    comeback_drawn_or_won: bool = False
    comeback_wins: bool = False
    comeback_draws: bool = False
    lost_deficit: bool = False

    max_lead_drop: float = 0.0
    max_comeback_gain: float = 0.0
    lead_collapse_move: dict[str, Any] | None = None
    comeback_turn_move: dict[str, Any] | None = None

    peak_eval_cp: int | None = None
    lowest_eval_cp: int | None = None
    book_exit_ply: int | None = None

    immediate_hung: int = 0
    punished_lost: int = 0
    total_lost: int = 0
    hanging_blunders: int = 0
    opponent_hanging_captured: int = 0
    opponent_hanging_missed: int = 0
    seen_loss_keys: set[tuple[int, str]] = field(default_factory=set)

    clock_stats: ClockStats = field(default_factory=ClockStats)


__all__ = ["ClockStats", "TacticsState"]
