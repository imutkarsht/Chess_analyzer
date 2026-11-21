# SPDX-License-Identifier: GPL-3.0-only
"""Project canonical termination modes into dashboard buckets.

Board-aware detection lives in ``src.backend.domain.termination``. This module
only maps its stored mode token to the Stats dashboard's display buckets.
"""

from __future__ import annotations

from typing import Any

from src.backend.analysis.metrics.constants import DRAW_MODE_TO_BUCKET

_NON_DRAW_BUCKETS = {
    "checkmate": "Checkmate",
    "timeout": "Time",
    "timeout_insufficient": "Time",
    "abandonment": "Abandon",
    "resignation": "Resignation",
    "rules_violation": "Resignation",
    "unterminated": "Resignation",
}


def classify_termination(
    game: dict[str, Any],
    is_draw: bool,
) -> tuple[str, str | None]:
    """Map a canonical ``termination_mode`` to a dashboard bucket.

    Returns ``(term_type, draw_type)`` where ``term_type`` is one of
    Checkmate, Resignation, Time, Abandon, Draw.
    """
    term_mode = (game.get("termination_mode") or "").strip().lower()

    if is_draw:
        return "Draw", DRAW_MODE_TO_BUCKET.get(term_mode, "Agreement")

    return _NON_DRAW_BUCKETS.get(term_mode, "Resignation"), None


__all__ = ["classify_termination"]
