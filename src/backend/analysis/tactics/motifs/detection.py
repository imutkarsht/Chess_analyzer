"""
Public motif-detection entry points.

Collects candidates from the focused detector modules, merges multiple
alignments of one motif on the same move, and exposes the backward-compatible
motif-name façade.

Zero Qt dependencies.
"""

from __future__ import annotations

import chess

from src.backend.analysis.tactics.constants import TacticalTheme
from src.backend.analysis.tactics.facts import TacticFact, merge_same_motif_facts
from src.backend.analysis.tactics.motifs.alignments import alignment_facts
from src.backend.analysis.tactics.motifs.attacks import discovered_facts, fork_fact
from src.backend.analysis.tactics.motifs.context import MotifCtx, sliders
from src.backend.analysis.tactics.motifs.losses import (
    hanging_facts,
    removal_of_defender_fact,
    trapped_piece_fact,
)
from src.backend.analysis.tactics.motifs.mates import mate_facts
from src.backend.analysis.tactics.motifs.special import promotion_fact, sacrifice_fact


def detect_candidates(
    board_before: chess.Board,
    board_after: chess.Board,
    move: chess.Move,
    color: chess.Color,
    classification: str | None = None,
) -> list[TacticFact]:
    """
    Detect probable tactical facts for a move.

    Returned facts are unconfirmed; call :func:`validation.confirm_facts` to
    promote them to headline confidence.
    """
    piece = board_after.piece_at(move.to_square)
    if piece is None:
        return []

    ctx = MotifCtx(
        before=board_before,
        after=board_after,
        move=move,
        color=color,
        piece=piece,
        enemy_color=not color,
        enemy_king_sq=board_after.king(not color),
        sliders=sliders(board_after, color),
        classification=classification,
    )

    facts: list[TacticFact] = []
    facts.extend(hanging_facts(ctx))

    fork = fork_fact(ctx)
    if fork is not None:
        facts.append(fork)

    facts.extend(alignment_facts(ctx, TacticalTheme.PIN))
    facts.extend(alignment_facts(ctx, TacticalTheme.SKEWER))
    facts.extend(discovered_facts(ctx))

    for factory in (
        removal_of_defender_fact,
        trapped_piece_fact,
        sacrifice_fact,
        promotion_fact,
    ):
        fact = factory(ctx)
        if fact is not None:
            facts.append(fact)

    facts.extend(mate_facts(ctx))
    return merge_same_motif_facts(facts)


def detect_tactical_motifs(
    board_before: chess.Board,
    board_after: chess.Board,
    move: chess.Move,
    color: chess.Color,
    classification: str | None = None,
) -> list[str]:
    """Backwards-compatible façade returning motif names only."""
    return [
        fact.motif
        for fact in detect_candidates(
            board_before, board_after, move, color, classification
        )
    ]


__all__ = ["detect_candidates", "detect_tactical_motifs"]
