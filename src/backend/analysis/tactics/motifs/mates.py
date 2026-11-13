"""
Common checkmate patterns.

All detectors require an actual checkmate; they only describe the pattern of
the final position. Back-rank and smothered mates are the primary patterns;
Morphy, Opera and Boden are conservative named variants.

Zero Qt dependencies.
"""

from __future__ import annotations

import chess

from src.backend.analysis.tactics.constants import PIECE_NAMES, TacticalTheme
from src.backend.analysis.tactics.facts import TacticFact
from src.backend.analysis.tactics.motifs.context import MotifCtx, make_fact


def mate_facts(ctx: MotifCtx) -> list[TacticFact]:
    """All mate-pattern facts that apply to the played move."""
    facts: list[TacticFact] = []
    for factory in (
        back_rank_mate_fact,
        smothered_mate_fact,
        morphy_mate_fact,
        opera_mate_fact,
        boden_mate_fact,
    ):
        fact = factory(ctx)
        if fact is not None:
            facts.append(fact)
    return facts


def back_rank_mate_fact(ctx: MotifCtx) -> TacticFact | None:
    """Checkmate on the enemy back rank with the king trapped by its own pieces."""
    if not ctx.after.is_checkmate() or ctx.enemy_king_sq is None:
        return None

    back_rank = 0 if ctx.enemy_color == chess.WHITE else 7
    if chess.square_rank(ctx.enemy_king_sq) != back_rank:
        return None

    # A back-rank mate is delivered by a rook or queen along the back rank.
    checkers = ctx.after.checkers()
    if len(checkers) != 1:
        return None
    checker_sq = next(iter(checkers))
    checker = ctx.after.piece_at(checker_sq)
    if checker is None or checker.piece_type not in (chess.ROOK, chess.QUEEN):
        return None
    if chess.square_rank(checker_sq) != back_rank:
        return None

    escape_rank = 1 if back_rank == 0 else 6
    king_file = chess.square_file(ctx.enemy_king_sq)
    for file in range(max(0, king_file - 1), min(8, king_file + 2)):
        square = chess.square(file, escape_rank)
        piece = ctx.after.piece_at(square)
        if piece is not None and piece.color == ctx.enemy_color:
            continue
        if square not in ctx.after.attacks(ctx.color):
            return None

    return _mate_fact(ctx, TacticalTheme.BACK_RANK_MATE, "king trapped on the back rank")


def smothered_mate_fact(ctx: MotifCtx) -> TacticFact | None:
    """Checkmate by a knight where the king is surrounded by its own pieces."""
    if not ctx.after.is_checkmate() or ctx.enemy_king_sq is None:
        return None

    checkers = ctx.after.checkers()
    if len(checkers) != 1:
        return None
    checker_sq = next(iter(checkers))
    checker = ctx.after.piece_at(checker_sq)
    if checker is None or checker.piece_type != chess.KNIGHT:
        return None

    for square in ctx.after.attacks(ctx.enemy_king_sq):
        piece = ctx.after.piece_at(square)
        if piece is None or piece.color != ctx.enemy_color:
            return None

    return _mate_fact(ctx, TacticalTheme.SMOTHERED_MATE, "knight mates a smothered king")


def morphy_mate_fact(ctx: MotifCtx) -> TacticFact | None:
    """Bishop delivers mate while a rook confines the king."""
    if not single_checker(ctx, chess.BISHOP):
        return None
    if not ctx.after.pieces(chess.ROOK, ctx.color):
        return None
    return _mate_fact(ctx, TacticalTheme.MORPHY_MATE, "bishop mates with rook support")


def opera_mate_fact(ctx: MotifCtx) -> TacticFact | None:
    """Rook delivers mate while a bishop defends the rook."""
    if not single_checker(ctx, chess.ROOK):
        return None
    checker_sq = next(iter(ctx.after.checkers()))
    if not any(
        (piece := ctx.after.piece_at(sq)) is not None
        and piece.piece_type == chess.BISHOP
        for sq in ctx.after.attackers(ctx.color, checker_sq)
    ):
        return None
    return _mate_fact(ctx, TacticalTheme.OPERA_MATE, "rook mates while a bishop defends it")


def boden_mate_fact(ctx: MotifCtx) -> TacticFact | None:
    """Two bishops on criss-crossing diagonals mate the king."""
    if not single_checker(ctx, chess.BISHOP):
        return None
    if len(ctx.after.pieces(chess.BISHOP, ctx.color)) < 2:
        return None
    return _mate_fact(ctx, TacticalTheme.BODEN_MATE, "two bishops cover the mating net")


def single_checker(ctx: MotifCtx, piece_type: chess.PieceType) -> bool:
    """True when the position is mate with exactly one checker of ``piece_type``."""
    if not ctx.after.is_checkmate():
        return False
    checkers = ctx.after.checkers()
    if len(checkers) != 1:
        return False
    checker = ctx.after.piece_at(next(iter(checkers)))
    return checker is not None and checker.piece_type == piece_type


def _mate_fact(ctx: MotifCtx, motif: TacticalTheme, evidence: str) -> TacticFact:
    return make_fact(
        ctx,
        motif,
        target_square=ctx.move.to_square,
        target_piece=PIECE_NAMES.get(ctx.piece.piece_type),
        evidence=evidence,
    )


__all__ = [
    "back_rank_mate_fact",
    "boden_mate_fact",
    "mate_facts",
    "morphy_mate_fact",
    "opera_mate_fact",
    "single_checker",
    "smothered_mate_fact",
]
