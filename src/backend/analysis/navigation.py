"""
Move-list navigation helpers shared by the keyboard shortcuts.
"""

from collections.abc import Iterable, Sequence

from src.backend.storage.models import MoveAnalysis
from src.constants import CRITICAL_CLASSIFICATIONS


def find_critical_move(
    moves: Sequence[MoveAnalysis],
    current_index: int,
    step: int,
    classifications: Iterable[str] = CRITICAL_CLASSIFICATIONS,
) -> int | None:
    """Return the index of the nearest critical move strictly after (step=1) or
    before (step=-1) ``current_index``, or None if there is none.

    ``current_index`` may be -1 (the starting position, before the first move).
    Matching is case-insensitive because the analyser stores title-case labels.
    """
    if step not in (1, -1):
        raise ValueError(f"step must be 1 or -1, got {step}")

    wanted = {c.lower() for c in classifications}
    index = current_index + step
    while 0 <= index < len(moves):
        if (moves[index].classification or "").lower() in wanted:
            return index
        index += step
    return None
