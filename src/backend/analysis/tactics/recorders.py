"""
Record tactical metrics from parsed move contexts.

Each ``record_*`` function owns one concern (accuracy, clock, facts, losses,
opponent mistakes) and mutates the shared :class:`TacticsState`. Keeping them
out of the orchestrator makes both units small and independently testable.

Zero Qt dependencies.
"""

from __future__ import annotations

from typing import Any

import chess

from src.backend.analysis.math_utils import (
    aggregate_accuracy,
    apply_accuracy_floor,
    calculate_move_accuracy,
)
from src.backend.analysis.tactics.attribution import (
    LossRecord,
    is_blunder,
)
from src.backend.analysis.tactics.board_utils import captured_piece, captured_square
from src.backend.analysis.tactics.constants import (
    ADVANTAGE_THRESHOLD_CP,
    BAD_MOVE_CLASSIFICATIONS,
    BLUNDER_CLASSIFICATIONS,
    BRILLIANT_CLASSIFICATIONS,
    PIECE_VALUES,
    SOUND_CLASSIFICATIONS,
    SOUND_TACTIC_MAX_WP_DROP,
    TURNING_POINT_MIN_WP_SWING,
    TacticalTheme,
    TacticRole,
)
from src.backend.analysis.tactics.contexts import MoveCtx
from src.backend.analysis.tactics.facts import TacticFact, fact_to_dict
from src.backend.analysis.tactics.piece_safety import get_lost_pieces
from src.backend.analysis.tactics.state import TacticsState


def move_detail(ctx: MoveCtx, **extra: Any) -> dict[str, Any]:
    """Standard drill-down dictionary for one ply."""
    return {
        "ply": ctx.ply,
        "move_number": ctx.move_number,
        "san": ctx.san,
        "uci": ctx.uci,
        "fen_before": ctx.fen_before,
        "fen_after": ctx.fen_after,
        "classification": ctx.classification,
        "eval_before_cp": ctx.eval_user_cp,
        "eval_after_cp": ctx.eval_after_user,
        "eval_drop": ctx.eval_diff,
        "wp_drop": round(ctx.wp_drop, 3),
        "win_chance_before": round(ctx.player_wp_before, 3),
        "win_chance_after": round(ctx.player_wp_after, 3),
        **extra,
    }


def phase_accuracy(accuracies: list[float], win_percents: list[float]) -> float | None:
    """Volatility-weighted accuracy for one phase, or None when empty."""
    if not accuracies:
        return None
    return aggregate_accuracy(accuracies, win_percents)


def record_accuracy(ctx: MoveCtx, state: TacticsState) -> None:
    state.phase_move_counts[ctx.phase] += 1

    if ctx.is_book or ctx.is_checkmate_move or ctx.is_mating_move:
        accuracy = 100.0
    else:
        accuracy = calculate_move_accuracy(ctx.player_wp_before, ctx.player_wp_after)

    state.phase_accuracies[ctx.phase].append(apply_accuracy_floor(accuracy))
    state.phase_win_percents[ctx.phase].append(ctx.player_wp_before)

    if ctx.classification in BLUNDER_CLASSIFICATIONS:
        state.phase_blunders[ctx.phase] += 1
        state.blunders_details.append(move_detail(ctx))


def record_brilliancies(ctx: MoveCtx, state: TacticsState) -> None:
    if ctx.classification not in BRILLIANT_CLASSIFICATIONS:
        return
    state.brilliancies.append(
        {
            "ply": ctx.ply,
            "move_number": ctx.move_number,
            "san": ctx.san,
            "uci": ctx.uci,
            "fen_before": ctx.fen_before,
            "classification": ctx.classification,
            "explanation": ctx.explanation,
            "opening_name": ctx.opening_name,
            "time_spent": ctx.time_spent,
        }
    )


def record_turning_points(ctx: MoveCtx, state: TacticsState) -> None:
    if ctx.eval_user_cp is not None:
        if state.peak_eval_cp is None or ctx.eval_user_cp > state.peak_eval_cp:
            state.peak_eval_cp = ctx.eval_user_cp
        if state.lowest_eval_cp is None or ctx.eval_user_cp < state.lowest_eval_cp:
            state.lowest_eval_cp = ctx.eval_user_cp

        if ctx.eval_user_cp >= ADVANTAGE_THRESHOLD_CP:
            state.had_winning_advantage = True
        if ctx.eval_user_cp <= -ADVANTAGE_THRESHOLD_CP:
            state.had_losing_position = True

    if (
        state.had_winning_advantage
        and ctx.wp_drop > state.max_lead_drop
        and ctx.wp_drop > TURNING_POINT_MIN_WP_SWING
    ):
        state.max_lead_drop = ctx.wp_drop
        state.lead_collapse_move = move_detail(ctx)

    wp_gain = ctx.player_wp_after - ctx.player_wp_before
    if (
        state.had_losing_position
        and wp_gain > state.max_comeback_gain
        and wp_gain > TURNING_POINT_MIN_WP_SWING
    ):
        state.max_comeback_gain = wp_gain
        state.comeback_turn_move = {
            "ply": ctx.ply,
            "move_number": ctx.move_number,
            "san": ctx.san,
            "uci": ctx.uci,
            "fen_before": ctx.fen_before,
            "fen_after": ctx.fen_after,
            "classification": ctx.classification,
            "eval_before_cp": ctx.eval_user_cp,
            "eval_after_cp": ctx.eval_after_user,
            "eval_gain": -ctx.eval_diff if ctx.eval_diff is not None else None,
            "wp_gain": round(wp_gain, 3),
        }


def record_clock(ctx: MoveCtx, state: TacticsState, trouble_threshold: float) -> None:
    state.clock_stats.record(
        time_spent=ctx.time_spent,
        time_left=ctx.time_left,
        phase=ctx.phase,
        classification=ctx.classification,
        trouble_threshold=trouble_threshold,
    )


def record_facts(
    ctx: MoveCtx,
    state: TacticsState,
    facts: list[TacticFact],
    role: TacticRole,
) -> None:
    """Record confirmed facts only; probable facts stay out of headline stats."""
    for fact in facts:
        if not fact.is_confirmed:
            continue
        roles = state.tactical_roles.get(fact.motif)
        if roles is None:
            continue

        roles[role.value] += 1
        if role is TacticRole.EXECUTED:
            state.tactical_themes[fact.motif] = roles[TacticRole.EXECUTED.value]

        state.tactical_motifs_details.append(
            {
                **move_detail(ctx, motif=fact.motif),
                "role": role.value,
                "confidence": fact.confidence,
                "target_square": fact.target_square,
                "target_piece": fact.target_piece,
                "evidence": fact.evidence,
            }
        )
        state.tactic_facts.append(fact_to_dict(fact))


def record_losses(ctx: MoveCtx, state: TacticsState, losses: list[LossRecord]) -> None:
    for loss in losses:
        key = (ctx.ply, loss.square)
        if key in state.seen_loss_keys:
            continue
        state.seen_loss_keys.add(key)

        if loss.kind == "punished":
            state.punished_lost += 1
        else:
            state.immediate_hung += 1
        state.total_lost += 1

        if loss.piece_name in state.pieces_hung_by_type:
            state.pieces_hung_by_type[loss.piece_name] += 1

        state.hung_pieces_details.append(
            {
                **move_detail(ctx),
                "piece_name": loss.piece_name,
                "square": loss.square,
                "loss_kind": loss.kind,
                "punished_by": loss.punished_by,
                "punished_by_uci": loss.punished_by_uci,
                "line": list(loss.line),
                "see_gain_cp": loss.see_gain_cp,
            }
        )

        if is_blunder(ctx):
            state.hanging_blunders += 1


def record_opp_hanging(
    ctx: MoveCtx,
    state: TacticsState,
    opp_hanging_before: list[dict[str, Any]],
    prev_ctx: MoveCtx | None,
) -> None:
    """Record the user capitalising on, or missing, opponent hanging pieces."""
    if not opp_hanging_before or ctx.move_obj is None:
        return
    if is_previous_capture(ctx, prev_ctx):
        return

    opp_hung = {item["square"]: item for item in opp_hanging_before}
    to_square = chess.square_name(ctx.move_obj.to_square)

    if to_square in opp_hung:
        if (
            ctx.classification not in BAD_MOVE_CLASSIFICATIONS
            and ctx.wp_drop < SOUND_TACTIC_MAX_WP_DROP
        ):
            state.opponent_hanging_captured += 1
            captured = opp_hung[to_square]
            piece_name = captured["piece_name"]
            if piece_name in state.captured_by_piece:
                state.captured_by_piece[piece_name] += 1
            state.opp_captured_details.append(
                {
                    "piece_name": piece_name,
                    "square": to_square,
                    "ply": ctx.ply,
                    "move_number": ctx.move_number,
                    "san": ctx.san,
                    "uci": ctx.uci,
                    "fen_before": ctx.fen_before,
                    "fen_after": ctx.fen_after,
                    "classification": ctx.classification,
                    "eval_before_cp": ctx.eval_user_cp,
                }
            )
    elif ctx.classification in ("Mistake", "Blunder", "Miss"):
        state.opponent_hanging_missed += 1


def is_previous_capture(ctx: MoveCtx, prev_ctx: MoveCtx | None) -> bool:
    """True when the user's move simply recaptures on the same square."""
    if (
        prev_ctx is None
        or prev_ctx.move_obj is None
        or ctx.move_obj is None
        or prev_ctx.move_obj.to_square != ctx.move_obj.to_square
    ):
        return False
    if not prev_ctx.board_before.is_capture(prev_ctx.move_obj):
        return False

    captured = captured_piece(prev_ctx.board_before, prev_ctx.move_obj)
    user_piece = ctx.board_before.piece_at(ctx.move_obj.to_square)
    if captured is None or user_piece is None:
        return False

    return PIECE_VALUES.get(captured.piece_type, 0) >= PIECE_VALUES.get(
        user_piece.piece_type, 0
    )


def record_missed_tactics(ctx: MoveCtx, state: TacticsState) -> None:
    """High-confidence missed tactics: hanging captures and mate in one."""
    if ctx.move_obj is None:
        return
    # A move that is already best/sound or delivers mate did not miss a tactic.
    if ctx.is_checkmate_move or ctx.is_mating_move:
        return
    if ctx.classification in SOUND_CLASSIFICATIONS:
        return
    if (
        ctx.classification not in ("Mistake", "Blunder", "Miss")
        and ctx.wp_drop < SOUND_TACTIC_MAX_WP_DROP
    ):
        return

    enemy_hanging = get_lost_pieces(ctx.board_before, not ctx.board_before.turn)
    captured_sq = (
        chess.square_name(captured_square(ctx.board_before, ctx.move_obj))
        if ctx.board_before.is_capture(ctx.move_obj)
        else None
    )

    missed_capture = next(
        (item for item in enemy_hanging if item["square"] != captured_sq),
        None,
    )
    if missed_capture is not None:
        state.tactical_roles[TacticalTheme.HANGING_PIECE.value][
            TacticRole.MISSED.value
        ] += 1
        state.missed_tactics_details.append(
            {
                **move_detail(ctx),
                "motif": TacticalTheme.HANGING_PIECE.value,
                "role": TacticRole.MISSED.value,
                "missed_square": missed_capture["square"],
                "missed_piece": missed_capture["piece_name"],
                "missed_see_gain": missed_capture.get("enemy_see_gain", 0),
            }
        )

    mate_move = find_mate_in_one(ctx.board_before)
    if mate_move is not None and ctx.move_obj != mate_move:
        state.missed_tactics_details.append(
            {
                **move_detail(ctx),
                "motif": TacticalTheme.BACK_RANK_MATE.value,
                "role": TacticRole.MISSED.value,
                "missed_uci": mate_move.uci(),
                "missed_san": ctx.board_before.san(mate_move),
            }
        )


def find_mate_in_one(board: chess.Board) -> chess.Move | None:
    """Return a legal mate-in-one move, or None. Only probes checking moves."""
    for move in board.legal_moves:
        if not board.gives_check(move):
            continue
        work = board.copy(stack=False)
        work.push(move)
        if work.is_checkmate():
            return move
    return None


__all__ = [
    "find_mate_in_one",
    "is_previous_capture",
    "move_detail",
    "phase_accuracy",
    "record_accuracy",
    "record_brilliancies",
    "record_clock",
    "record_facts",
    "record_losses",
    "record_missed_tactics",
    "record_opp_hanging",
    "record_turning_points",
]
