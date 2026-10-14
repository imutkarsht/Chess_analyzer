"""Heuristics to classify moves (Brilliant, Blunder, etc.) based on Win Probability Loss."""

from typing import Any

import chess

from src.utils.logger import logger

from .math_utils import get_win_probability

# Standard piece values in centipawns. Used for sacrifice detection.
_PIECE_VALUES_CP: dict[chess.PieceType, int] = {
    chess.PAWN: 100,
    chess.KNIGHT: 300,
    chess.BISHOP: 325,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 0,  # King cannot be sacrificed or captured
}


def _get_piece_value(piece_type: chess.PieceType | None) -> int:
    if piece_type is None:
        return 0
    return _PIECE_VALUES_CP.get(piece_type, 0)


def _detect_sacrifice(fen_before: str | None, uci: str | None) -> bool:
    """
    Determines if a move constitutes a sound/intentional piece sacrifice.

    A sacrifice requires:
    1. A minor piece (Knight, Bishop), Rook, or Queen is moved or left hanging.
    2. The destination square (or an unblocked friendly major/minor piece) is
       attacked by an opponent piece of lower value, OR destination square is
       attacked with net material deficit if taken.
    3. Not an equal/higher trade (e.g. QxQ or RxR is an exchange, not a sacrifice).
    """
    if not fen_before or not uci:
        return False

    try:
        # Support Standard or Chess960 boards
        board = chess.Board(fen_before, chess960=True)
        move = chess.Move.from_uci(uci)

        if move not in board.legal_moves:
            return False

        moving_piece = board.piece_at(move.from_square)
        if moving_piece is None:
            return False

        moving_val = _get_piece_value(moving_piece.piece_type)
        captured_piece = board.piece_at(move.to_square)
        captured_val = _get_piece_value(captured_piece.piece_type) if captured_piece else 0

        # Disallow simple pawn moves from triggering piece sacrifice
        # (pawn gambits are not standard piece sacrifices)
        if moving_piece.piece_type == chess.PAWN:
            return False

        # If we captured an enemy piece of equal or greater value, it's a trade/recapture
        if captured_piece is not None and captured_val >= moving_val:
            return False

        # Apply the move to analyze resulting square attacks
        board.push(move)
        dest_sq = move.to_square
        opponent_color = board.turn  # After push, it is opponent's turn

        # Check if the destination square can be legally captured by opponent.
        # Note: A pinned piece attacking the square cannot legally capture!
        # If the opponent cannot legally capture the piece, it is NOT a sacrifice.
        legal_attackers = [
            sq
            for sq in board.attackers(opponent_color, dest_sq)
            if chess.Move(sq, dest_sq) in board.legal_moves
        ]

        if legal_attackers:
            cheapest_attacker_val = min(
                _get_piece_value(board.piece_at(sq).piece_type if board.piece_at(sq) else None)
                for sq in legal_attackers
            )

            # Case A: An opponent piece of lower value attacks our piece
            # (e.g. pawn attacks knight/bishop/rook/queen, minor attacks rook/queen, rook attacks queen)
            # Net deficit: moving_val - captured_val >= 150 (covers exchange sacrifices, e.g. R for B/N: 500 - 325 = 175)
            net_material_given = moving_val - captured_val
            if cheapest_attacker_val < moving_val and net_material_given >= 150:
                logger.debug(
                    "Sacrifice detected (Case A: lower-value attacker): move %s, net deficit %d cp",
                    uci,
                    net_material_given,
                )
                return True

            # Case B: Square is defended by opponent and friendly defenders < attackers
            # (hanging piece / sacrifice on a defended square)
            friendly_color = not opponent_color
            defenders = board.attackers(friendly_color, dest_sq)
            if len(legal_attackers) > len(defenders) and net_material_given >= 150:
                logger.debug(
                    "Sacrifice detected (Case B: underdefended square): move %s, net deficit %d cp",
                    uci,
                    net_material_given,
                )
                return True

        return False
    except Exception as e:
        logger.debug("Sacrifice detection failed for move %s: %s", uci, e)
        return False


def _is_recapture_or_routine_capture(
    fen_before: str | None,
    uci: str | None,
    prev_move: Any = None,
) -> bool:
    """
    Determines if a move is a recapture, routine piece trade, or obvious capture of a hanging piece.
    Such moves must be classified as 'Best', never 'Great', even if they are the only viable move.
    """
    # 1. Check direct recapture via move coordinates
    # If the opponent moved to square X on the previous ply and this move lands on square X,
    # it is capturing the piece that just moved/captured there (direct recapture or taking blunder).
    if prev_move is not None and uci and len(uci) >= 4:
        prev_uci = getattr(prev_move, "uci", None)
        if prev_uci and len(prev_uci) >= 4 and prev_uci[2:4] == uci[2:4]:
            logger.debug(
                "Recapture detected via square matching: %s on %s",
                uci,
                uci[2:4],
            )
            return True

    if not fen_before or not uci:
        return False

    try:
        board = chess.Board(fen_before, chess960=True)
        chess_move = chess.Move.from_uci(uci)

        if chess_move not in board.legal_moves:
            return False

        # If it's not a capture, it cannot be a recapture or piece trade
        if not board.is_capture(chess_move):
            return False

        dest_sq = chess_move.to_square

        # En passant always captures the pawn that just moved
        if board.is_en_passant(chess_move):
            return True

        moving_piece = board.piece_at(chess_move.from_square)
        moving_val = _get_piece_value(moving_piece.piece_type if moving_piece else None)
        captured_piece = board.piece_at(dest_sq)
        captured_val = _get_piece_value(captured_piece.piece_type if captured_piece else chess.PAWN)

        # Equal trade (e.g. QxQ, RxR, BxB, NxN, PxP)
        if captured_val == moving_val:
            return True

        # Minor piece for minor piece trade (Bishop for Knight or Knight for Bishop)
        return bool(
            moving_piece
            and captured_piece
            and moving_piece.piece_type in (chess.KNIGHT, chess.BISHOP)
            and captured_piece.piece_type in (chess.KNIGHT, chess.BISHOP)
        )
    except Exception as e:
        logger.debug("Recapture check failed for move %s: %s", uci, e)
        return False


def classify_move(
    move: Any,
    wpl: float,
    side: str,
    multi_pvs: list[dict[str, Any]] | None = None,
    prev_move: Any = None,
) -> None:
    """
    Classifies a move via WPL thresholds and special-case checks.
    Modifies move.classification and move.explanation in-place.

    Priority order: checkmate > missed mate > winning position > best move > blunder > miss > WPL tiers.
    """
    player_wc_before = move.win_chance_before if side == "white" else (1.0 - move.win_chance_before)
    player_wc_after = move.win_chance_after if side == "white" else (1.0 - move.win_chance_after)

    # ============ PRIORITY 1: Delivering Checkmate ============
    if move.san and move.san.endswith("#"):
        move.classification = "Best"
        move.explanation = "Delivered checkmate!"
        return

    # ============ PRIORITY 2: Missed Forced Mate ============
    player_had_mate = move.eval_before_mate is not None and (
        (side == "white" and move.eval_before_mate > 0)
        or (side == "black" and move.eval_before_mate < 0)
    )

    fen_before = getattr(move, "fen_before", None)
    uci = getattr(move, "uci", None)
    is_sacrifice_candidate = move.uci == move.best_move and _detect_sacrifice(fen_before, uci)

    if player_had_mate:
        missed_mate = False
        if side == "white":
            if move.eval_after_mate is None or move.eval_after_mate < 0:
                missed_mate = True
        else:
            if move.eval_after_mate is None or move.eval_after_mate > 0:
                missed_mate = True

        if missed_mate:
            move.classification = "Miss"
            move.explanation = "Missed a forced checkmate."
            return

        if move.uci != move.best_move and player_wc_after >= 0.99:
            pass
        elif player_wc_after >= 0.99 and not is_sacrifice_candidate:
            move.classification = "Best"
            move.explanation = "Winning position maintained."
            return

    # ============ PRIORITY 2.5: Winning Position After (no mate context) ============
    # Allow Brilliant piece sacrifice checks to run even in high winning chances
    # if the player executed a genuine tactical sacrifice.
    if (
        player_wc_after >= 0.99
        and not is_sacrifice_candidate
        and not (player_had_mate and move.uci != move.best_move)
    ):
        move.classification = "Best"
        move.explanation = "Winning position maintained."
        return

    # ============ PRIORITY 3: Best Move Check ============
    is_best_choice = move.uci == move.best_move

    if is_best_choice:
        # --- BRILLIANT MOVE DETECTION ---
        # Criteria:
        # 1. Piece sacrifice detected (minor piece, rook, queen given up/offered).
        # 2. Engine approves the sacrifice as sound (wpl <= 0.05).
        # 3. Position remains competitive or winning after (player_wc_after >= 0.40).
        # 4. Contextual gating:
        #    - In balanced, slight, or moderately winning positions (player_wc_before < 0.95),
        #      any sound piece sacrifice is Brilliant.
        #    - In dead-winning positions (player_wc_before >= 0.95, e.g. up +7 or more):
        #      Chess.com allows Brilliant ONLY if the sacrifice is forcing/decisive:
        #      either it leads to a forced checkmate (eval_after_mate is not None),
        #      or alternative moves were clearly inferior (diff > 0.05 if multi_pvs available).
        #      This prevents lazy "free" sacrifices when already up multiple pieces.
        is_sac = _detect_sacrifice(fen_before, uci)
        competitive_after = player_wc_after >= 0.40
        sound_eval = wpl <= 0.05

        leads_to_mate = move.eval_after_mate is not None and (
            (side == "white" and move.eval_after_mate > 0)
            or (side == "black" and move.eval_after_mate < 0)
        )

        # Allow if position wasn't crushing (wc < 0.95), OR if crushing but leads to forced mate
        context_approved = (player_wc_before < 0.95) or leads_to_mate

        if is_sac and context_approved and competitive_after and sound_eval:
            # If multi-PV exists, ensure alternative wasn't vastly superior or equally trivial
            alternative_veto = False
            if multi_pvs and len(multi_pvs) > 1:
                sb_data = multi_pvs[1]
                sb_cp = sb_data.get("cp")
                sb_mate = sb_data.get("mate")
                if sb_cp is not None or sb_mate is not None:
                    norm_sb_cp = -sb_cp if (side == "black" and sb_cp is not None) else sb_cp
                    norm_sb_mate = (
                        -sb_mate if (side == "black" and sb_mate is not None) else sb_mate
                    )
                    sb_wp = get_win_probability(norm_sb_cp, norm_sb_mate)
                    player_sb_wp = sb_wp if side == "white" else (1.0 - sb_wp)

                    if player_sb_wp > player_wc_after + 0.10:
                        alternative_veto = True

                    # In dead-winning positions, if alternative is just as good and no mate, don't give free brilliant
                    if (
                        player_wc_before >= 0.95
                        and not leads_to_mate
                        and (player_wc_after - player_sb_wp) < 0.05
                    ):
                        alternative_veto = True

            if not alternative_veto:
                move.classification = "Brilliant"
                move.explanation = (
                    "Brilliant sacrifice! Sacrificed material to gain a decisive advantage."
                )
                logger.debug(
                    "Move %s (%s) classified as Brilliant (sacrifice verified, wpl=%.3f, wc_before=%.2f, wc_after=%.2f)",
                    getattr(move, "san", getattr(move, "uci", "unknown")),
                    side,
                    wpl,
                    player_wc_before,
                    player_wc_after,
                )
                return

        # --- GREAT MOVE DETECTION ---
        # Chess.com criteria: An only move that is critical to saving the game or maintaining an advantage.
        # Obvious recaptures, routine trades, and simple captures of hanging pieces are strictly excluded.
        is_routine_or_recapture = _is_recapture_or_routine_capture(fen_before, uci, prev_move)

        # Check if the move is forced or trivial escape from check
        is_forced_or_trivial = False
        if fen_before:
            try:
                temp_board = chess.Board(fen_before, chess960=True)
                legal_count = temp_board.legal_moves.count()
                if legal_count <= 1 or (temp_board.is_check() and legal_count <= 2):
                    is_forced_or_trivial = True
            except Exception:
                pass

        # Exclude direct recaptures, routine equal trades, or forced moves
        can_be_great = not is_routine_or_recapture and not is_forced_or_trivial

        if can_be_great and multi_pvs and len(multi_pvs) > 1:
            sb_data = multi_pvs[1]
            sb_cp = sb_data.get("cp")
            sb_mate = sb_data.get("mate")

            if sb_cp is not None or sb_mate is not None:
                norm_sb_cp = sb_cp
                norm_sb_mate = sb_mate

                if side == "black":
                    if norm_sb_cp is not None:
                        norm_sb_cp = -norm_sb_cp
                    if norm_sb_mate is not None:
                        norm_sb_mate = -norm_sb_mate

                sb_wp = get_win_probability(norm_sb_cp, norm_sb_mate)
                player_sb_wp = sb_wp if side == "white" else (1.0 - sb_wp)
                diff = player_wc_after - player_sb_wp

                # If alternatives were significantly worse (rest are worse), this is the only move -> Great!
                if diff >= 0.15:
                    move.classification = "Great"
                    move.explanation = f"Only good move! Alternatives were {diff * 100:.0f}% worse."
                    logger.debug(
                        "Move %s (%s) classified as Great (only move, diff=%.2f)",
                        getattr(move, "san", getattr(move, "uci", "unknown")),
                        side,
                        diff,
                    )
                    return

        move.classification = "Best"
        move.explanation = "Engine's top choice."
        return

    # Noise guard: If the player remains overwhelmingly winning after the move
    # (e.g. still +700 cp or higher, up multiple pieces), it is not a game-altering blunder/mistake.
    still_crushing_after = move.eval_after_cp is not None and (
        (side == "white" and move.eval_after_cp >= 700)
        or (side == "black" and move.eval_after_cp <= -700)
    )

    # ============ PRIORITY 4: Miss Check (Missed Opportunity) ============
    # A Miss occurs when the player had a clear winning or tactical advantage
    # (player_wc_before >= 0.70) but failed to find the punish, letting the opponent
    # off the hook back into an equal or roughly balanced game (player_wc_after >= 0.45).
    # Since the player did NOT ruin their position into a loss, it is a MISS, not a Blunder!
    is_missed_opportunity = (
        player_wc_before >= 0.70
        and wpl >= 0.15
        and player_wc_after >= 0.42
        and not still_crushing_after
    )
    if is_missed_opportunity:
        move.classification = "Miss"
        move.explanation = f"Missed opportunity (dropped from {player_wc_before * 100:.0f}% to {player_wc_after * 100:.0f}%)."
        logger.debug(
            "Move %s (%s) classified as Miss (wc_before=%.2f -> wc_after=%.2f)",
            getattr(move, "san", getattr(move, "uci", "unknown")),
            side,
            player_wc_before,
            player_wc_after,
        )
        return

    # ============ PRIORITY 5: Blunder Check ============
    # A Blunder is a catastrophic error that directly turns the position into a loss
    # or severely damages winning chances:
    # 1. Massive win chance loss (WPL >= 0.25) where player does not remain winning (wc_after < 0.60).
    # 2. Or substantial win chance loss (WPL >= 0.20) that directly plunges player into losing territory (wc_after < 0.35).
    is_blunder = (
        (wpl >= 0.25 and player_wc_after < 0.60) or (wpl >= 0.20 and player_wc_after < 0.35)
    ) and not still_crushing_after

    if is_blunder:
        move.classification = "Blunder"
        move.explanation = f"Blunder! Lost {wpl * 100:.1f}% winning chances."
        logger.debug(
            "Move %s (%s) classified as Blunder (wpl=%.3f, wc_after=%.2f)",
            getattr(move, "san", getattr(move, "uci", "unknown")),
            side,
            wpl,
            player_wc_after,
        )
        return

    # If player had a big lead (wc >= 70%) and dropped down to losing (wc < 42%), that is also a Missed Win
    if (
        player_wc_before >= 0.70
        and player_wc_after < 0.42
        and wpl >= 0.25
        and not still_crushing_after
    ):
        move.classification = "Miss"
        move.explanation = f"Missed win (dropped from {player_wc_before * 100:.0f}% to {player_wc_after * 100:.0f}%)."
        logger.debug(
            "Move %s (%s) classified as Miss (wc_before=%.2f -> wc_after=%.2f)",
            getattr(move, "san", getattr(move, "uci", "unknown")),
            side,
            player_wc_before,
            player_wc_after,
        )
        return

    # ============ PRIORITY 6: Standard Expected Points Tiers ============
    # Standard Chess.com Expected Points Loss (WPL) thresholds:
    # Mistake:    0.10 <= WPL < 0.25
    # Inaccuracy: 0.05 <= WPL < 0.10
    # Good:       0.02 <= WPL < 0.05
    # Excellent:  WPL < 0.02
    if wpl >= 0.10 and not still_crushing_after:
        move.classification = "Mistake"
        move.explanation = f"Mistake (lost {wpl * 100:.1f}% winning chances)."
    elif wpl >= 0.05 and not still_crushing_after:
        move.classification = "Inaccuracy"
        move.explanation = f"Inaccuracy (lost {wpl * 100:.1f}% winning chances)."
    elif wpl >= 0.02:
        move.classification = "Good"
        move.explanation = "Solid move."
    else:
        move.classification = "Excellent"
        move.explanation = "Excellent move."
