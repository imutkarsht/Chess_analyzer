"""
Shared context, geometry and fact construction for motif detection.

Zero Qt dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass

import chess

from src.backend.analysis.tactics.board_utils import (
    find_slider_ray_targets,
    is_on_segment,
)
from src.backend.analysis.tactics.constants import (
    Confidence,
    TacticalTheme,
    TacticRole,
)
from src.backend.analysis.tactics.facts import TacticFact


@dataclass(frozen=True)
class MotifCtx:
    """Immutable context for evaluating one played move."""

    before: chess.Board
    after: chess.Board
    move: chess.Move
    color: chess.Color
    piece: chess.Piece
    enemy_color: chess.Color
    enemy_king_sq: chess.Square | None
    sliders: chess.SquareSet
    classification: str | None = None

    @property
    def side(self) -> str:
        return "white" if self.color == chess.WHITE else "black"

    @property
    def move_san(self) -> str | None:
        try:
            return self.before.san(self.move)
        except Exception:  # noqa: BLE001
            return None


def sliders(board: chess.Board, color: chess.Color) -> chess.SquareSet:
    """Bishops, rooks and queens of ``color``."""
    return (
        board.pieces(chess.BISHOP, color)
        | board.pieces(chess.ROOK, color)
        | board.pieces(chess.QUEEN, color)
    )


def stays_on_line(
    square: chess.Square,
    slider_sq: chess.Square,
    rear_sq: chess.Square,
) -> bool:
    """True when ``square`` keeps blocking the slider-to-rear line."""
    return square in (slider_sq, rear_sq) or is_on_segment(slider_sq, rear_sq, square)


def affected_alignments(
    ctx: MotifCtx,
) -> list[tuple[chess.Square, chess.Square, chess.Square]]:
    """
    Newly formed (slider, front, rear) alignments.

    A slider that moved is compared with the ray from its previous square, so a
    slider that simply keeps the same pin is not reported again.
    """
    alignments: list[tuple[chess.Square, chess.Square, chess.Square]] = []

    for slider_sq in sliders(ctx.after, ctx.color):
        after_pairs = find_slider_ray_targets(ctx.after, slider_sq, ctx.color)
        previous_sq = ctx.move.from_square if slider_sq == ctx.move.to_square else slider_sq
        before_pairs = find_slider_ray_targets(ctx.before, previous_sq, ctx.color)
        before_set = {(front_sq, rear_sq) for front_sq, _, rear_sq, _ in before_pairs}

        for front_sq, _front_p, rear_sq, _rear_p in after_pairs:
            if (front_sq, rear_sq) not in before_set:
                alignments.append((slider_sq, front_sq, rear_sq))

    return alignments


def make_fact(
    ctx: MotifCtx,
    motif: TacticalTheme,
    *,
    target_square: chess.Square | None = None,
    target_piece: str | None = None,
    targets: tuple[str, ...] = (),
    evidence: str = "",
    material_gain_cp: int = 0,
    mate_in: int | None = None,
    include_origin: bool = True,
) -> TacticFact:
    """Build a probable executed fact with the shared move metadata filled in."""
    return TacticFact(
        motif=motif.value,
        role=TacticRole.EXECUTED.value,
        side=ctx.side,
        confidence=Confidence.PROBABLE.value,
        move_san=ctx.move_san,
        move_uci=ctx.move.uci(),
        origin_square=(
            chess.square_name(ctx.move.from_square) if include_origin else None
        ),
        target_square=(
            chess.square_name(target_square) if target_square is not None else None
        ),
        target_piece=target_piece,
        targets=targets,
        evidence=evidence,
        material_gain_cp=material_gain_cp,
        mate_in=mate_in,
    )


__all__ = [
    "MotifCtx",
    "affected_alignments",
    "make_fact",
    "sliders",
    "stays_on_line",
]
