"""Presentation helpers for engine lines."""

from src.backend.storage.models import MoveAnalysis


def lines_for_display(move: MoveAnalysis) -> list[dict]:
    """Return the engine lines that make sense for a selected move.

    MultiPV lines belong to the position *before* the move. When that move
    delivers checkmate the game is over, so the remaining entries are
    alternatives to the mating move, not continuations after it. Keep only
    the line that starts with the played move (falling back to the top line).
    """
    lines = move.multi_pvs or []
    if not move.is_checkmate:
        return lines

    for line in lines:
        pv = line.get("pv_uci") or line.get("pv") or []
        first = pv[0] if pv else None
        if first is not None and not isinstance(first, str):
            first = first.uci()
        if first == move.uci:
            return [line]
    return lines[:1]
