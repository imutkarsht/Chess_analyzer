"""
Comprehensive game tactical analysis, phase accuracies, advantage conversion,
and drill-down position tracking.
Zero Qt dependencies — headless and independently testable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import chess

from src.backend.analysis.math_utils import (
    apply_accuracy_floor,
    calculate_move_accuracy,
    calculate_volatility_weights,
    harmonic_mean,
    weighted_mean,
)
from src.backend.analysis.tactics.board_utils import to_user_cp, to_user_wp
from src.backend.analysis.tactics.constants import (
    ADVANTAGE_THRESHOLD_CP,
    BAD_MOVE_CLASSIFICATIONS,
    BLUNDER_CLASSIFICATIONS,
    BRILLIANT_CLASSIFICATIONS,
    DEFAULT_TROUBLE_SECONDS,
    GOOD_MOVE_WP_DROP_THRESHOLD,
    MAX_REASONABLE_TIME_SECONDS,
    PHASES,
    PIECE_NAMES_ORDERED,
    PIECE_VALUES,
    SOUND_MOVE_WP_DROP_THRESHOLD,
    SOUND_TACTIC_MAX_WP_DROP,
    TROUBLE_SECONDS,
    TURNING_POINT_MIN_WP_SWING,
    WINNING_WP_THRESHOLD,
    MoveQualityBucket,
    TacticalTheme,
)
from src.backend.analysis.tactics.hanging import get_hanging_pieces
from src.backend.analysis.tactics.motifs import detect_tactical_motifs
from src.backend.analysis.tactics.phase import classify_game_phase

# ==============================================================================
# CONTEXT & DATA OBJECTS
# ==============================================================================


@dataclass(frozen=True)
class MoveCtx:
    """Immutable data context for a single analyzed ply in the game."""

    ply: int
    move_number: int
    san: str
    uci: str
    fen_before: str
    fen_after: str
    classification: str
    eval_user_cp: int | None
    eval_after_user: int | None
    eval_diff: int | None
    wp_drop: float
    player_wp_before: float
    player_wp_after: float
    is_user_move: bool
    is_book: bool
    is_mating_move: bool
    is_checkmate_move: bool
    board_before: chess.Board
    board_after: chess.Board | None
    move_obj: chess.Move | None
    phase: str
    time_spent: float | None = None
    time_left: float | None = None
    opening_name: str = ""
    explanation: str = ""


def _move_detail(mv: MoveCtx, **extra: Any) -> dict[str, Any]:
    """Factory creating the standardized 11-key drill-down detail dictionary."""
    return {
        "ply": mv.ply,
        "move_number": mv.move_number,
        "san": mv.san,
        "uci": mv.uci,
        "fen_before": mv.fen_before,
        "fen_after": mv.fen_after,
        "classification": mv.classification,
        "eval_before_cp": mv.eval_user_cp,
        "eval_after_cp": mv.eval_after_user,
        "eval_drop": mv.eval_diff,
        "wp_drop": round(mv.wp_drop, 3),
        **extra,
    }


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
        default_factory=lambda: {t.value: 0 for t in TacticalTheme}
    )

    brilliancies: list[dict[str, Any]] = field(default_factory=list)
    hung_pieces_details: list[dict[str, Any]] = field(default_factory=list)
    opp_captured_details: list[dict[str, Any]] = field(default_factory=list)
    tactical_motifs_details: list[dict[str, Any]] = field(default_factory=list)
    blunders_details: list[dict[str, Any]] = field(default_factory=list)

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
    total_hung: int = 0
    hanging_blunders: int = 0
    opponent_hanging_captured: int = 0
    opponent_hanging_missed: int = 0

    clock_stats: ClockStats = field(default_factory=ClockStats)


# ==============================================================================
# RECORDERS
# ==============================================================================


def _phase_accuracy(accuracies: list[float], win_percents: list[float]) -> float | None:
    """Computes harmonic volatility-weighted phase accuracy."""
    if not accuracies:
        return None
    if len(accuracies) == 1:
        return accuracies[0]
    window_size = max(2, min(8, len(accuracies) // 10))
    weights = calculate_volatility_weights(win_percents, window_size)
    wm = weighted_mean(accuracies, weights)
    hm = harmonic_mean(accuracies)
    return (wm + hm) / 2.0


def _record_accuracy(ctx: MoveCtx, state: TacticsState) -> None:
    """Records move accuracy and blunder occurrence by game phase."""
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


def _record_hanging(
    ctx: MoveCtx,
    state: TacticsState,
    hanging_before: list[dict[str, Any]],
    hanging_after: list[dict[str, Any]],
) -> None:
    """Records hung pieces and hanging blunders resulting from user moves."""
    is_advantageous_or_sound = (
        ctx.is_book
        or ctx.classification in ("Brilliant", "Great", "Best", "Excellent")
        or (ctx.classification == "Good" and ctx.wp_drop < GOOD_MOVE_WP_DROP_THRESHOLD)
        or (
            ctx.wp_drop < SOUND_MOVE_WP_DROP_THRESHOLD
            and ctx.player_wp_after >= WINNING_WP_THRESHOLD
        )
    )
    if is_advantageous_or_sound:
        return

    hung_sqs_before = {h["square"] for h in hanging_before}
    to_sq_name = chess.square_name(ctx.move_obj.to_square) if ctx.move_obj else ""
    newly_hung = [
        h for h in hanging_after if h["square"] not in hung_sqs_before or h["square"] == to_sq_name
    ]

    if newly_hung:
        state.total_hung += len(newly_hung)
        for h in newly_hung:
            p_name = h["piece_name"]
            if p_name in state.pieces_hung_by_type:
                state.pieces_hung_by_type[p_name] += 1
            state.hung_pieces_details.append(
                _move_detail(ctx, piece_name=p_name, square=h["square"])
            )

        if ctx.classification in BAD_MOVE_CLASSIFICATIONS:
            state.hanging_blunders += 1


def _record_opp_hanging(
    ctx: MoveCtx,
    state: TacticsState,
    opp_hanging_before: list[dict[str, Any]],
    prev_move_obj: chess.Move | None = None,
    prev_board_before: chess.Board | None = None,
) -> None:
    """Records user capitalizing on or missing opponent hanging pieces."""
    if not opp_hanging_before or not ctx.move_obj:
        return

    # Routine recapture / exchange filter:
    # If user is capturing on the exact square where opponent just captured an equal
    # or greater value piece on the immediately preceding ply, this is a routine
    # recapture completing an exchange — NOT capitalizing on an opponent hanging piece!
    if (
        prev_move_obj is not None
        and prev_board_before is not None
        and prev_move_obj.to_square == ctx.move_obj.to_square
    ):
        opp_captured_piece = prev_board_before.piece_at(ctx.move_obj.to_square)
        if opp_captured_piece is None and prev_board_before.is_en_passant(prev_move_obj):
            ep_sq = chess.square(
                chess.square_file(prev_move_obj.to_square),
                chess.square_rank(prev_move_obj.from_square),
            )
            opp_captured_piece = prev_board_before.piece_at(ep_sq)

        if opp_captured_piece is not None:
            opp_captured_val = PIECE_VALUES.get(opp_captured_piece.piece_type, 0)
            opp_mover_piece = ctx.board_before.piece_at(ctx.move_obj.to_square)
            opp_mover_val = (
                PIECE_VALUES.get(opp_mover_piece.piece_type, 0)
                if opp_mover_piece is not None
                else 0
            )
            if opp_captured_val >= opp_mover_val:
                return

    opp_hung_sqs = {h["square"]: h for h in opp_hanging_before}
    to_sq_name = chess.square_name(ctx.move_obj.to_square)

    if to_sq_name in opp_hung_sqs:
        # Only count as a successful capture if user didn't blunder into a trap/poisoned piece
        if (
            ctx.classification not in BAD_MOVE_CLASSIFICATIONS
            and ctx.wp_drop < SOUND_TACTIC_MAX_WP_DROP
        ):
            state.opponent_hanging_captured += 1
            captured_h = opp_hung_sqs[to_sq_name]
            p_name = captured_h["piece_name"]
            if p_name in state.captured_by_piece:
                state.captured_by_piece[p_name] += 1
            state.opp_captured_details.append(
                {
                    "piece_name": p_name,
                    "square": to_sq_name,
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
    elif opp_hanging_before and ctx.classification in ("Mistake", "Blunder", "Miss"):
        state.opponent_hanging_missed += 1


def _record_motifs(ctx: MoveCtx, state: TacticsState) -> None:
    """Detects and records tactical motifs on sound moves."""
    if not ctx.move_obj or not ctx.board_after:
        return
    if ctx.classification in BAD_MOVE_CLASSIFICATIONS or ctx.wp_drop >= SOUND_TACTIC_MAX_WP_DROP:
        return

    motifs = detect_tactical_motifs(
        ctx.board_before,
        ctx.board_after,
        ctx.move_obj,
        ctx.board_before.turn,
        ctx.classification,
    )
    for motif in motifs:
        if motif in state.tactical_themes:
            state.tactical_themes[motif] += 1
            state.tactical_motifs_details.append(_move_detail(ctx, motif=motif))


def _record_brilliancies(ctx: MoveCtx, state: TacticsState) -> None:
    """Records brilliancies and great moves."""
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
    """Tracks peak/lowest evaluation and advantage collapse/comeback turning points."""
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
        eval_gain = -ctx.eval_diff if ctx.eval_diff is not None else None
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
            "eval_gain": eval_gain,
            "wp_gain": round(wp_gain, 3),
        }


def _record_clock(
    ctx: MoveCtx,
    state: TacticsState,
    trouble_threshold: float,
) -> None:
    """Records clock metrics for timed moves."""
    state.clock_stats.record(
        time_spent=ctx.time_spent,
        time_left=ctx.time_left,
        phase=ctx.phase,
        classification=ctx.classification,
        trouble_threshold=trouble_threshold,
    )


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
    Full comprehensive tactical, phase, and advantage analysis of a game's moves.

    Returns a rich dict containing:
    - phase_accuracies: {opening: float, middlegame: float, endgame: float}
    - phase_blunders: {opening: int, middlegame: int, endgame: int}
    - phase_move_counts: {opening: int, middlegame: int, endgame: int}
    - hanging_metrics: {total_hung, by_piece, captured_by_piece, ...}
    - advantage_metrics: {had_winning_advantage, converted_advantage, ...}
    - brilliancies: list of brilliancy dicts
    - tactical_themes: {fork, pin, skewer, discovered_attack, sacrifice, back_rank}
    - drill_down detail lists (hung_pieces_details, opp_captured_details, etc.)
    - clock_metrics: aggregated timing summary
    """
    is_user_white = user_color.lower() == "white"
    target_color = chess.WHITE if is_user_white else chess.BLACK

    cat = (speed_category or "blitz").lower()
    trouble_threshold = DEFAULT_TROUBLE_SECONDS
    for k, v in TROUBLE_SECONDS.items():
        if k in cat:
            trouble_threshold = v
            break

    state = TacticsState()
    cached_hanging_target: list[dict[str, Any]] | None = None
    cached_hanging_enemy: list[dict[str, Any]] | None = None
    prev_move_obj: chess.Move | None = None
    prev_board_before: chess.Board | None = None

    for idx, move_dict in enumerate(moves_data):
        ply = move_dict.get("ply", idx)
        move_number = move_dict.get("move_number", (ply + 1) // 2)
        san = move_dict.get("san", "")
        uci = move_dict.get("uci", "")
        fen_before = move_dict.get("fen_before", "")
        fen_after = move_dict.get("fen_after", "")
        classification = move_dict.get("classification", "")
        is_book = bool(move_dict.get("is_book_move", move_dict.get("is_book", False)))
        eval_before_raw = move_dict.get("eval_before_cp")
        eval_after_raw = move_dict.get("eval_after_cp")
        eval_after_mate = move_dict.get("eval_after_mate")

        wp_before_raw = move_dict.get("win_chance_before", 0.5)
        wp_after_raw = move_dict.get("win_chance_after", 0.5)
        player_wp_before = to_user_wp(wp_before_raw, is_user_white)
        player_wp_after = to_user_wp(wp_after_raw, is_user_white)

        is_checkmate_move = san.endswith("#") if san else False
        is_mating_move = eval_after_mate is not None and (
            (is_user_white and eval_after_mate > 0) or (not is_user_white and eval_after_mate < 0)
        )

        time_spent = move_dict.get("time_spent")
        time_left = move_dict.get("time_left")
        opening_name = move_dict.get("opening_name", "")
        explanation = move_dict.get("explanation", "")

        try:
            board_before = chess.Board(fen_before) if fen_before else chess.Board()
        except Exception:
            board_before = chess.Board()

        is_white_turn = board_before.turn == chess.WHITE if fen_before else (ply % 2 == 0)
        is_user_move = is_white_turn == is_user_white

        phase = classify_game_phase(board_before, ply, is_book_move=is_book)
        if not is_book and state.book_exit_ply is None:
            state.book_exit_ply = ply

        # Move parsing (if move exists)
        move_obj: chess.Move | None = None
        board_after: chess.Board | None = None
        if uci or san:
            try:
                move_obj = chess.Move.from_uci(uci) if uci else board_before.parse_san(san)
                board_after = chess.Board(fen_after) if fen_after else board_before.copy()
                if not fen_after:
                    board_after.push(move_obj)
            except (ValueError, chess.IllegalMoveError):
                move_obj = None
                board_after = None
        elif fen_after:
            try:
                board_after = chess.Board(fen_after)
            except ValueError:
                board_after = None

        if board_after is not None:
            fen_after = board_after.fen()

        eval_user_cp = to_user_cp(eval_before_raw, is_user_white)
        eval_after_user = to_user_cp(eval_after_raw, is_user_white)
        eval_diff = (
            (eval_user_cp - eval_after_user)
            if (eval_user_cp is not None and eval_after_user is not None)
            else move_dict.get("eval_diff")
        )
        wp_drop = max(0.0, player_wp_before - player_wp_after)

        ctx = MoveCtx(
            ply=ply,
            move_number=move_number,
            san=san,
            uci=uci,
            fen_before=fen_before,
            fen_after=fen_after,
            classification=classification,
            eval_user_cp=eval_user_cp,
            eval_after_user=eval_after_user,
            eval_diff=eval_diff,
            wp_drop=wp_drop,
            player_wp_before=player_wp_before,
            player_wp_after=player_wp_after,
            is_user_move=is_user_move,
            is_book=is_book,
            is_mating_move=is_mating_move,
            is_checkmate_move=is_checkmate_move,
            board_before=board_before,
            board_after=board_after,
            move_obj=move_obj,
            phase=phase,
            time_spent=time_spent,
            time_left=time_left,
            opening_name=opening_name,
            explanation=explanation,
        )

        if not is_user_move:
            if board_after is not None:
                cached_hanging_target = get_hanging_pieces(board_after, target_color)
                cached_hanging_enemy = get_hanging_pieces(
                    board_after, not target_color, last_move=move_obj, board_before=board_before
                )
            prev_move_obj = move_obj
            prev_board_before = board_before
            continue

        # User move analysis
        _record_accuracy(ctx, state)
        _record_turning_points(ctx, state)
        _record_brilliancies(ctx, state)
        _record_clock(ctx, state, trouble_threshold)

        if move_obj is not None and board_after is not None:
            hanging_before = (
                cached_hanging_target
                if cached_hanging_target is not None
                else get_hanging_pieces(board_before, target_color)
            )
            opp_hanging_before = (
                cached_hanging_enemy
                if cached_hanging_enemy is not None
                else get_hanging_pieces(
                    board_before,
                    not target_color,
                    last_move=prev_move_obj,
                    board_before=prev_board_before,
                )
            )

            hanging_after = get_hanging_pieces(
                board_after, target_color, last_move=move_obj, board_before=board_before
            )
            cached_hanging_target = hanging_after
            cached_hanging_enemy = get_hanging_pieces(board_after, not target_color)

            _record_hanging(ctx, state, hanging_before, hanging_after)
            _record_opp_hanging(
                ctx,
                state,
                opp_hanging_before,
                prev_move_obj=prev_move_obj,
                prev_board_before=prev_board_before,
            )
            _record_motifs(ctx, state)

        prev_move_obj = move_obj
        prev_board_before = board_before

    # Finalize advantage conversion
    is_user_win = (result == "1-0" and is_user_white) or (result == "0-1" and not is_user_white)
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

    phase_acc_results = {
        p: _phase_accuracy(state.phase_accuracies[p], state.phase_win_percents[p]) for p in PHASES
    }

    return {
        "phase_accuracies": phase_acc_results,
        "phase_blunders": state.phase_blunders,
        "phase_move_counts": state.phase_move_counts,
        "hanging_metrics": {
            "total_hung": state.total_hung,
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
        "tactical_themes": state.tactical_themes,
        "hung_pieces_details": state.hung_pieces_details,
        "opp_captured_details": state.opp_captured_details,
        "tactical_motifs_details": state.tactical_motifs_details,
        "blunders_details": state.blunders_details,
        "lead_collapse_move": state.lead_collapse_move,
        "comeback_turn_move": state.comeback_turn_move,
        "book_exit_ply": state.book_exit_ply,
        "clock_metrics": state.clock_stats.to_dict(),
    }
