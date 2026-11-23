# SPDX-License-Identifier: GPL-3.0-only
"""Clock values derived from a move list at a given index."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.backend.storage.models import MoveAnalysis


def compute_clock_times(
    moves: list[MoveAnalysis],
    index: int = -1,
    termination_mode: str | None = None,
) -> tuple[float | None, float | None]:
    """Calculate White and Black clock values at a given move index."""
    has_clocks = any(m.time_left is not None for m in moves) if moves else False
    if not has_clocks:
        return None, None

    white_time = None
    black_time = None

    # Find the latest clock values at or before index.
    if index >= 0:
        for i in range(index, -1, -1):
            if i % 2 == 0 and moves[i].time_left is not None:
                white_time = moves[i].time_left
                break
        for i in range(index, -1, -1):
            if i % 2 == 1 and moves[i].time_left is not None:
                black_time = moves[i].time_left
                break

    # Fall back to starting times if no move has been played yet on that side.
    if white_time is None:
        for idx, m in enumerate(moves):
            if m.time_left is not None and idx % 2 == 0:
                white_time = m.time_left + (
                    m.time_spent if m.time_spent is not None else 0.0
                )
                break
    if black_time is None:
        for idx, m in enumerate(moves):
            if m.time_left is not None and idx % 2 == 1:
                black_time = m.time_left + (
                    m.time_spent if m.time_spent is not None else 0.0
                )
                break

    # PGNs omit the flag-fall clock because the losing side never moved again.
    # On the terminal position, show the side to move at 0:00 instead of their
    # last recorded clock.
    if (
        termination_mode in ("timeout", "timeout_insufficient")
        and moves
        and index == len(moves) - 1
    ):
        side_to_move = (moves[-1].ply + 1) % 2
        if side_to_move == 0:
            white_time = 0.0
        else:
            black_time = 0.0

    return white_time, black_time


__all__ = ["compute_clock_times"]
