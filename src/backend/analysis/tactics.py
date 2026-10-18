"""
Tactical and game-phase analysis utilities.
Provides deterministic hanging piece detection, game phase classification
(Opening, Middlegame, Endgame), advantage conversion calculation, and
brilliancy extraction.
Zero Qt dependencies — headless and independently testable.
"""

from __future__ import annotations

from typing import Any

import chess

from src.backend.analysis.math_utils import (
    apply_accuracy_floor,
    calculate_move_accuracy,
    calculate_volatility_weights,
    harmonic_mean,
    weighted_mean,
)

PIECE_VALUES: dict[chess.PieceType, int] = {
    chess.PAWN: 1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK: 5,
    chess.QUEEN: 9,
    chess.KING: 0,
}

PIECE_NAMES: dict[chess.PieceType, str] = {
    chess.PAWN: "pawn",
    chess.KNIGHT: "knight",
    chess.BISHOP: "bishop",
    chess.ROOK: "rook",
    chess.QUEEN: "queen",
    chess.KING: "king",
}


def find_slider_ray_targets(
    board: chess.Board,
    slider_sq: chess.Square,
    color: chess.Color,
) -> list[tuple[chess.Square, chess.Piece, chess.Square, chess.Piece]]:
    """
    Finds all aligned pairs of enemy pieces (front_sq, front_piece, rear_sq, rear_piece)
    along straight rays extending outwards from `slider_sq`.
    Guarantees physical order along each ray outwards from `slider_sq`.
    """
    enemy_color = not color
    results: list[tuple[chess.Square, chess.Piece, chess.Square, chess.Piece]] = []
    slider_piece = board.piece_at(slider_sq)
    if not slider_piece:
        return results

    directions: list[tuple[int, int]] = []
    if slider_piece.piece_type in (chess.BISHOP, chess.QUEEN):
        directions.extend([(1, 1), (1, -1), (-1, 1), (-1, -1)])
    if slider_piece.piece_type in (chess.ROOK, chess.QUEEN):
        directions.extend([(1, 0), (-1, 0), (0, 1), (0, -1)])

    s_f = chess.square_file(slider_sq)
    s_r = chess.square_rank(slider_sq)

    for df, dr in directions:
        f = s_f + df
        r = s_r + dr
        front_sq: chess.Square | None = None
        front_piece: chess.Piece | None = None

        while 0 <= f < 8 and 0 <= r < 8:
            sq = chess.square(f, r)
            p = board.piece_at(sq)
            if p is not None:
                if front_sq is None:
                    if p.color == enemy_color:
                        front_sq = sq
                        front_piece = p
                    else:
                        break  # Friendly piece blocks ray immediately
                else:
                    if p.color == enemy_color and front_piece is not None:
                        results.append((front_sq, front_piece, sq, p))
                    break  # Second piece blocks further vision on this ray
            f += df
            r += dr

    return results


def is_on_segment(a: chess.Square, b: chess.Square, c: chess.Square) -> bool:
    """Returns True if square `c` lies strictly between `a` and `b` on a straight ray."""
    af, ar = chess.square_file(a), chess.square_rank(a)
    bf, br = chess.square_file(b), chess.square_rank(b)
    cf, cr = chess.square_file(c), chess.square_rank(c)
    df, dr = bf - af, br - ar
    if df != 0 and dr != 0 and abs(df) != abs(dr):
        return False
    step_f = 0 if df == 0 else (1 if df > 0 else -1)
    step_r = 0 if dr == 0 else (1 if dr > 0 else -1)
    f, r = af + step_f, ar + step_r
    while (f, r) != (bf, br):
        if (f, r) == (cf, cr):
            return True
        f += step_f
        r += step_r
    return False


def static_exchange_evaluation(
    board: chess.Board,
    square: chess.Square,
    attacking_color: chess.Color | None = None,
) -> int:
    """
    Computes Static Exchange Evaluation (SEE) score on `square` in centipawns.
    Positive value indicates `attacking_color` gains material on that square.
    """
    target_piece = board.piece_at(square)
    if not target_piece:
        return 0

    if attacking_color is None:
        attacking_color = board.turn

    color = attacking_color
    enemy_color = not color

    attackers = board.attackers(color, square)
    if not attackers:
        return 0

    best_attacker = None
    min_val = 99999
    enemy_attacks = board.attackers(enemy_color, square)
    for sq in attackers:
        if board.is_pinned(color, sq) and square not in board.pin(color, sq):
            continue
        p = board.piece_at(sq)
        if not p:
            continue
        # King cannot legally capture on a defended square
        if p.piece_type == chess.KING and enemy_attacks:
            continue
        val = PIECE_VALUES.get(p.piece_type, 0)
        if val < min_val:
            min_val = val
            best_attacker = sq

    if best_attacker is None:
        return 0

    captured_val = PIECE_VALUES.get(target_piece.piece_type, 0) * 100

    b_copy = board.copy(stack=False)
    attacker_p = board.piece_at(best_attacker)
    promotion = None
    if attacker_p and attacker_p.piece_type == chess.PAWN and chess.square_rank(square) in (0, 7):
        promotion = chess.QUEEN
        captured_val += 800  # Promotion adds net Queen value over pawn

    b_copy.push(chess.Move(best_attacker, square, promotion=promotion))

    recapture_gain = static_exchange_evaluation(b_copy, square, enemy_color)
    return max(0, captured_val - recapture_gain)


def is_piece_hanging(
    board: chess.Board,
    square: chess.Square,
    color: chess.Color,
    last_move: chess.Move | None = None,
    board_before: chess.Board | None = None,
) -> bool:
    """
    Determines if the piece on `square` belonging to `color` is hanging on `board`.
    Strictly follows SPEC.md:
    1. Not a King.
    2. Attacked by >= 1 enemy piece.
    3. Undefended, attacked by lesser value, or enemy SEE > 0.
    4. Excludes equal or winning recaptures/trades on `last_move` (including en passant).
    """
    piece = board.piece_at(square)
    if not piece or piece.color != color or piece.piece_type == chess.KING:
        return False

    enemy_color = not color
    enemy_attackers = board.attackers(enemy_color, square)
    if not enemy_attackers:
        return False

    piece_val = PIECE_VALUES.get(piece.piece_type, 0)

    # Filter legal friendly defenders (excluding pinned defenders)
    raw_defenders = board.attackers(color, square)
    friendly_defenders = [
        sq
        for sq in raw_defenders
        if not (board.is_pinned(color, sq) and square not in board.pin(color, sq))
    ]

    attacker_vals = [
        PIECE_VALUES.get(board.piece_at(sq).piece_type, 0)
        for sq in enemy_attackers
        if board.piece_at(sq)
    ]
    min_attacker_val = min(attacker_vals) if attacker_vals else 99

    is_undefended = len(friendly_defenders) == 0
    attacked_by_lesser = min_attacker_val < piece_val
    enemy_see_gain = static_exchange_evaluation(board, square, enemy_color)
    is_underdefended = enemy_see_gain > 0

    if not (is_undefended or attacked_by_lesser or is_underdefended):
        return False

    # RECAPTURE / TRADE EXCLUSION (Resolves Queen/Piece exchange bug):
    if last_move and board_before is not None and last_move.to_square == square:
        captured = board_before.piece_at(square)
        if captured is None and board_before.is_en_passant(last_move):
            ep_sq = chess.square(
                chess.square_file(last_move.to_square),
                chess.square_rank(last_move.from_square),
            )
            captured = board_before.piece_at(ep_sq)
        if captured and PIECE_VALUES.get(captured.piece_type, 0) >= piece_val:
            return False

    return True


def get_hanging_pieces(
    board: chess.Board,
    color: chess.Color,
    last_move: chess.Move | None = None,
    board_before: chess.Board | None = None,
) -> list[dict]:
    """
    Finds all pieces belonging to `color` that are hanging on `board`.
    """
    hanging = []
    enemy_color = not color

    for square, piece in board.piece_map().items():
        if piece.color == color and is_piece_hanging(board, square, color, last_move, board_before):
            piece_val = PIECE_VALUES.get(piece.piece_type, 0)
            enemy_attackers = board.attackers(enemy_color, square)
            attacker_vals = [
                PIECE_VALUES.get(board.piece_at(sq).piece_type, 0)
                for sq in enemy_attackers
                if board.piece_at(sq)
            ]
            min_attacker = min(attacker_vals) if attacker_vals else 99
            raw_defenders = board.attackers(color, square)
            friendly_defenders = [
                sq
                for sq in raw_defenders
                if not (board.is_pinned(color, sq) and square not in board.pin(color, sq))
            ]

            hanging.append(
                {
                    "square": chess.square_name(square),
                    "square_index": square,
                    "piece_type": piece.piece_type,
                    "piece_name": PIECE_NAMES.get(piece.piece_type, "piece"),
                    "piece_val": piece_val,
                    "is_undefended": len(friendly_defenders) == 0,
                    "attacked_by_lesser": min_attacker < piece_val,
                    "is_outnumbered": len(enemy_attackers) > len(friendly_defenders),
                }
            )

    return hanging


def detect_tactical_motifs(
    board_before: chess.Board,
    board_after: chess.Board,
    move_obj: chess.Move,
    color: chess.Color,
    classification: str = "",
) -> list[str]:
    """
    Detects tactical motifs executed by a move:
    - 'fork': Piece attacks 2+ tactical targets (King, undefended, higher value, or SEE > 0).
    - 'pin': Establishes or exploits an absolute or relative pin.
    - 'skewer': Attacks higher-value piece in front with target behind on same ray.
    - 'discovered_attack': Removing a piece unmasks a sliding attack creating a real threat.
    - 'sacrifice': Sound piece sacrifice or material investment.
    - 'back_rank': Delivers or threatens back-rank mate against a trapped King.
    """
    motifs: list[str] = []
    enemy_color = not color
    to_sq = move_obj.to_square
    from_sq = move_obj.from_square
    piece = board_after.piece_at(to_sq)
    if not piece:
        return motifs

    piece_val = PIECE_VALUES.get(piece.piece_type, 0)
    enemy_king_sq = board_after.king(enemy_color)

    # 1. Sacrifice
    # A true sacrifice requires voluntarily giving up material (net >= 200 cp) for tactical/positional gain.
    # Exclusions:
    # - Equal trades (QxQ, RxR, BxB, NxN, etc.) are fair exchanges, NEVER sacrifices.
    # - Defended pieces where opponent cannot capture profitably (enemy SEE gain < 200) are NEVER sacrifices.
    # - Pawn moves / gambits (net deficit 100 cp) are not piece sacrifices.
    # - Routine "Great" or "Best" moves without actual material deficit are NEVER sacrifices.
    if piece.piece_type not in (chess.PAWN, chess.KING):
        captured_piece = board_before.piece_at(to_sq)
        captured_val = PIECE_VALUES.get(captured_piece.piece_type, 0) if captured_piece else 0
        if captured_val < piece_val:
            is_pinned_before = board_before.is_pinned(color, from_sq)
            attacked_by_target = to_sq in board_before.attackers(enemy_color, from_sq)
            under_attack_by_lesser = False
            for att_sq in board_before.attackers(enemy_color, from_sq):
                att_p = board_before.piece_at(att_sq)
                if att_p and PIECE_VALUES.get(att_p.piece_type, 0) < piece_val:
                    under_attack_by_lesser = True
                    break

            if not (is_pinned_before or attacked_by_target or under_attack_by_lesser):
                enemy_gain = static_exchange_evaluation(board_after, to_sq, enemy_color)
                net_deficit = enemy_gain - (captured_val * 100)
                if net_deficit >= 200:
                    motifs.append("sacrifice")

    # 2. Fork / Double Attack
    if piece.piece_type != chess.KING:
        attacks = board_after.attacks(to_sq)
        valuable_targets = 0
        has_check = enemy_king_sq is not None and enemy_king_sq in attacks
        if has_check:
            valuable_targets += 1

        for target_sq in attacks:
            if target_sq == enemy_king_sq:
                continue
            target_p = board_after.piece_at(target_sq)
            if target_p and target_p.color == enemy_color:
                # Fork targets must strictly be pieces (Knight, Bishop, Rook, Queen), NOT pawns!
                # Attacking a Queen/Rook and a pawn (e.g. Nd5 attacking Qf6 and Pc7) is NOT a fork.
                if target_p.piece_type == chess.PAWN:
                    continue

                target_val = PIECE_VALUES.get(target_p.piece_type, 0)
                defenders = board_after.attackers(enemy_color, target_sq)
                if (
                    len(defenders) == 0
                    or target_val > piece_val
                    or static_exchange_evaluation(board_after, target_sq, color) > 0
                ):
                    valuable_targets += 1

        if valuable_targets >= 2:
            # Safety check: A move is NOT a fork if the forking piece itself can be immediately
            # captured without compensation (e.g. undefended rook or capturable pawn).
            can_be_captured = any(m.to_square == to_sq for m in board_after.legal_moves)
            if can_be_captured:
                forker_defenders = board_after.attackers(color, to_sq)
                # If undefended, or opponent captures at a profit (SEE > 0):
                if (
                    len(forker_defenders) == 0
                    or static_exchange_evaluation(board_after, to_sq, enemy_color) > 0
                ):
                    valuable_targets = 0

        if valuable_targets >= 2:
            motifs.append("fork")

    # 3. Pin: Absolute or Relative (Created by slider move or unmasking)
    pin_found = False
    friendly_sliders = (
        board_after.pieces(chess.BISHOP, color)
        | board_after.pieces(chess.ROOK, color)
        | board_after.pieces(chess.QUEEN, color)
    )
    for s_sq in friendly_sliders:
        is_moved = s_sq == to_sq
        alignments = find_slider_ray_targets(board_after, s_sq, color)
        slider_p = board_after.piece_at(s_sq)
        slider_type = slider_p.piece_type if slider_p else None

        for front_sq, front_p, rear_sq, rear_p in alignments:
            if not is_moved and not is_on_segment(s_sq, front_sq, from_sq):
                continue

            # 1. Absolute Pin: Rear piece is enemy King.
            # Front piece cannot legally move off the pin ray.
            if rear_p.piece_type == chess.KING:
                pin_found = True
                break

            # 2. Relative Pin: Rear piece is NOT King.
            # Tactical requirements:
            # - Front piece CANNOT be a pawn (pawns are never relatively pinned to pieces).
            # - Rear piece CANNOT be a pawn or minor piece (cannot pin to a pawn/knight/bishop).
            # - Valid relative pin targets:
            #   * Rear piece is Queen (val 9), front piece is Minor (val 3) or Rook (val 5).
            #   * Rear piece is Rook (val 5), front piece is Minor (val 3), and slider is Bishop (exchange win) or Rook is undefended.
            if front_p.piece_type != chess.PAWN:
                if rear_p.piece_type == chess.QUEEN:
                    pin_found = True
                    break
                elif rear_p.piece_type == chess.ROOK and front_p.piece_type in (
                    chess.KNIGHT,
                    chess.BISHOP,
                ):
                    rear_defenders = board_after.attackers(enemy_color, rear_sq)
                    if slider_type == chess.BISHOP or len(rear_defenders) == 0:
                        pin_found = True
                        break

        if pin_found:
            break

    if pin_found:
        motifs.append("pin")

    # 4. Discovered Attack / Discovered Check
    is_discovered = False
    if board_after.is_check():
        checkers = board_after.checkers()
        if to_sq not in checkers and len(checkers) > 0:
            is_discovered = True

    if not is_discovered:
        for s_sq in friendly_sliders:
            if s_sq != to_sq and from_sq in board_after.attacks(s_sq):
                new_targets = board_after.attacks(s_sq) - board_before.attacks(s_sq)
                slider_piece = board_after.piece_at(s_sq)
                slider_val = PIECE_VALUES.get(slider_piece.piece_type, 0) if slider_piece else 0

                for nt in new_targets:
                    nt_piece = board_after.piece_at(nt)
                    if not nt_piece or nt_piece.color != enemy_color:
                        continue

                    target_val = PIECE_VALUES.get(nt_piece.piece_type, 0)
                    defenders = board_after.attackers(enemy_color, nt)

                    # Real tactical threat check:
                    # 1. Undefended
                    # 2. Target has strictly higher value than slider (e.g. Rook attacks Queen)
                    # 3. Under-defended: SEE > 0 for this slider
                    if (
                        len(defenders) == 0
                        or target_val > slider_val
                        or (
                            nt_piece.piece_type != chess.PAWN
                            and static_exchange_evaluation(board_after, nt, color) > 0
                        )
                    ):
                        is_discovered = True
                        break
            if is_discovered:
                break

    if is_discovered:
        motifs.append("discovered_attack")

    # 5. Skewer
    skewer_found = False
    for s_sq in friendly_sliders:
        is_moved = s_sq == to_sq
        alignments = find_slider_ray_targets(board_after, s_sq, color)
        s_piece = board_after.piece_at(s_sq)
        s_val = PIECE_VALUES.get(s_piece.piece_type, 0) if s_piece else 0

        for front_sq, front_p, _rear_sq, rear_p in alignments:
            if not is_moved and not is_on_segment(s_sq, front_sq, from_sq):
                continue

            # In a true tactical skewer:
            # 1. The rear piece must be a non-pawn piece (Queen, Rook, Minor piece).
            #    A piece is never skewered to win a pawn.
            if rear_p.piece_type == chess.PAWN:
                continue

            front_val = (
                100 if front_p.piece_type == chess.KING else PIECE_VALUES.get(front_p.piece_type, 0)
            )
            rear_val = PIECE_VALUES.get(rear_p.piece_type, 0)

            # 2. Front piece must be strictly more valuable than rear piece.
            if front_val <= rear_val:
                continue

            # 3. Front piece must be genuinely compelled to move:
            # - King in check: legally compelled to move, exposing rear piece.
            # - Queen: attacked by lesser slider (Rook or Bishop) or completely undefended.
            # - Rook: attacked by lesser slider (Bishop) or completely undefended.
            front_defenders = board_after.attackers(enemy_color, front_sq)
            is_compelled = False

            if front_p.piece_type == chess.KING:
                is_compelled = True
            elif front_p.piece_type == chess.QUEEN:
                if s_val < 9 or len(front_defenders) == 0:
                    is_compelled = True
            elif front_p.piece_type == chess.ROOK:
                if s_val < 5 or len(front_defenders) == 0:
                    is_compelled = True
            elif len(front_defenders) == 0:
                is_compelled = True

            if is_compelled:
                skewer_found = True
                break

        if skewer_found:
            break

    if skewer_found:
        motifs.append("skewer")

    # 6. Back Rank Weakness / Infiltration
    back_rank = 7 if enemy_color == chess.BLACK else 0
    if enemy_king_sq is not None and chess.square_rank(enemy_king_sq) == back_rank:
        adj_rank = 6 if enemy_color == chess.BLACK else 1
        king_file = chess.square_file(enemy_king_sq)
        escape_sqs = [
            chess.square(f, adj_rank) for f in range(max(0, king_file - 1), min(8, king_file + 2))
        ]
        has_luft = False
        for esq in escape_sqs:
            occ = board_after.piece_at(esq)
            if occ is None and esq not in board_after.attacks(color):
                has_luft = True
                break

        if not has_luft:
            if board_after.is_checkmate() and any(
                chess.square_rank(c) == back_rank for c in board_after.checkers()
            ):
                motifs.append("back_rank")
            elif (
                piece.piece_type in (chess.ROOK, chess.QUEEN)
                and chess.square_rank(to_sq) == back_rank
                and ((enemy_king_sq in board_after.attacks(to_sq)) or board_after.is_check())
            ):
                # When not checkmate, ensure it is a real back-rank threat:
                # It is NOT a back-rank threat if the enemy can simply capture it on to_sq:
                # - If undefended (e.g. Rd1+ where enemy rook can simply take it)
                # - If it was a capture (e.g. "rook takes rook") and can be recaptured
                can_be_captured = any(m.to_square == to_sq for m in board_after.legal_moves)
                if can_be_captured:
                    defenders = board_after.attackers(color, to_sq)
                    is_undefended = len(defenders) == 0
                    is_recapturable_trade = board_before.is_capture(move_obj)
                    if not (is_undefended or is_recapturable_trade):
                        enemy_see = static_exchange_evaluation(board_after, to_sq, enemy_color)
                        if enemy_see <= 0:
                            motifs.append("back_rank")
                else:
                    motifs.append("back_rank")

    return motifs


def classify_game_phase(
    board: chess.Board,
    ply: int,
    is_book_move: bool = False,
) -> str:
    """
    Classifies a position into 'opening', 'middlegame', or 'endgame'.

    Rules:
    - Opening: In opening book OR ply <= 16 with queens present and substantial material.
    - Endgame:
        * No queens on board, OR
        * Total non-pawn piece material for both sides <= 20 points (e.g. R+N vs R+B), OR
        * Either side has non-pawn piece material <= 9 points.
    - Middlegame: All positions between Opening and Endgame.
    """
    if is_book_move:
        return "opening"

    # Material count excluding pawns and kings
    white_non_pawn = sum(
        PIECE_VALUES[p.piece_type]
        for p in board.piece_map().values()
        if p.color == chess.WHITE and p.piece_type not in (chess.KING, chess.PAWN)
    )
    black_non_pawn = sum(
        PIECE_VALUES[p.piece_type]
        for p in board.piece_map().values()
        if p.color == chess.BLACK and p.piece_type not in (chess.KING, chess.PAWN)
    )
    total_non_pawn = white_non_pawn + black_non_pawn

    has_white_queen = bool(board.pieces(chess.QUEEN, chess.WHITE))
    has_black_queen = bool(board.pieces(chess.QUEEN, chess.BLACK))

    # Endgame check:
    # 1. Neither side has a queen and total non-pawn material is moderately low
    # 2. Total non-pawn material is <= 20 points
    # 3. Either side has <= 6 points of non-pawn pieces
    if (
        (not has_white_queen and not has_black_queen and total_non_pawn <= 26)
        or total_non_pawn <= 18
        or white_non_pawn <= 6
        or black_non_pawn <= 6
    ):
        return "endgame"

    # Opening check:
    if ply <= 16 and white_non_pawn >= 20 and black_non_pawn >= 20:
        return "opening"

    return "middlegame"


def analyze_game_tactics(
    moves_data: list[dict],
    user_color: str,
    result: str = "*",
    speed_category: str = "Blitz",
) -> dict:
    """
    Full comprehensive tactical, phase, and advantage analysis of a game's moves.
    Operates on the serialized move dictionaries from `moves_json`.

    Returns a rich dict containing:
    - phase_accuracies: {opening: float, middlegame: float, endgame: float}
    - phase_blunders: {opening: int, middlegame: int, endgame: int}
    - hanging_metrics: {
        total_hung: int,
        by_piece: {pawn: int, knight: int, bishop: int, rook: int, queen: int},
        hanging_blunders: int,
        opponent_hanging_captured: int,
        opponent_hanging_missed: int,
      }
    - advantage_metrics: {
        had_winning_advantage: bool,
        converted_advantage: bool,
        choked_advantage: bool,
        had_losing_position: bool,
        comeback_drawn_or_won: bool,
        peak_eval_cp: int,
        lowest_eval_cp: int,
      }
    - brilliancies: list of dicts for user moves classified as 'Brilliant' or 'Great'
    - book_exit_ply: int | None
    - clock_metrics: dict of time-spent and time-trouble indicators
    """
    is_user_white = user_color.lower() == "white"
    target_color = chess.WHITE if is_user_white else chess.BLACK

    # Phase tracking
    phase_accuracies: dict[str, list[float]] = {"opening": [], "middlegame": [], "endgame": []}
    phase_win_percents: dict[str, list[float]] = {"opening": [], "middlegame": [], "endgame": []}
    phase_blunders: dict[str, int] = {"opening": 0, "middlegame": 0, "endgame": 0}

    # Hanging tracking
    pieces_hung_by_type: dict[str, int] = {
        "pawn": 0,
        "knight": 0,
        "bishop": 0,
        "rook": 0,
        "queen": 0,
    }
    opp_pieces_captured_by_type: dict[str, int] = {
        "pawn": 0,
        "knight": 0,
        "bishop": 0,
        "rook": 0,
        "queen": 0,
    }
    total_hung = 0
    hanging_blunders = 0
    opp_hanging_captured = 0
    opp_hanging_missed = 0

    # Tactical themes tracking
    tactical_theme_counts: dict[str, int] = {
        "fork": 0,
        "pin": 0,
        "skewer": 0,
        "discovered_attack": 0,
        "sacrifice": 0,
        "back_rank": 0,
    }

    # Advantage tracking
    peak_eval = 0
    lowest_eval = 0
    had_winning_advantage = False  # >= +300 cp from user perspective
    had_losing_position = False  # <= -300 cp from user perspective

    # Time trouble threshold
    sc_lower = (speed_category or "").lower()
    if "ultrabullet" in sc_lower or "bullet" in sc_lower:
        trouble_threshold = 15.0
    elif "blitz" in sc_lower:
        trouble_threshold = 30.0
    elif "rapid" in sc_lower:
        trouble_threshold = 60.0
    elif "classical" in sc_lower:
        trouble_threshold = 120.0
    else:
        trouble_threshold = 30.0

    # Clock and time management tracking
    total_timed_moves = 0
    total_time_spent = 0.0
    phase_time_spent = {"opening": 0.0, "middlegame": 0.0, "endgame": 0.0}
    phase_timed_moves = {"opening": 0, "middlegame": 0, "endgame": 0}
    quality_time_spent = {"best": 0.0, "blunder": 0.0, "other": 0.0}
    quality_timed_moves = {"best": 0, "blunder": 0, "other": 0}
    normal_moves = 0
    normal_blunders = 0
    trouble_moves = 0
    trouble_blunders = 0

    # Brilliancies list
    brilliancies = []
    book_exit_ply = None

    # Occurrence details for drill-down exploration
    hung_pieces_details: list[dict[str, Any]] = []
    opp_captured_details: list[dict[str, Any]] = []
    tactical_motifs_details: list[dict[str, Any]] = []
    blunders_details: list[dict[str, Any]] = []

    lead_collapse_move: dict[str, Any] | None = None
    max_lead_drop: float = 0.0
    comeback_turn_move: dict[str, Any] | None = None
    max_comeback_gain: float = 0.0

    for m in moves_data:
        ply = m.get("ply", 0)
        san = m.get("san", "")
        uci = m.get("uci", "")
        fen_before = m.get("fen_before", "")
        classification = m.get("classification", "")
        is_book = bool(m.get("is_book_move", False))

        if not is_book and book_exit_ply is None:
            book_exit_ply = ply

        # Parse board
        try:
            board_before = chess.Board(fen_before)
        except Exception:
            board_before = chess.Board()

        # Is this move made by the user?
        # board_before.turn is authoritative for side-to-move.
        # Fall back to ply % 2 == 0 (0-indexed ply in python-chess) if fen_before is empty.
        is_white_turn = board_before.turn == chess.WHITE if fen_before else (ply % 2 == 0)
        is_user_move = is_white_turn == is_user_white

        phase = classify_game_phase(board_before, ply, is_book)

        # Eval perspective normalization:
        # MoveAnalysis eval_before_cp is White-perspective.
        eval_before_white = m.get("eval_before_cp") or 0
        eval_user_cp = eval_before_white if is_user_white else -eval_before_white

        if eval_user_cp > peak_eval:
            peak_eval = eval_user_cp
        if eval_user_cp < lowest_eval:
            lowest_eval = eval_user_cp

        if eval_user_cp >= 300:
            had_winning_advantage = True
        if eval_user_cp <= -300:
            had_losing_position = True

        if is_user_move:
            # 1. Accuracy & Phase
            wp_before = m.get("win_chance_before", 0.5)
            wp_after = m.get("win_chance_after", 0.5)
            # In MoveAnalysis, win chances are White-perspective. Convert to user perspective:
            player_wp_before = wp_before if is_user_white else (1.0 - wp_before)
            player_wp_after = wp_after if is_user_white else (1.0 - wp_after)

            eval_after_mate = m.get("eval_after_mate")
            is_checkmate_move = san.endswith("#") if san else False
            is_mating_move = eval_after_mate is not None and (
                (is_user_white and eval_after_mate > 0)
                or (not is_user_white and eval_after_mate < 0)
            )

            if is_book or is_checkmate_move or is_mating_move:
                acc = 100.0
            else:
                acc = calculate_move_accuracy(player_wp_before, player_wp_after)

            acc = apply_accuracy_floor(acc)
            phase_accuracies[phase].append(acc)
            phase_win_percents[phase].append(player_wp_before)

            eval_after_raw = m.get("eval_after_cp")
            eval_after_user = (
                (eval_after_raw if is_user_white else -eval_after_raw)
                if eval_after_raw is not None
                else None
            )
            eval_diff = (
                (eval_user_cp - eval_after_user)
                if (eval_user_cp is not None and eval_after_user is not None)
                else None
            )

            # 2. Hanging piece & tactical pattern detection after user move
            try:
                move_obj = chess.Move.from_uci(uci) if uci else board_before.parse_san(san)
                board_after = board_before.copy()
                board_after.push(move_obj)
                fen_after = board_after.fen()

                wp_drop = player_wp_before - player_wp_after

                if classification == "Blunder":
                    phase_blunders[phase] += 1
                    blunders_details.append(
                        {
                            "ply": ply,
                            "move_number": m.get("move_number", (ply + 1) // 2),
                            "san": san,
                            "uci": uci,
                            "fen_before": fen_before,
                            "fen_after": fen_after,
                            "classification": classification,
                            "eval_before_cp": eval_user_cp,
                            "eval_after_cp": eval_after_user,
                            "eval_drop": eval_diff,
                            "wp_drop": round(wp_drop, 3),
                        }
                    )

                # Robust filter: Do NOT count sacrifices, brilliant moves, or engine-best advantageous moves as hangs!
                # If a move is Brilliant, Great, Best, or Excellent, leaving a piece attacked is intentional,
                # advantageous (sacrifices, tactics, traps), and must never be recorded as an accidental hung piece.
                is_advantageous_or_sound = (
                    is_book
                    or classification in ("Brilliant", "Great", "Best", "Excellent")
                    or (classification == "Good" and wp_drop < 0.05)
                    or (wp_drop < 0.03 and player_wp_after >= 0.50)
                )

                if not is_advantageous_or_sound:
                    # Did user leave a piece hanging on board_after?
                    user_hanging = get_hanging_pieces(
                        board_after, target_color, last_move=move_obj, board_before=board_before
                    )
                    # Compare to hanging pieces before move to see if newly created or persisted
                    hanging_before = get_hanging_pieces(board_before, target_color)
                    hung_sqs_before = {h["square"] for h in hanging_before}

                    newly_hung = [
                        h
                        for h in user_hanging
                        if h["square"] not in hung_sqs_before
                        or h["square"] == chess.square_name(move_obj.to_square)
                    ]
                    if newly_hung:
                        total_hung += len(newly_hung)
                        for h in newly_hung:
                            p_name = h["piece_name"]
                            if p_name in pieces_hung_by_type:
                                pieces_hung_by_type[p_name] += 1

                            hung_pieces_details.append(
                                {
                                    "piece_name": p_name,
                                    "square": h["square"],
                                    "ply": ply,
                                    "move_number": m.get("move_number", (ply + 1) // 2),
                                    "san": san,
                                    "uci": uci,
                                    "fen_before": fen_before,
                                    "fen_after": fen_after,
                                    "classification": classification,
                                    "eval_before_cp": eval_user_cp,
                                    "eval_after_cp": eval_after_user,
                                    "eval_drop": eval_diff,
                                    "wp_drop": round(wp_drop, 3),
                                }
                            )

                        if classification in ("Blunder", "Mistake"):
                            hanging_blunders += 1

                # 3. Did user capture an opponent hanging piece that existed on board_before?
                opp_color = not target_color
                opp_hanging_before = get_hanging_pieces(board_before, opp_color)
                opp_hanging_sqs = {h["square"]: h for h in opp_hanging_before}

                to_sq_name = chess.square_name(move_obj.to_square)
                if to_sq_name in opp_hanging_sqs:
                    # Only count as a successful capture if user didn't blunder into a trap/poisoned piece
                    if classification not in ("Blunder", "Mistake") and wp_drop < 0.08:
                        opp_hanging_captured += 1
                        captured_h = opp_hanging_sqs[to_sq_name]
                        p_name = captured_h["piece_name"]
                        if p_name in opp_pieces_captured_by_type:
                            opp_pieces_captured_by_type[p_name] += 1

                        opp_captured_details.append(
                            {
                                "piece_name": p_name,
                                "square": to_sq_name,
                                "ply": ply,
                                "move_number": m.get("move_number", (ply + 1) // 2),
                                "san": san,
                                "uci": uci,
                                "fen_before": fen_before,
                                "fen_after": fen_after,
                                "classification": classification,
                                "eval_before_cp": eval_user_cp,
                            }
                        )
                elif opp_hanging_before and classification in (
                    "Mistake",
                    "Blunder",
                    "Miss",
                ):
                    opp_hanging_missed += 1

                # 4. Tactical themes detection (sound moves only)
                if classification not in ("Blunder", "Mistake") and wp_drop < 0.08:
                    found_motifs = detect_tactical_motifs(
                        board_before, board_after, move_obj, target_color, classification
                    )
                    for motif in found_motifs:
                        if motif in tactical_theme_counts:
                            tactical_theme_counts[motif] += 1
                            tactical_motifs_details.append(
                                {
                                    "motif": motif,
                                    "ply": ply,
                                    "move_number": m.get("move_number", (ply + 1) // 2),
                                    "san": san,
                                    "uci": uci,
                                    "fen_before": fen_before,
                                    "fen_after": fen_after,
                                    "classification": classification,
                                    "eval_before_cp": eval_user_cp,
                                    "eval_after_cp": eval_after_user,
                                    "eval_drop": eval_diff,
                                    "wp_drop": round(wp_drop, 3),
                                }
                            )

                # 5. Advantage turning point tracking
                if had_winning_advantage and wp_drop > max_lead_drop and wp_drop > 0.05:
                    max_lead_drop = wp_drop
                    lead_collapse_move = {
                        "ply": ply,
                        "move_number": m.get("move_number", (ply + 1) // 2),
                        "san": san,
                        "uci": uci,
                        "fen_before": fen_before,
                        "fen_after": fen_after,
                        "classification": classification,
                        "eval_before_cp": eval_user_cp,
                        "eval_after_cp": eval_after_user,
                        "eval_drop": eval_diff,
                        "wp_drop": round(wp_drop, 3),
                    }

                wp_gain = player_wp_after - player_wp_before
                if had_losing_position and wp_gain > max_comeback_gain and wp_gain > 0.05:
                    max_comeback_gain = wp_gain
                    comeback_turn_move = {
                        "ply": ply,
                        "move_number": m.get("move_number", (ply + 1) // 2),
                        "san": san,
                        "uci": uci,
                        "fen_before": fen_before,
                        "fen_after": fen_after,
                        "classification": classification,
                        "eval_before_cp": eval_user_cp,
                        "eval_after_cp": eval_after_user,
                        "eval_gain": -eval_diff if eval_diff is not None else None,
                        "wp_gain": round(wp_gain, 3),
                    }

            except Exception:
                pass

            # 4. Brilliancies / Great moves
            if classification in ("Brilliant", "Great"):
                brilliancies.append(
                    {
                        "ply": ply,
                        "move_number": m.get("move_number", (ply + 1) // 2),
                        "san": san,
                        "uci": uci,
                        "fen_before": fen_before,
                        "classification": classification,
                        "explanation": m.get("explanation", ""),
                        "opening_name": m.get("opening_name", ""),
                        "time_spent": m.get("time_spent"),
                    }
                )

            # 5. Clock & Thinking Time Metrics
            t_spent = m.get("time_spent")
            t_left = m.get("time_left")

            if t_spent is not None and 0.0 <= t_spent < 7200.0:
                total_timed_moves += 1
                total_time_spent += t_spent
                phase_time_spent[phase] += t_spent
                phase_timed_moves[phase] += 1

                if classification in ("Brilliant", "Great", "Best"):
                    quality_time_spent["best"] += t_spent
                    quality_timed_moves["best"] += 1
                elif classification in ("Blunder", "Mistake"):
                    quality_time_spent["blunder"] += t_spent
                    quality_timed_moves["blunder"] += 1
                else:
                    quality_time_spent["other"] += t_spent
                    quality_timed_moves["other"] += 1

            if t_left is not None and t_left >= 0.0:
                if t_left <= trouble_threshold:
                    trouble_moves += 1
                    if classification in ("Blunder", "Mistake"):
                        trouble_blunders += 1
                else:
                    normal_moves += 1
                    if classification in ("Blunder", "Mistake"):
                        normal_blunders += 1

    # Phase accuracy calculation using harmonic + volatility-weighted mean matching analyzer.py
    def compute_phase_acc(accs: list[float], wps: list[float]) -> float | None:
        if not accs:
            return None
        if len(accs) == 1:
            return accs[0]
        window_size = max(2, min(8, len(accs) // 10))
        weights = calculate_volatility_weights(wps, window_size)
        wm = weighted_mean(accs, weights)
        hm = harmonic_mean(accs)
        return (wm + hm) / 2

    # Conversion logic
    user_won = (result == "1-0" and is_user_white) or (result == "0-1" and not is_user_white)
    is_draw = result in ("1/2-1/2", "Draw")
    user_lost = not user_won and not is_draw

    converted_advantage = had_winning_advantage and user_won
    choked_advantage = had_winning_advantage and not user_won
    thrown_losses = had_winning_advantage and user_lost
    squandered_draws = had_winning_advantage and is_draw

    comeback_drawn_or_won = had_losing_position and (user_won or is_draw)
    comeback_wins = had_losing_position and user_won
    comeback_draws = had_losing_position and is_draw
    lost_deficit = had_losing_position and user_lost

    return {
        "phase_accuracies": {
            "opening": compute_phase_acc(
                phase_accuracies["opening"], phase_win_percents["opening"]
            ),
            "middlegame": compute_phase_acc(
                phase_accuracies["middlegame"], phase_win_percents["middlegame"]
            ),
            "endgame": compute_phase_acc(
                phase_accuracies["endgame"], phase_win_percents["endgame"]
            ),
        },
        "phase_move_counts": {
            "opening": len(phase_accuracies["opening"]),
            "middlegame": len(phase_accuracies["middlegame"]),
            "endgame": len(phase_accuracies["endgame"]),
        },
        "phase_blunders": phase_blunders,
        "hanging_metrics": {
            "total_hung": total_hung,
            "by_piece": pieces_hung_by_type,
            "hanging_blunders": hanging_blunders,
            "opponent_hanging_captured": opp_hanging_captured,
            "opponent_hanging_missed": opp_hanging_missed,
            "captured_by_piece": opp_pieces_captured_by_type,
        },
        "advantage_metrics": {
            "had_winning_advantage": had_winning_advantage,
            "converted_advantage": converted_advantage,
            "choked_advantage": choked_advantage,
            "thrown_losses": thrown_losses,
            "squandered_draws": squandered_draws,
            "had_losing_position": had_losing_position,
            "comeback_drawn_or_won": comeback_drawn_or_won,
            "comeback_wins": comeback_wins,
            "comeback_draws": comeback_draws,
            "lost_deficit": lost_deficit,
            "peak_eval_cp": peak_eval,
            "lowest_eval_cp": lowest_eval,
        },
        "brilliancies": brilliancies,
        "book_exit_ply": book_exit_ply,
        "tactical_themes": tactical_theme_counts,
        "hung_pieces_details": hung_pieces_details,
        "opp_captured_details": opp_captured_details,
        "tactical_motifs_details": tactical_motifs_details,
        "blunders_details": blunders_details,
        "lead_collapse_move": lead_collapse_move,
        "comeback_turn_move": comeback_turn_move,
        "clock_metrics": {
            "total_timed_moves": total_timed_moves,
            "total_time_spent": total_time_spent,
            "phase_time_spent": phase_time_spent,
            "phase_timed_moves": phase_timed_moves,
            "quality_time_spent": quality_time_spent,
            "quality_timed_moves": quality_timed_moves,
            "normal_moves": normal_moves,
            "normal_blunders": normal_blunders,
            "trouble_moves": trouble_moves,
            "trouble_blunders": trouble_blunders,
        },
    }
