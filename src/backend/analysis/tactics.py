"""
Tactical and game-phase analysis utilities.
Provides deterministic hanging piece detection, game phase classification
(Opening, Middlegame, Endgame), advantage conversion calculation, and
brilliancy extraction.
Zero Qt dependencies — headless and independently testable.
"""

from __future__ import annotations

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


def get_hanging_pieces(board: chess.Board, color: chess.Color) -> list[dict]:
    """
    Finds all pieces belonging to `color` that are hanging on `board`.
    A piece is truly hanging if:
    1. It is attacked by at least one enemy piece, AND
    2. Either:
       a) It is completely undefended (no legal defenders), OR
       b) It is attacked by an enemy piece of strictly lower value (e.g. Queen/Rook attacked by Pawn/Minor), OR
       c) Enemy attackers outnumber friendly legal defenders AND the minimum attacker value
          is less than or equal to the target piece value (meaning an exchange is profitable).
    Pinned defenders that cannot legally move to the target square without exposing their King
    to check are correctly filtered out as unable to defend.
    """
    hanging = []
    enemy_color = not color

    for square, piece in board.piece_map().items():
        if piece.color != color or piece.piece_type == chess.KING:
            continue

        enemy_attackers = board.attackers(enemy_color, square)
        if not enemy_attackers:
            continue

        piece_val = PIECE_VALUES[piece.piece_type]

        # Filter friendly defenders for absolute pins:
        # A pinned defender can only defend squares along its legal pin ray
        raw_defenders = board.attackers(color, square)
        friendly_defenders = [sq for sq in raw_defenders if square in board.pin(color, sq)]

        attacker_vals = [
            PIECE_VALUES[board.piece_at(sq).piece_type]
            for sq in enemy_attackers
            if board.piece_at(sq)
        ]
        if not attacker_vals:
            continue

        min_attacker_val = min(attacker_vals)

        # 1. Completely undefended by legal pieces
        is_undefended = len(friendly_defenders) == 0

        # 2. Attacked by a strictly lower-value piece (e.g., Queen attacked by Bishop/Pawn)
        attacked_by_lesser = min_attacker_val < piece_val

        # 3. Under-defended exchange: more attackers than defenders, AND the lowest attacker
        # can profitably or equally initiate the trade (not a defended pawn attacked by minor/major pieces)
        is_outnumbered = (len(enemy_attackers) > len(friendly_defenders)) and (
            min_attacker_val <= piece_val
        )

        if is_undefended or attacked_by_lesser or is_outnumbered:
            hanging.append(
                {
                    "square": chess.square_name(square),
                    "square_index": square,
                    "piece_type": piece.piece_type,
                    "piece_name": PIECE_NAMES[piece.piece_type],
                    "piece_val": piece_val,
                    "is_undefended": is_undefended,
                    "attacked_by_lesser": attacked_by_lesser,
                    "is_outnumbered": is_outnumbered,
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
    - 'fork': Piece attacks 2+ valuable/undefended enemy pieces or King + piece.
    - 'pin': Establishes an absolute pin against the enemy King.
    - 'skewer': Attacks high-value piece in front with another target behind on same ray.
    - 'discovered_attack': Removing a piece unmasks a sliding attack/check from a piece behind it.
    - 'sacrifice': Sound piece sacrifice for tactical advantage (Brilliant/Great).
    - 'back_rank': Infiltrating or delivering check on the 8th/1st rank against a trapped King.
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
    if classification in ("Brilliant", "Great"):
        motifs.append("sacrifice")

    # 2. Fork / Double Attack
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
            target_val = PIECE_VALUES.get(target_p.piece_type, 0)
            defenders = board_after.attackers(enemy_color, target_sq)
            if len(defenders) == 0 or target_val >= piece_val or target_val >= 3:
                valuable_targets += 1

    if valuable_targets >= 2:
        motifs.append("fork")

    # 3. Pin: Did this move establish a new absolute pin on an enemy piece?
    if piece.piece_type in (chess.BISHOP, chess.ROOK, chess.QUEEN) and enemy_king_sq is not None:
        for sq in board_after.piece_map():
            if (
                board_after.color_at(sq) == enemy_color
                and sq != enemy_king_sq
                and board_after.is_pinned(enemy_color, sq)
                and not board_before.is_pinned(enemy_color, sq)
                and to_sq in board_after.attackers(color, sq)
            ):
                motifs.append("pin")
                break

    # 4. Discovered Attack / Discovered Check
    is_discovered = False
    if board_after.is_check():
        checkers = board_after.checkers()
        if to_sq not in checkers and len(checkers) > 0:
            is_discovered = True

    if not is_discovered:
        friendly_sliders = (
            board_after.pieces(chess.ROOK, color)
            | board_after.pieces(chess.BISHOP, color)
            | board_after.pieces(chess.QUEEN, color)
        )
        for s_sq in friendly_sliders:
            if s_sq != to_sq and from_sq in board_after.attacks(s_sq):
                new_targets = board_after.attacks(s_sq) - board_before.attacks(s_sq)
                for nt in new_targets:
                    nt_piece = board_after.piece_at(nt)
                    if (
                        nt_piece
                        and nt_piece.color == enemy_color
                        and nt_piece.piece_type != chess.PAWN
                    ):
                        is_discovered = True
                        break
            if is_discovered:
                break

    if is_discovered:
        motifs.append("discovered_attack")

    # 5. Skewer
    if piece.piece_type in (chess.BISHOP, chess.ROOK, chess.QUEEN):
        for direct_target in board_after.attacks(to_sq):
            dt_p = board_after.piece_at(direct_target)
            if dt_p and dt_p.color == enemy_color:
                dt_val = (
                    10 if dt_p.piece_type == chess.KING else PIECE_VALUES.get(dt_p.piece_type, 0)
                )
                if dt_val >= 3:
                    ray = chess.SquareSet.ray(to_sq, direct_target)
                    behind_sqs = [
                        sq
                        for sq in ray
                        if chess.square_distance(to_sq, sq)
                        > chess.square_distance(to_sq, direct_target)
                    ]
                    for b_sq in behind_sqs:
                        b_piece = board_after.piece_at(b_sq)
                        if b_piece:
                            if b_piece.color == enemy_color and dt_val > PIECE_VALUES.get(
                                b_piece.piece_type, 0
                            ):
                                motifs.append("skewer")
                            break

    # 6. Back Rank Weakness / Infiltration
    back_rank = 7 if enemy_color == chess.BLACK else 0
    if (
        chess.square_rank(to_sq) == back_rank
        and piece.piece_type in (chess.ROOK, chess.QUEEN)
        and enemy_king_sq is not None
        and chess.square_rank(enemy_king_sq) == back_rank
    ):
        pawn_rank = 6 if enemy_color == chess.BLACK else 1
        shield_pawns = [
            sq
            for sq in board_after.pieces(chess.PAWN, enemy_color)
            if chess.square_rank(sq) == pawn_rank
            and abs(chess.square_file(sq) - chess.square_file(enemy_king_sq)) <= 1
        ]
        if len(shield_pawns) >= 2 and (has_check or board_after.is_check()):
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

            if classification == "Blunder":
                phase_blunders[phase] += 1

            # 2. Hanging piece detection after user move
            try:
                move_obj = chess.Move.from_uci(uci) if uci else board_before.parse_san(san)
                board_after = board_before.copy()
                board_after.push(move_obj)

                wp_drop = player_wp_before - player_wp_after

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
                    user_hanging = get_hanging_pieces(board_after, target_color)
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
