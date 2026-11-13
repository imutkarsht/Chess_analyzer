"""
Engine/game corroboration for candidate tactic facts.

Detection answers "is this tactically true by the rules?". Validation answers
"did the game or the engine actually demonstrate it?". Facts that survive are
confirmed; the rest stay probable and are excluded from headline statistics.

Zero Qt dependencies.
"""

from __future__ import annotations

import chess

from src.backend.analysis.tactics.board_utils import captured_square
from src.backend.analysis.tactics.constants import (
    SOUND_CLASSIFICATIONS,
    Confidence,
    TacticalTheme,
)
from src.backend.analysis.tactics.facts import TacticFact
from src.backend.analysis.tactics.piece_safety import is_piece_doomed, is_piece_lost

_MATE_MOTIFS = {
    TacticalTheme.BACK_RANK_MATE.value,
    TacticalTheme.SMOTHERED_MATE.value,
    TacticalTheme.MORPHY_MATE.value,
    TacticalTheme.OPERA_MATE.value,
    TacticalTheme.BODEN_MATE.value,
}

_OBJECTIVE_LOSS_MOTIFS = {
    TacticalTheme.HANGING_PIECE.value,
    TacticalTheme.TRAPPED_PIECE.value,
}

_OBJECTIVE_CHECK_MOTIFS = {
    TacticalTheme.DISCOVERED_CHECK.value,
    TacticalTheme.DOUBLE_CHECK.value,
}


def confirm_facts(
    facts: list[TacticFact],
    board_after: chess.Board,
    reply_move: chess.Move | None = None,
    engine_pv: list[str] | None = None,
    classification: str | None = None,
    board_before: chess.Board | None = None,
) -> list[TacticFact]:
    """
    Return ``facts`` with confidence upgraded where evidence allows.

    Objective facts (mate, check, doomed target, promotion, validated sacrifice)
    are confirmed directly. Other facts are confirmed only when the actual reply
    or engine PV captures the target or mates.
    """
    demonstrated = _demonstrated_capture_squares(board_after, reply_move, engine_pv)
    mate_demonstrated = _pv_ends_in_mate(board_after, engine_pv)

    validated: list[TacticFact] = []
    for fact in facts:
        if _is_objective(fact, board_after, classification, board_before):
            validated.append(
                fact.with_confidence(Confidence.CONFIRMED.value, fact.evidence)
            )
            continue

        if fact.motif in _MATE_MOTIFS and mate_demonstrated:
            validated.append(
                fact.with_confidence(
                    Confidence.CONFIRMED.value, "continuation ends in mate"
                )
            )
            continue

        if _fact_targets(fact) & demonstrated:
            validated.append(
                fact.with_confidence(
                    Confidence.CONFIRMED.value, "target captured in the continuation"
                )
            )
            continue

        validated.append(fact)

    return validated


def _fact_targets(fact: TacticFact) -> set[str]:
    """All target squares a fact can be demonstrated by."""
    targets = set(fact.targets)
    if fact.target_square is not None:
        targets.add(fact.target_square)
    return targets


def _target_square(fact: TacticFact) -> chess.Square | None:
    """Parsed primary target square, or None when absent/invalid."""
    if fact.target_square is None:
        return None
    try:
        return chess.parse_square(fact.target_square)
    except ValueError:
        return None


def _is_objective(
    fact: TacticFact,
    board_after: chess.Board,
    classification: str | None,
    board_before: chess.Board | None,
) -> bool:
    """True when the motif is proven by the rules alone."""
    if fact.motif in _MATE_MOTIFS:
        return board_after.is_checkmate()

    if fact.motif in _OBJECTIVE_CHECK_MOTIFS:
        return board_after.is_check()

    if fact.motif in _OBJECTIVE_LOSS_MOTIFS:
        square = _target_square(fact)
        if square is None:
            return False

        target = board_after.piece_at(square)
        if target is not None:
            return is_piece_doomed(board_after, square, target.color)

        # The move itself may have captured the hanging piece.
        if board_before is not None:
            captured = board_before.piece_at(square)
            if captured is not None:
                return is_piece_lost(board_before, square, captured.color)
        return False

    if fact.motif == TacticalTheme.FORK.value:
        return _fork_target_is_lost(fact, board_after)

    if fact.motif in {TacticalTheme.PIN.value, TacticalTheme.SKEWER.value}:
        # A pin or skewer is only actionable when the continuation actually
        # wins the target or mates. Otherwise it stays probable and is kept out
        # of headline statistics.
        return False

    if fact.motif == TacticalTheme.PROMOTION.value:
        return True

    if fact.motif == TacticalTheme.SACRIFICE.value:
        return classification in SOUND_CLASSIFICATIONS

    return False


def _fork_target_is_lost(fact: TacticFact, board_after: chess.Board) -> bool:
    square = _target_square(fact)
    if square is None:
        return False

    target = board_after.piece_at(square)
    if target is None:
        return False
    if target.piece_type == chess.KING:
        return board_after.is_check()
    return is_piece_doomed(board_after, square, target.color)


def _demonstrated_capture_squares(
    board_after: chess.Board,
    reply_move: chess.Move | None,
    engine_pv: list[str] | None,
) -> set[str]:
    """Destinations of captures in the reply or PV."""
    squares: set[str] = set()

    if reply_move is not None and board_after.is_capture(reply_move):
        squares.add(chess.square_name(captured_square(board_after, reply_move)))

    if not engine_pv:
        return squares

    work = board_after.copy(stack=False)
    for uci in engine_pv:
        try:
            move = chess.Move.from_uci(uci)
        except ValueError:
            break
        if move not in work.legal_moves:
            break
        if work.is_capture(move):
            squares.add(chess.square_name(captured_square(work, move)))
        work.push(move)

    return squares


def _pv_ends_in_mate(board_after: chess.Board, engine_pv: list[str] | None) -> bool:
    if not engine_pv:
        return False

    work = board_after.copy(stack=False)
    for uci in engine_pv:
        try:
            move = chess.Move.from_uci(uci)
        except ValueError:
            return False
        if move not in work.legal_moves:
            return False
        work.push(move)

    return work.is_checkmate()


__all__ = ["confirm_facts"]
