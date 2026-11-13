"""
Candidate tactical motif detection.

Detectors describe *why* a move is tactical using legal moves and static
exchange evaluation. They never assign headline confidence: that is the job of
``validation.py``, which corroborates candidates with the game reply, engine PV
or mate evidence.

Motif definitions follow the Lichess puzzle themes:
- pin: a piece cannot leave a line without exposing a more valuable piece;
- skewer: the inverse, a more valuable front piece is forced away and a lower
  value rear piece is captured;
- fork: one piece attacks two or more meaningful targets;
- hanging piece: an enemy piece can be won by a legal capture;
- removal of the defender: capturing a defender leaves another piece loose.

Zero Qt dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import chess

from src.backend.analysis.tactics.board_utils import (
    find_slider_ray_targets,
    is_on_segment,
    min_attacker_value,
    piece_value,
)
from src.backend.analysis.tactics.constants import (
    KING_SKEWER_VALUE,
    MIN_SACRIFICE_DEFICIT_CP,
    PIECE_NAMES,
    PIECE_VALUES,
    SOUND_CLASSIFICATIONS,
    Confidence,
    TacticalTheme,
    TacticRole,
)
from src.backend.analysis.tactics.facts import TacticFact
from src.backend.analysis.tactics.piece_safety import get_lost_pieces, is_piece_doomed
from src.backend.analysis.tactics.see import is_safely_placed, static_exchange_evaluation


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


# ---------------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------------


def _sliders(board: chess.Board, color: chess.Color) -> chess.SquareSet:
    return (
        board.pieces(chess.BISHOP, color)
        | board.pieces(chess.ROOK, color)
        | board.pieces(chess.QUEEN, color)
    )


def _stays_on_line(
    square: chess.Square,
    slider_sq: chess.Square,
    rear_sq: chess.Square,
) -> bool:
    """True when ``square`` keeps blocking the slider-to-rear line."""
    return square in (slider_sq, rear_sq) or is_on_segment(slider_sq, rear_sq, square)


def _affected_alignments(
    ctx: MotifCtx,
) -> list[tuple[chess.Square, chess.Square, chess.Square]]:
    """
    Newly formed (slider, front, rear) alignments.

    A slider that moved is compared with the ray from its previous square, so a
    slider that simply keeps the same pin is not reported again.
    """
    alignments: list[tuple[chess.Square, chess.Square, chess.Square]] = []

    for slider_sq in _sliders(ctx.after, ctx.color):
        after_pairs = find_slider_ray_targets(ctx.after, slider_sq, ctx.color)
        previous_sq = ctx.move.from_square if slider_sq == ctx.move.to_square else slider_sq
        before_pairs = find_slider_ray_targets(ctx.before, previous_sq, ctx.color)
        before_set = {(front_sq, rear_sq) for front_sq, _, rear_sq, _ in before_pairs}

        for front_sq, _front_p, rear_sq, _rear_p in after_pairs:
            if (front_sq, rear_sq) not in before_set:
                alignments.append((slider_sq, front_sq, rear_sq))

    return alignments


# ---------------------------------------------------------------------------
# Pin and skewer
# ---------------------------------------------------------------------------


def _pin_is_effective(
    board: chess.Board,
    enemy_color: chess.Color,
    slider_sq: chess.Square,
    front_sq: chess.Square,
    rear_sq: chess.Square,
) -> bool:
    """True when the front piece cannot leave the line without losing the rear."""
    if board.is_pinned(enemy_color, front_sq):
        return True

    front = board.piece_at(front_sq)
    rear = board.piece_at(rear_sq)
    if front is None or rear is None or front.piece_type == chess.KING:
        return False

    front_value = PIECE_VALUES.get(front.piece_type, 0)
    rear_value = PIECE_VALUES.get(rear.piece_type, 0)
    if rear_value <= front_value:
        return False

    for move in board.legal_moves:
        if move.from_square != front_sq:
            continue
        if move.to_square == slider_sq:
            return False  # captures the pinner
        if _stays_on_line(move.to_square, slider_sq, rear_sq):
            continue

        next_board = board.copy(stack=False)
        next_board.push(move)
        if not _is_lost_by(next_board, rear_sq, rear.color, not enemy_color):
            return False

    return True


def _skewer_is_effective(
    board: chess.Board,
    enemy_color: chess.Color,
    slider_sq: chess.Square,
    front_sq: chess.Square,
    rear_sq: chess.Square,
) -> bool:
    """
    True when the front piece is genuinely forced off the line and the rear
    piece becomes doomed.

    A rear king is always a pin, never a skewer. A king front piece only counts
    when the check cannot be blocked by another piece. A non-king front piece
    must itself be hanging; otherwise it can simply stay on the line.
    """
    front = board.piece_at(front_sq)
    rear = board.piece_at(rear_sq)
    if front is None or rear is None or rear.piece_type == chess.KING:
        return False

    front_value = (
        KING_SKEWER_VALUE
        if front.piece_type == chess.KING
        else PIECE_VALUES.get(front.piece_type, 0)
    )
    rear_value = PIECE_VALUES.get(rear.piece_type, 0)
    if front_value <= rear_value:
        return False

    if front_sq not in board.attacks(slider_sq):
        return False

    if front.piece_type == chess.KING:
        if not board.is_check():
            return False
    elif not _is_lost_by(board, front_sq, enemy_color, not enemy_color):
        return False

    exposed = False
    for move in board.legal_moves:
        if move.from_square != front_sq:
            continue
        if move.to_square == slider_sq:
            return False  # can capture the skewering piece
        if _stays_on_line(move.to_square, slider_sq, rear_sq):
            return False  # can keep blocking

        next_board = board.copy(stack=False)
        next_board.push(move)
        # The rear piece must be genuinely attacked; it does not have to be
        # unable to move, because a skewer can win it or force it away.
        if not _is_lost_by(next_board, rear_sq, rear.color, not enemy_color):
            return False
        exposed = True

    return exposed


def _is_lost_by(
    board: chess.Board,
    square: chess.Square,
    color: chess.Color,
    attacker: chess.Color,
) -> bool:
    """True when ``attacker`` can win the piece on ``square``."""
    if attacker == board.turn:
        return static_exchange_evaluation(board, square, attacker) > 0
    work = board.copy(stack=False)
    work.turn = attacker
    return static_exchange_evaluation(work, square, attacker) > 0


# ---------------------------------------------------------------------------
# Fork
# ---------------------------------------------------------------------------


def _fork_target_is_meaningful(
    board: chess.Board,
    target_sq: chess.Square,
    enemy_color: chess.Color,
    forking_value: int,
) -> bool:
    """King or a non-pawn piece that can actually be won."""
    target = board.piece_at(target_sq)
    if target is None or target.color != enemy_color:
        return False
    if target.piece_type == chess.KING:
        return True
    if target.piece_type == chess.PAWN:
        return False

    target_value = PIECE_VALUES.get(target.piece_type, 0)
    return target_value > forking_value or static_exchange_evaluation(
        board, target_sq, not enemy_color
    ) > 0


# ---------------------------------------------------------------------------
# Detectors
# ---------------------------------------------------------------------------


def _executed_hanging_pieces(ctx: MotifCtx) -> list[TacticFact]:
    """Hanging pieces captured by the move, plus enemy pieces it newly dooms."""
    before_lost = {
        item["square"] for item in get_lost_pieces(ctx.before, ctx.enemy_color)
    }
    facts: list[TacticFact] = []

    # Capturing a piece that was already hanging is itself a hanging-piece tactic.
    if ctx.before.is_capture(ctx.move):
        captured_sq = (
            chess.square(
                chess.square_file(ctx.move.to_square),
                chess.square_rank(ctx.move.from_square),
            )
            if ctx.before.is_en_passant(ctx.move)
            else ctx.move.to_square
        )
        captured = ctx.before.piece_at(captured_sq)
        if (
            captured is not None
            and captured.color == ctx.enemy_color
            and _is_lost_by(ctx.before, captured_sq, ctx.enemy_color, ctx.color)
        ):
            facts.append(
                TacticFact(
                    motif=TacticalTheme.HANGING_PIECE.value,
                    role=TacticRole.EXECUTED.value,
                    side=ctx.side,
                    confidence=Confidence.PROBABLE.value,
                    move_san=ctx.move_san,
                    move_uci=ctx.move.uci(),
                    origin_square=chess.square_name(ctx.move.from_square),
                    target_square=chess.square_name(captured_sq),
                    target_piece=PIECE_NAMES.get(captured.piece_type, "piece"),
                    targets=(chess.square_name(captured_sq),),
                    evidence="captures a piece that was already hanging",
                    material_gain_cp=PIECE_VALUES.get(captured.piece_type, 0) * 100,
                )
            )

    for item in get_lost_pieces(
        ctx.after,
        ctx.enemy_color,
        last_move=ctx.move,
        board_before=ctx.before,
    ):
        if item["square"] in before_lost:
            continue

        square = item["square_index"]
        if not is_piece_doomed(ctx.after, square, ctx.enemy_color):
            continue

        facts.append(
            TacticFact(
                motif=TacticalTheme.HANGING_PIECE.value,
                role=TacticRole.EXECUTED.value,
                side=ctx.side,
                confidence=Confidence.PROBABLE.value,
                move_san=ctx.move_san,
                move_uci=ctx.move.uci(),
                origin_square=chess.square_name(ctx.move.from_square),
                target_square=item["square"],
                target_piece=item["piece_name"],
                targets=(item["square"],),
                evidence=f"{item['piece_name']} on {item['square']} cannot be saved",
                material_gain_cp=item.get("enemy_see_gain", 0),
            )
        )

    return facts


def _fork_fact(ctx: MotifCtx) -> TacticFact | None:
    if ctx.piece.piece_type == chess.KING:
        return None
    if not is_safely_placed(ctx.after, ctx.move.to_square, ctx.color):
        return None

    forking_value = piece_value(ctx.after, ctx.move.to_square)
    before_attacks = (
        ctx.before.attacks(ctx.move.from_square)
        if ctx.before.piece_at(ctx.move.from_square)
        else chess.SquareSet()
    )

    targets: list[tuple[chess.Square, chess.Piece]] = []
    new_target = False
    for target_sq in ctx.after.attacks(ctx.move.to_square):
        if not _fork_target_is_meaningful(
            ctx.after, target_sq, ctx.enemy_color, forking_value
        ):
            continue
        target = ctx.after.piece_at(target_sq)
        if target is None:
            continue
        targets.append((target_sq, target))
        if target_sq not in before_attacks:
            new_target = True

    if len(targets) < 2 or not new_target:
        return None

    names = ", ".join(
        f"{PIECE_NAMES.get(piece.piece_type, 'piece')} on {chess.square_name(sq)}"
        for sq, piece in targets
    )
    return TacticFact(
        motif=TacticalTheme.FORK.value,
        role=TacticRole.EXECUTED.value,
        side=ctx.side,
        confidence=Confidence.PROBABLE.value,
        move_san=ctx.move_san,
        move_uci=ctx.move.uci(),
        origin_square=chess.square_name(ctx.move.from_square),
        target_square=chess.square_name(ctx.move.to_square),
        target_piece=PIECE_NAMES.get(ctx.piece.piece_type),
        targets=tuple(chess.square_name(sq) for sq, _ in targets),
        evidence=f"attacks {names}",
    )


def _alignment_facts(ctx: MotifCtx, motif: str) -> list[TacticFact]:
    facts: list[TacticFact] = []
    for slider_sq, front_sq, rear_sq in _affected_alignments(ctx):
        effective = (
            _pin_is_effective(ctx.after, ctx.enemy_color, slider_sq, front_sq, rear_sq)
            if motif == TacticalTheme.PIN.value
            else _skewer_is_effective(ctx.after, ctx.enemy_color, slider_sq, front_sq, rear_sq)
        )
        if not effective:
            continue

        rear = ctx.after.piece_at(rear_sq)
        # A pin can be exploited by capturing either side of the line; the
        # front piece is often the one that falls. A skewer always wins the
        # lower-value rear piece.
        targets = (
            (chess.square_name(front_sq), chess.square_name(rear_sq))
            if motif == TacticalTheme.PIN.value
            else (chess.square_name(rear_sq),)
        )
        facts.append(
            TacticFact(
                motif=motif,
                role=TacticRole.EXECUTED.value,
                side=ctx.side,
                confidence=Confidence.PROBABLE.value,
                move_san=ctx.move_san,
                move_uci=ctx.move.uci(),
                origin_square=chess.square_name(ctx.move.from_square),
                target_square=chess.square_name(rear_sq),
                target_piece=PIECE_NAMES.get(rear.piece_type) if rear else None,
                targets=targets,
                evidence=(
                    f"line {chess.square_name(slider_sq)}-"
                    f"{chess.square_name(front_sq)}-{chess.square_name(rear_sq)}"
                ),
            )
        )
    return facts


def _discovered_facts(ctx: MotifCtx) -> list[TacticFact]:
    facts: list[TacticFact] = []
    double_check = ctx.after.is_check() and len(ctx.after.checkers()) >= 2
    discovered_check = ctx.after.is_check() and any(
        checker != ctx.move.to_square for checker in ctx.after.checkers()
    )

    if double_check:
        facts.append(_simple_fact(ctx, TacticalTheme.DOUBLE_CHECK, "both pieces give check"))
    elif discovered_check:
        facts.append(
            _simple_fact(ctx, TacticalTheme.DISCOVERED_CHECK, "unmasks a check")
        )

    for slider_sq in ctx.sliders:
        if slider_sq == ctx.move.to_square:
            continue

        new_targets = ctx.after.attacks(slider_sq) - ctx.before.attacks(slider_sq)

        for target_sq in new_targets:
            target = ctx.after.piece_at(target_sq)
            if target is None or target.color != ctx.enemy_color:
                continue

            # A discovered attack is only forcing when the uncovered target is
            # the king or a piece that cannot escape. A merely valuable target
            # is often a secondary alignment that the forced line ignores.
            meaningful = target.piece_type == chess.KING or is_piece_doomed(
                ctx.after, target_sq, ctx.enemy_color
            )
            if not meaningful:
                continue

            facts.append(
                TacticFact(
                    motif=TacticalTheme.DISCOVERED_ATTACK.value,
                    role=TacticRole.EXECUTED.value,
                    side=ctx.side,
                    confidence=Confidence.PROBABLE.value,
                    move_san=ctx.move_san,
                    move_uci=ctx.move.uci(),
                    origin_square=chess.square_name(ctx.move.from_square),
                    target_square=chess.square_name(target_sq),
                    target_piece=PIECE_NAMES.get(target.piece_type),
                    targets=(chess.square_name(target_sq),),
                    evidence=(
                        f"{chess.square_name(slider_sq)} now attacks "
                        f"{chess.square_name(target_sq)}"
                    ),
                )
            )
            break

    return facts


def _removal_of_defender_fact(ctx: MotifCtx) -> TacticFact | None:
    if not ctx.before.is_capture(ctx.move):
        return None

    captured_sq = (
        chess.square(
            chess.square_file(ctx.move.to_square),
            chess.square_rank(ctx.move.from_square),
        )
        if ctx.before.is_en_passant(ctx.move)
        else ctx.move.to_square
    )
    captured = ctx.before.piece_at(captured_sq)
    if captured is None:
        return None

    captured_value = PIECE_VALUES.get(captured.piece_type, 0)
    for square, piece in ctx.before.piece_map().items():
        if piece.color != ctx.enemy_color or square == captured_sq:
            continue
        if piece.piece_type == chess.PAWN:
            continue  # winning a pawn by removing its defender is not a tactic
        if PIECE_VALUES.get(piece.piece_type, 0) <= captured_value:
            continue  # the target must be worth more than the defender
        if captured_sq not in ctx.before.attackers(ctx.enemy_color, square):
            continue
        if not is_piece_doomed(ctx.after, square, ctx.enemy_color):
            continue

        return TacticFact(
            motif=TacticalTheme.REMOVAL_OF_DEFENDER.value,
            role=TacticRole.EXECUTED.value,
            side=ctx.side,
            confidence=Confidence.PROBABLE.value,
            move_san=ctx.move_san,
            move_uci=ctx.move.uci(),
            origin_square=chess.square_name(ctx.move.from_square),
            target_square=chess.square_name(square),
            target_piece=PIECE_NAMES.get(piece.piece_type),
            targets=(chess.square_name(square),),
            evidence=(
                f"captured defender on {chess.square_name(captured_sq)}; "
                f"{PIECE_NAMES.get(piece.piece_type, 'piece')} on "
                f"{chess.square_name(square)} is now loose"
            ),
        )

    return None


def _trapped_piece_fact(ctx: MotifCtx) -> TacticFact | None:
    for target_sq in ctx.after.attacks(ctx.move.to_square):
        target = ctx.after.piece_at(target_sq)
        if target is None or target.color != ctx.enemy_color:
            continue
        if target.piece_type in (chess.KING, chess.PAWN):
            continue
        # A trapped piece has no legal escape at all. A piece that can move but
        # merely loses material is a different motif (hanging/doomed).
        if any(
            move.from_square == target_sq for move in ctx.after.legal_moves
        ):
            continue
        if not is_piece_doomed(ctx.after, target_sq, ctx.enemy_color):
            continue

        return TacticFact(
            motif=TacticalTheme.TRAPPED_PIECE.value,
            role=TacticRole.EXECUTED.value,
            side=ctx.side,
            confidence=Confidence.PROBABLE.value,
            move_san=ctx.move_san,
            move_uci=ctx.move.uci(),
            target_square=chess.square_name(target_sq),
            target_piece=PIECE_NAMES.get(target.piece_type),
            targets=(chess.square_name(target_sq),),
            evidence=(
                f"{PIECE_NAMES.get(target.piece_type, 'piece')} on "
                f"{chess.square_name(target_sq)} has no safe escape"
            ),
        )

    return None


def _sacrifice_fact(ctx: MotifCtx) -> TacticFact | None:
    if ctx.piece.piece_type in (chess.PAWN, chess.KING):
        return None
    # A sacrifice is only a tactic when the move is actually sound. Without a
    # sound classification the move may simply be hanging material.
    if ctx.classification not in SOUND_CLASSIFICATIONS:
        return None

    moved_value = piece_value(ctx.after, ctx.move.to_square)
    captured_value = piece_value(ctx.before, ctx.move.to_square)
    if captured_value >= moved_value:
        return None

    if ctx.before.is_pinned(ctx.color, ctx.move.from_square):
        return None
    if ctx.move.to_square in ctx.before.attackers(
        ctx.enemy_color, ctx.move.from_square
    ):
        return None
    if min_attacker_value(ctx.before, ctx.enemy_color, ctx.move.from_square) < moved_value:
        return None

    enemy_gain = static_exchange_evaluation(ctx.after, ctx.move.to_square, ctx.enemy_color)
    net_deficit = enemy_gain - captured_value * 100
    if net_deficit < MIN_SACRIFICE_DEFICIT_CP:
        return None

    return TacticFact(
        motif=TacticalTheme.SACRIFICE.value,
        role=TacticRole.EXECUTED.value,
        side=ctx.side,
        confidence=Confidence.PROBABLE.value,
        move_san=ctx.move_san,
        move_uci=ctx.move.uci(),
        origin_square=chess.square_name(ctx.move.from_square),
        target_square=chess.square_name(ctx.move.to_square),
        target_piece=PIECE_NAMES.get(ctx.piece.piece_type),
        evidence=f"offers {moved_value} points for a tactical return",
        material_gain_cp=-net_deficit,
    )


def _promotion_fact(ctx: MotifCtx) -> TacticFact | None:
    if ctx.move.promotion is None:
        return None
    return _simple_fact(
        ctx,
        TacticalTheme.PROMOTION,
        f"promotes to {PIECE_NAMES.get(ctx.move.promotion, 'piece')}",
    )


def _back_rank_mate_fact(ctx: MotifCtx) -> TacticFact | None:
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

    return _simple_fact(ctx, TacticalTheme.BACK_RANK_MATE, "king trapped on the back rank")


def _smothered_mate_fact(ctx: MotifCtx) -> TacticFact | None:
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

    return _simple_fact(ctx, TacticalTheme.SMOTHERED_MATE, "knight mates a smothered king")


def _morphy_mate_fact(ctx: MotifCtx) -> TacticFact | None:
    if not _single_checker(ctx, chess.BISHOP):
        return None
    if not ctx.after.pieces(chess.ROOK, ctx.color):
        return None
    return _simple_fact(ctx, TacticalTheme.MORPHY_MATE, "bishop mates with rook support")


def _opera_mate_fact(ctx: MotifCtx) -> TacticFact | None:
    if not _single_checker(ctx, chess.ROOK):
        return None
    checker_sq = next(iter(ctx.after.checkers()))
    if not any(
        (piece := ctx.after.piece_at(sq)) is not None and piece.piece_type == chess.BISHOP
        for sq in ctx.after.attackers(ctx.color, checker_sq)
    ):
        return None
    return _simple_fact(ctx, TacticalTheme.OPERA_MATE, "rook mates while a bishop defends it")


def _boden_mate_fact(ctx: MotifCtx) -> TacticFact | None:
    if not _single_checker(ctx, chess.BISHOP):
        return None
    if len(ctx.after.pieces(chess.BISHOP, ctx.color)) < 2:
        return None
    return _simple_fact(ctx, TacticalTheme.BODEN_MATE, "two bishops cover the mating net")


def _single_checker(ctx: MotifCtx, piece_type: chess.PieceType) -> bool:
    if not ctx.after.is_checkmate():
        return False
    checkers = ctx.after.checkers()
    if len(checkers) != 1:
        return False
    checker = ctx.after.piece_at(next(iter(checkers)))
    return checker is not None and checker.piece_type == piece_type


def _simple_fact(ctx: MotifCtx, motif: TacticalTheme, evidence: str) -> TacticFact:
    return TacticFact(
        motif=motif.value,
        role=TacticRole.EXECUTED.value,
        side=ctx.side,
        confidence=Confidence.PROBABLE.value,
        move_san=ctx.move_san,
        move_uci=ctx.move.uci(),
        origin_square=chess.square_name(ctx.move.from_square),
        target_square=chess.square_name(ctx.move.to_square),
        target_piece=PIECE_NAMES.get(ctx.piece.piece_type),
        evidence=evidence,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


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
    to_square = move.to_square
    piece = board_after.piece_at(to_square)
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
        sliders=_sliders(board_after, color),
        classification=classification,
    )

    facts: list[TacticFact] = []
    facts.extend(_executed_hanging_pieces(ctx))

    fork = _fork_fact(ctx)
    if fork is not None:
        facts.append(fork)

    facts.extend(_alignment_facts(ctx, TacticalTheme.PIN.value))
    facts.extend(_alignment_facts(ctx, TacticalTheme.SKEWER.value))
    facts.extend(_discovered_facts(ctx))

    for factory in (
        _removal_of_defender_fact,
        _trapped_piece_fact,
        _sacrifice_fact,
        _promotion_fact,
        _back_rank_mate_fact,
        _smothered_mate_fact,
        _morphy_mate_fact,
        _opera_mate_fact,
        _boden_mate_fact,
    ):
        fact = factory(ctx)
        if fact is not None:
            facts.append(fact)

    return _merge_facts(facts)


def _merge_facts(facts: list[TacticFact]) -> list[TacticFact]:
    """
    Collapse multiple alignments of the same motif on one move into a single
    fact. A queen can pin two pieces at once; that is one tactical occurrence,
    not two, and the drill-down should show it once.
    """
    merged: dict[str, TacticFact] = {}
    for fact in facts:
        existing = merged.get(fact.motif)
        if existing is None:
            merged[fact.motif] = fact
            continue

        targets = tuple(dict.fromkeys((*existing.targets, *fact.targets)))
        evidence = existing.evidence
        if fact.evidence and fact.evidence not in evidence:
            evidence = f"{evidence}; {fact.evidence}" if evidence else fact.evidence

        merged[fact.motif] = TacticFact(
            motif=existing.motif,
            role=existing.role,
            side=existing.side,
            confidence=existing.confidence,
            ply=existing.ply,
            move_san=existing.move_san,
            move_uci=existing.move_uci,
            origin_square=existing.origin_square,
            target_square=existing.target_square,
            target_piece=existing.target_piece,
            targets=targets,
            evidence=evidence,
            line=existing.line or fact.line,
            material_gain_cp=max(existing.material_gain_cp, fact.material_gain_cp),
            mate_in=existing.mate_in if existing.mate_in is not None else fact.mate_in,
        )

    return list(merged.values())


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


__all__: list[Any] = ["MotifCtx", "detect_candidates", "detect_tactical_motifs"]
