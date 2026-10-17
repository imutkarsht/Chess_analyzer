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
    A piece is hanging if:
    1. It is attacked by at least one enemy piece, AND
    2. Either it is completely undefended, OR
       it is attacked by an enemy piece of strictly lower value, OR
       enemy attackers outnumber friendly defenders (under-defended exchange).
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
        friendly_defenders = board.attackers(color, square)

        # 1. Attacked by a lower-value piece (e.g., Queen attacked by Bishop/Pawn)
        attacked_by_lesser = any(
            PIECE_VALUES[board.piece_at(sq).piece_type] < piece_val
            for sq in enemy_attackers
            if board.piece_at(sq)
        )

        # 2. Completely undefended
        is_undefended = len(friendly_defenders) == 0

        # 3. Under-defended (more attackers than defenders)
        is_outnumbered = len(enemy_attackers) > len(friendly_defenders)

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
    total_hung = 0
    hanging_blunders = 0
    opp_hanging_captured = 0
    opp_hanging_missed = 0

    # Advantage tracking
    peak_eval = 0
    lowest_eval = 0
    had_winning_advantage = False  # >= +300 cp from user perspective
    had_losing_position = False  # <= -300 cp from user perspective

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
                opp_hanging_sqs = {h["square"] for h in opp_hanging_before}

                if chess.square_name(move_obj.to_square) in opp_hanging_sqs:
                    opp_hanging_captured += 1
                elif opp_hanging_before and classification in (
                    "Mistake",
                    "Inaccuracy",
                    "Blunder",
                    "Miss",
                ):
                    opp_hanging_missed += 1

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

    converted_advantage = had_winning_advantage and user_won
    choked_advantage = had_winning_advantage and not user_won
    comeback_drawn_or_won = had_losing_position and (user_won or is_draw)

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
        },
        "advantage_metrics": {
            "had_winning_advantage": had_winning_advantage,
            "converted_advantage": converted_advantage,
            "choked_advantage": choked_advantage,
            "had_losing_position": had_losing_position,
            "comeback_drawn_or_won": comeback_drawn_or_won,
            "peak_eval_cp": peak_eval,
            "lowest_eval_cp": lowest_eval,
        },
        "brilliancies": brilliancies,
        "book_exit_ply": book_exit_ply,
    }
