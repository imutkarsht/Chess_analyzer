"""
Game-level tactical analysis orchestrator.

One pass over parsed move contexts produces:
- phase accuracies and blunder distribution;
- validated executed / allowed / missed tactic facts;
- hanging-piece losses with immediate vs punished attribution;
- advantage conversion, brilliancies, clock metrics and drill-down records.

The heavy lifting lives in ``recorders.py`` and ``state.py``; this module only
coordinates them.

Zero Qt dependencies.
"""

from __future__ import annotations

from typing import Any

import chess

from src.backend.analysis.tactics.attribution import is_sound_move, resolve_losses
from src.backend.analysis.tactics.constants import (
    BAD_MOVE_CLASSIFICATIONS,
    DEFAULT_TROUBLE_SECONDS,
    PHASES,
    TACTICS_VERSION,
    TROUBLE_SECONDS,
    TacticRole,
)
from src.backend.analysis.tactics.contexts import MoveCtx, build_contexts
from src.backend.analysis.tactics.motifs import detect_candidates
from src.backend.analysis.tactics.piece_safety import get_lost_pieces
from src.backend.analysis.tactics.recorders import (
    phase_accuracy,
    record_accuracy,
    record_brilliancies,
    record_clock,
    record_facts,
    record_losses,
    record_missed_tactics,
    record_opp_hanging,
    record_turning_points,
)
from src.backend.analysis.tactics.state import ClockStats, TacticsState
from src.backend.analysis.tactics.validation import confirm_facts

# Re-exported for callers that imported these from this module historically.
__all__ = ["ClockStats", "MoveCtx", "TacticsState", "analyze_game_tactics"]


def analyze_game_tactics(
    moves_data: list[dict[str, Any]],
    user_color: str,
    result: str = "*",
    speed_category: str = "Blitz",
) -> dict[str, Any]:
    """
    Comprehensive tactical, phase and advantage analysis for one game.

    Headline tactic counts use confirmed facts only. Every historical key is
    preserved; new fields are additive.
    """
    is_user_white = user_color.lower() == "white"
    target_color = chess.WHITE if is_user_white else chess.BLACK
    enemy_color = not target_color

    trouble_threshold = _trouble_threshold(speed_category)
    contexts = build_contexts(moves_data, is_user_white)
    state = TacticsState()

    for index, ctx in enumerate(contexts):
        if ctx is None:
            continue

        if not ctx.is_book and state.book_exit_ply is None:
            state.book_exit_ply = ctx.ply

        if not ctx.is_user_move:
            continue

        _record_standard_metrics(ctx, state, trouble_threshold)

        if ctx.move_obj is None or ctx.board_after is None:
            continue

        next_ctx = contexts[index + 1] if index + 1 < len(contexts) else None
        prev_ctx = contexts[index - 1] if index > 0 else None

        _record_losses(ctx, next_ctx, state, target_color)
        _record_executed_facts(ctx, next_ctx, state)
        _record_allowed_facts(ctx, next_ctx, state)
        record_missed_tactics(ctx, state)
        record_opp_hanging(
            ctx,
            state,
            get_lost_pieces(ctx.board_before, enemy_color),
            prev_ctx,
        )

    _finalize_advantage(state, result, is_user_white)
    return _summary(state)


def _trouble_threshold(speed_category: str) -> float:
    category = (speed_category or "blitz").lower()
    for key, seconds in TROUBLE_SECONDS.items():
        if key in category:
            return seconds
    return DEFAULT_TROUBLE_SECONDS


def _record_standard_metrics(
    ctx: MoveCtx,
    state: TacticsState,
    trouble_threshold: float,
) -> None:
    record_accuracy(ctx, state)
    record_turning_points(ctx, state)
    record_brilliancies(ctx, state)
    record_clock(ctx, state, trouble_threshold)


def _record_losses(
    ctx: MoveCtx,
    next_ctx: MoveCtx | None,
    state: TacticsState,
    target_color: chess.Color,
) -> None:
    record_losses(ctx, state, resolve_losses(ctx, next_ctx, target_color))


def _record_executed_facts(
    ctx: MoveCtx,
    next_ctx: MoveCtx | None,
    state: TacticsState,
) -> None:
    board_after = ctx.board_after
    move_obj = ctx.move_obj
    if board_after is None or move_obj is None:
        return

    facts = confirm_facts(
        detect_candidates(
            ctx.board_before,
            board_after,
            move_obj,
            ctx.board_before.turn,
            ctx.classification,
        ),
        board_after,
        reply_move=next_ctx.move_obj if next_ctx is not None else None,
        engine_pv=list(next_ctx.engine_pv) if next_ctx is not None else None,
        classification=ctx.classification,
        board_before=ctx.board_before,
    )
    record_facts(ctx, state, facts, TacticRole.EXECUTED)


def _record_allowed_facts(
    ctx: MoveCtx,
    next_ctx: MoveCtx | None,
    state: TacticsState,
) -> None:
    if (
        next_ctx is None
        or next_ctx.move_obj is None
        or next_ctx.board_after is None
        or (is_sound_move(ctx) and ctx.classification not in BAD_MOVE_CLASSIFICATIONS)
    ):
        return

    facts = confirm_facts(
        detect_candidates(
            next_ctx.board_before,
            next_ctx.board_after,
            next_ctx.move_obj,
            next_ctx.board_before.turn,
            next_ctx.classification,
        ),
        next_ctx.board_after,
        engine_pv=list(next_ctx.engine_pv),
        classification=next_ctx.classification,
        board_before=next_ctx.board_before,
    )
    record_facts(next_ctx, state, facts, TacticRole.ALLOWED)


def _finalize_advantage(
    state: TacticsState,
    result: str,
    is_user_white: bool,
) -> None:
    is_user_win = (result == "1-0" and is_user_white) or (
        result == "0-1" and not is_user_white
    )
    is_draw = result in ("1/2-1/2", "Draw")
    user_lost = not is_user_win and not is_draw

    if state.had_winning_advantage:
        state.converted_advantage = is_user_win
        state.choked_advantage = not is_user_win
        if not is_user_win and not is_draw:
            state.thrown_losses = True
        elif is_draw:
            state.squandered_draws = True

    if state.had_losing_position:
        state.comeback_drawn_or_won = is_user_win or is_draw
        if is_user_win:
            state.comeback_wins = True
        elif is_draw:
            state.comeback_draws = True
        state.lost_deficit = user_lost


def _summary(state: TacticsState) -> dict[str, Any]:
    phase_accuracies = {
        phase: phase_accuracy(
            state.phase_accuracies[phase], state.phase_win_percents[phase]
        )
        for phase in PHASES
    }

    return {
        "tactics_version": TACTICS_VERSION,
        "phase_accuracies": phase_accuracies,
        "phase_blunders": state.phase_blunders,
        "phase_move_counts": state.phase_move_counts,
        "hanging_metrics": {
            "total_hung": state.total_lost,
            "total_lost": state.total_lost,
            "immediate_hung": state.immediate_hung,
            "punished_lost": state.punished_lost,
            "deduplicated_total": state.total_lost,
            "by_piece": state.pieces_hung_by_type,
            "captured_by_piece": state.captured_by_piece,
            "hanging_blunders": state.hanging_blunders,
            "opponent_hanging_captured": state.opponent_hanging_captured,
            "opponent_hanging_missed": state.opponent_hanging_missed,
        },
        "advantage_metrics": {
            "had_winning_advantage": state.had_winning_advantage,
            "converted_advantage": state.converted_advantage,
            "choked_advantage": state.choked_advantage,
            "thrown_losses": state.thrown_losses,
            "squandered_draws": state.squandered_draws,
            "had_losing_position": state.had_losing_position,
            "comeback_drawn_or_won": state.comeback_drawn_or_won,
            "comeback_wins": state.comeback_wins,
            "comeback_draws": state.comeback_draws,
            "lost_deficit": state.lost_deficit,
            "peak_eval_cp": state.peak_eval_cp if state.peak_eval_cp is not None else 0,
            "lowest_eval_cp": (
                state.lowest_eval_cp if state.lowest_eval_cp is not None else 0
            ),
        },
        "brilliancies": state.brilliancies,
        "tactical_themes": dict(state.tactical_themes),
        "tactical_roles": state.tactical_roles,
        "tactic_facts": state.tactic_facts,
        "hung_pieces_details": state.hung_pieces_details,
        "opp_captured_details": state.opp_captured_details,
        "tactical_motifs_details": state.tactical_motifs_details,
        "missed_tactics_details": state.missed_tactics_details,
        "blunders_details": state.blunders_details,
        "lead_collapse_move": state.lead_collapse_move,
        "comeback_turn_move": state.comeback_turn_move,
        "book_exit_ply": state.book_exit_ply,
        "clock_metrics": state.clock_stats.to_dict(),
    }
