"""
Game-level tactical analysis.

One pass over parsed move contexts produces:
- phase accuracies and blunder distribution;
- validated executed / allowed / missed tactic facts;
- hanging-piece losses with immediate vs punished attribution;
- advantage conversion, brilliancies, clock metrics and drill-down records.

Zero Qt dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
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
    is_sound_move,
    resolve_losses,
)
from src.backend.analysis.tactics.constants import (
    ADVANTAGE_THRESHOLD_CP,
    BAD_MOVE_CLASSIFICATIONS,
    BLUNDER_CLASSIFICATIONS,
    BRILLIANT_CLASSIFICATIONS,
    DEFAULT_TROUBLE_SECONDS,
    MAX_REASONABLE_TIME_SECONDS,
    PHASES,
    PIECE_NAMES_ORDERED,
    PIECE_VALUES,
    SOUND_TACTIC_MAX_WP_DROP,
    TACTICS_VERSION,
    TROUBLE_SECONDS,
    TURNING_POINT_MIN_WP_SWING,
    MoveQualityBucket,
    TacticalTheme,
    TacticRole,
)
from src.backend.analysis.tactics.contexts import MoveCtx, build_contexts
from src.backend.analysis.tactics.facts import TacticFact, fact_to_dict
from src.backend.analysis.tactics.motifs import detect_candidates
from src.backend.analysis.tactics.piece_safety import get_lost_pieces
from src.backend.analysis.tactics.validation import confirm_facts

# Re-exported for callers that imported MoveCtx from this module historically.
__all__ = ["ClockStats", "MoveCtx", "TacticsState", "analyze_game_tactics"]


@dataclass
class ClockStats:
    """Aggregates clock timing, time-trouble, and quality stats."""

    total_timed_moves: int = 0
    total_time_spent: float = 0.0
    normal_moves: int = 0
    normal_blunders: int = 0
    trouble_moves: int = 0
    trouble_blunders: int = 0
    phase_time_spent: dict[str, float] = field(default_factory=lambda: dict.fromkeys(PHASES, 0.0))
    phase_timed_moves: dict[str, int] = field(default_factory=lambda: dict.fromkeys(PHASES, 0))
    quality_time_spent: dict[str, float] = field(
        default_factory=lambda: {
            MoveQualityBucket.BEST.value: 0.0,
            MoveQualityBucket.BLUNDER.value: 0.0,
            MoveQualityBucket.OTHER.value: 0.0,
        }
    )
    quality_timed_moves: dict[str, int] = field(
        default_factory=lambda: {
            MoveQualityBucket.BEST.value: 0,
            MoveQualityBucket.BLUNDER.value: 0,
            MoveQualityBucket.OTHER.value: 0,
        }
    )

    def record(
        self,
        time_spent: float | None,
        time_left: float | None,
        phase: str,
        classification: str,
        trouble_threshold: float,
    ) -> None:
        if time_spent is not None and 0.0 <= time_spent < MAX_REASONABLE_TIME_SECONDS:
            self.total_timed_moves += 1
            self.total_time_spent += time_spent
            if phase in self.phase_time_spent:
                self.phase_time_spent[phase] += time_spent
                self.phase_timed_moves[phase] += 1

            if classification in ("Brilliant", "Great", "Best"):
                quality_bucket = MoveQualityBucket.BEST.value
            elif classification in ("Blunder", "Mistake"):
                quality_bucket = MoveQualityBucket.BLUNDER.value
            else:
                quality_bucket = MoveQualityBucket.OTHER.value
            self.quality_time_spent[quality_bucket] += time_spent
            self.quality_timed_moves[quality_bucket] += 1

        if time_left is not None and time_left >= 0.0:
            is_blunder_or_mistake = classification in ("Blunder", "Mistake")
            if time_left <= trouble_threshold:
                self.trouble_moves += 1
                if is_blunder_or_mistake:
                    self.trouble_blunders += 1
            else:
                self.normal_moves += 1
                if is_blunder_or_mistake:
                    self.normal_blunders += 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_timed_moves": self.total_timed_moves,
            "total_time_spent": round(self.total_time_spent, 1),
            "phase_time_spent": {k: round(v, 1) for k, v in self.phase_time_spent.items()},
            "phase_timed_moves": dict(self.phase_timed_moves),
            "quality_time_spent": {k: round(v, 1) for k, v in self.quality_time_spent.items()},
            "quality_timed_moves": dict(self.quality_timed_moves),
            "normal_moves": self.normal_moves,
            "normal_blunders": self.normal_blunders,
            "trouble_moves": self.trouble_moves,
            "trouble_blunders": self.trouble_blunders,
        }


@dataclass
class TacticsState:
    """Accumulates tactical tracking state across a full game analysis."""

    phase_accuracies: dict[str, list[float]] = field(
        default_factory=lambda: {p: [] for p in PHASES}
    )
    phase_win_percents: dict[str, list[float]] = field(
        default_factory=lambda: {p: [] for p in PHASES}
    )
    phase_blunders: dict[str, int] = field(default_factory=lambda: dict.fromkeys(PHASES, 0))
    phase_move_counts: dict[str, int] = field(default_factory=lambda: dict.fromkeys(PHASES, 0))
    pieces_hung_by_type: dict[str, int] = field(
        default_factory=lambda: dict.fromkeys(PIECE_NAMES_ORDERED, 0)
    )
    captured_by_piece: dict[str, int] = field(
        default_factory=lambda: dict.fromkeys(PIECE_NAMES_ORDERED, 0)
    )
    tactical_themes: dict[str, int] = field(
        default_factory=lambda: {theme.value: 0 for theme in TacticalTheme}
    )
    tactical_roles: dict[str, dict[str, int]] = field(
        default_factory=lambda: {
            theme.value: {
                TacticRole.EXECUTED.value: 0,
                TacticRole.ALLOWED.value: 0,
                TacticRole.MISSED.value: 0,
            }
            for theme in TacticalTheme
        }
    )

    brilliancies: list[dict[str, Any]] = field(default_factory=list)
    hung_pieces_details: list[dict[str, Any]] = field(default_factory=list)
    opp_captured_details: list[dict[str, Any]] = field(default_factory=list)
    tactical_motifs_details: list[dict[str, Any]] = field(default_factory=list)
    blunders_details: list[dict[str, Any]] = field(default_factory=list)
    missed_tactics_details: list[dict[str, Any]] = field(default_factory=list)
    tactic_facts: list[dict[str, Any]] = field(default_factory=list)

    had_winning_advantage: bool = False
    converted_advantage: bool = False
    choked_advantage: bool = False
    thrown_losses: bool = False
    squandered_draws: bool = False
    had_losing_position: bool = False
    comeback_drawn_or_won: bool = False
    comeback_wins: bool = False
    comeback_draws: bool = False
    lost_deficit: bool = False

    max_lead_drop: float = 0.0
    max_comeback_gain: float = 0.0
    lead_collapse_move: dict[str, Any] | None = None
    comeback_turn_move: dict[str, Any] | None = None

    peak_eval_cp: int | None = None
    lowest_eval_cp: int | None = None
    book_exit_ply: int | None = None

    immediate_hung: int = 0
    punished_lost: int = 0
    total_lost: int = 0
    hanging_blunders: int = 0
    opponent_hanging_captured: int = 0
    opponent_hanging_missed: int = 0
    seen_loss_keys: set[tuple[int, str]] = field(default_factory=set)

    clock_stats: ClockStats = field(default_factory=ClockStats)


# ==============================================================================
# RECORDERS
# ==============================================================================


def _move_detail(ctx: MoveCtx, **extra: Any) -> dict[str, Any]:
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


def _phase_accuracy(accuracies: list[float], win_percents: list[float]) -> float | None:
    if not accuracies:
        return None
    return aggregate_accuracy(accuracies, win_percents)


def _record_accuracy(ctx: MoveCtx, state: TacticsState) -> None:
    state.phase_move_counts[ctx.phase] += 1

    if ctx.is_book or ctx.is_checkmate_move or ctx.is_mating_move:
        accuracy = 100.0
    else:
        accuracy = calculate_move_accuracy(ctx.player_wp_before, ctx.player_wp_after)

    accuracy = apply_accuracy_floor(accuracy)
    state.phase_accuracies[ctx.phase].append(accuracy)
    state.phase_win_percents[ctx.phase].append(ctx.player_wp_before)

    if ctx.classification in BLUNDER_CLASSIFICATIONS:
        state.phase_blunders[ctx.phase] += 1
        state.blunders_details.append(_move_detail(ctx))


def _record_brilliancies(ctx: MoveCtx, state: TacticsState) -> None:
    if ctx.classification in BRILLIANT_CLASSIFICATIONS:
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


def _record_turning_points(ctx: MoveCtx, state: TacticsState) -> None:
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
        state.lead_collapse_move = _move_detail(ctx)

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


def _record_clock(ctx: MoveCtx, state: TacticsState, trouble_threshold: float) -> None:
    state.clock_stats.record(
        time_spent=ctx.time_spent,
        time_left=ctx.time_left,
        phase=ctx.phase,
        classification=ctx.classification,
        trouble_threshold=trouble_threshold,
    )


def _record_facts(
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
                **_move_detail(ctx, motif=fact.motif),
                "role": role.value,
                "confidence": fact.confidence,
                "target_square": fact.target_square,
                "target_piece": fact.target_piece,
                "evidence": fact.evidence,
            }
        )
        state.tactic_facts.append(fact_to_dict(fact))


def _record_losses(ctx: MoveCtx, state: TacticsState, losses: list[LossRecord]) -> None:
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
                **_move_detail(ctx),
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


def _record_opp_hanging(
    ctx: MoveCtx,
    state: TacticsState,
    opp_hanging_before: list[dict[str, Any]],
    prev_ctx: MoveCtx | None,
) -> None:
    """Records user capitalising on, or missing, opponent hanging pieces."""
    if not opp_hanging_before or ctx.move_obj is None:
        return

    if _is_previous_capture(ctx, prev_ctx):
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


def _is_previous_capture(ctx: MoveCtx, prev_ctx: MoveCtx | None) -> bool:
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

    _, captured = _captured_piece(prev_ctx.board_before, prev_ctx.move_obj)
    user_piece = ctx.board_before.piece_at(ctx.move_obj.to_square)
    if captured is None or user_piece is None:
        return False

    return PIECE_VALUES.get(captured.piece_type, 0) >= PIECE_VALUES.get(
        user_piece.piece_type, 0
    )


def _captured_piece(
    board: chess.Board, move: chess.Move
) -> tuple[chess.Square, chess.Piece | None]:
    if board.is_en_passant(move):
        square = chess.square(
            chess.square_file(move.to_square),
            chess.square_rank(move.from_square),
        )
    else:
        square = move.to_square
    return square, board.piece_at(square)


def _record_missed_tactics(ctx: MoveCtx, state: TacticsState) -> None:
    """High-confidence missed tactics: hanging captures and mate in one."""
    if ctx.move_obj is None:
        return

    enemy_hanging = get_lost_pieces(ctx.board_before, not ctx.board_before.turn)
    captured_square = (
        chess.square_name(_captured_piece(ctx.board_before, ctx.move_obj)[0])
        if ctx.board_before.is_capture(ctx.move_obj)
        else None
    )

    missed_capture = next(
        (item for item in enemy_hanging if item["square"] != captured_square),
        None,
    )
    if missed_capture is not None:
        state.tactical_roles[TacticalTheme.HANGING_PIECE.value][TacticRole.MISSED.value] += 1
        state.missed_tactics_details.append(
            {
                **_move_detail(ctx),
                "motif": TacticalTheme.HANGING_PIECE.value,
                "role": TacticRole.MISSED.value,
                "missed_square": missed_capture["square"],
                "missed_piece": missed_capture["piece_name"],
                "missed_see_gain": missed_capture.get("enemy_see_gain", 0),
            }
        )

    mate_move = _find_mate_in_one(ctx.board_before)
    if mate_move is not None and ctx.move_obj != mate_move:
        state.missed_tactics_details.append(
            {
                **_move_detail(ctx),
                "motif": TacticalTheme.BACK_RANK_MATE.value,
                "role": TacticRole.MISSED.value,
                "missed_uci": mate_move.uci(),
                "missed_san": ctx.board_before.san(mate_move),
            }
        )


def _find_mate_in_one(board: chess.Board) -> chess.Move | None:
    for move in board.legal_moves:
        if not board.gives_check(move):
            continue
        work = board.copy(stack=False)
        work.push(move)
        if work.is_checkmate():
            return move
    return None


# ==============================================================================
# MAIN ENTRY POINT
# ==============================================================================


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

    trouble_threshold = DEFAULT_TROUBLE_SECONDS
    category = (speed_category or "blitz").lower()
    for key, seconds in TROUBLE_SECONDS.items():
        if key in category:
            trouble_threshold = seconds
            break

    contexts = build_contexts(moves_data, is_user_white)
    state = TacticsState()

    for index, ctx in enumerate(contexts):
        if ctx is None:
            continue

        if not ctx.is_book and state.book_exit_ply is None:
            state.book_exit_ply = ctx.ply

        if not ctx.is_user_move:
            continue

        _record_accuracy(ctx, state)
        _record_turning_points(ctx, state)
        _record_brilliancies(ctx, state)
        _record_clock(ctx, state, trouble_threshold)

        if ctx.move_obj is None or ctx.board_after is None:
            continue

        next_ctx = contexts[index + 1] if index + 1 < len(contexts) else None
        prev_ctx = contexts[index - 1] if index > 0 else None

        losses = resolve_losses(ctx, next_ctx, target_color)
        _record_losses(ctx, state, losses)

        executed = confirm_facts(
            detect_candidates(
                ctx.board_before,
                ctx.board_after,
                ctx.move_obj,
                ctx.board_before.turn,
                ctx.classification,
            ),
            ctx.board_after,
            reply_move=next_ctx.move_obj if next_ctx is not None else None,
            engine_pv=list(next_ctx.engine_pv) if next_ctx is not None else None,
            classification=ctx.classification,
            board_before=ctx.board_before,
        )
        _record_facts(ctx, state, executed, TacticRole.EXECUTED)

        if (
            next_ctx is not None
            and next_ctx.move_obj is not None
            and next_ctx.board_after is not None
            and (not is_sound_move(ctx) or ctx.classification in BAD_MOVE_CLASSIFICATIONS)
        ):
            allowed = confirm_facts(
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
            _record_facts(next_ctx, state, allowed, TacticRole.ALLOWED)

        _record_missed_tactics(ctx, state)

        _record_opp_hanging(
            ctx,
            state,
            get_lost_pieces(ctx.board_before, enemy_color),
            prev_ctx,
        )

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

    phase_accuracies = {
        phase: _phase_accuracy(
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
            "lowest_eval_cp": state.lowest_eval_cp if state.lowest_eval_cp is not None else 0,
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
