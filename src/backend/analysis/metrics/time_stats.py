# SPDX-License-Identifier: GPL-3.0-only
"""Compact clock-data summaries for AI coach prompts."""

from __future__ import annotations

from src.utils.format_utils import format_clock


def format_time_stats_for_llm(moves) -> str:
    """Build a compact, LLM-friendly summary of the move clocks."""
    if not moves:
        return ""

    def is_white(move) -> bool:
        return move.ply % 2 == 0

    whites = [m for m in moves if is_white(m) and m.time_spent is not None]
    blacks = [m for m in moves if not is_white(m) and m.time_spent is not None]

    def average(items) -> float:
        return sum(m.time_spent for m in items) / len(items) if items else 0.0

    def format_move(move) -> str:
        side = "W" if is_white(move) else "B"
        separator = "." if is_white(move) else "..."
        return (
            f"{move.move_number}{separator} {move.san} "
            f"({side}, {move.time_spent:.1f}s)"
        )

    lines = [
        f"Avg think time — White: {average(whites):.1f}s, "
        f"Black: {average(blacks):.1f}s"
    ]

    by_spent = sorted(
        [m for m in moves if m.time_spent is not None],
        key=lambda move: move.time_spent,
        reverse=True,
    )
    if by_spent:
        lines.append(
            "Longest thinks — " + ", ".join(format_move(m) for m in by_spent[:5])
        )

    quick_swings = []
    for move in moves:
        if move.time_spent is None or move.time_spent > 5.0:
            continue
        before = move.eval_before_cp
        after = move.eval_after_cp
        if before is None or after is None or abs(after - before) < 150:
            continue
        side = "W" if is_white(move) else "B"
        separator = "." if is_white(move) else "..."
        quick_swings.append(
            f"{move.move_number}{separator} {move.san} "
            f"({side}, {move.time_spent:.1f}s, "
            f"swing {(after - before) / 100:+.1f})"
        )
    if quick_swings:
        lines.append(
            "Fastest large eval swings — " + ", ".join(quick_swings[:3])
        )

    def last_time(is_white_side: bool) -> float | None:
        wanted = 0 if is_white_side else 1
        for move in reversed(moves):
            if move.ply % 2 == wanted and move.time_left is not None:
                return move.time_left
        return None

    lines.append(
        "Final clock — "
        f"White: {format_clock(last_time(True), precision=1)}, "
        f"Black: {format_clock(last_time(False), precision=1)}"
    )
    return "\n".join(lines)
