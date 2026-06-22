"""
Move classifier module containing heuristics to tag moves (e.g. Brilliant, Blunder) based on evaluation changes.
"""
from typing import List, Dict, Any
from .math_utils import get_win_probability

def classify_move(move: Any, wpl: float, side: str, multi_pvs: List[Dict[str, Any]] = None) -> None:
    """
    Classifies a move based on Win Probability Loss (WPL).
    Modifies the move object's classification and explanation in-place.

    Classification priority (checked in order):
    1. Delivering checkmate -> Best
    2. Missed forced mate -> Miss
    3. Missed winning/better position -> Miss
    4. Best move (matches engine) -> Brilliant/Great/Best
    5. WPL thresholds -> Blunder/Mistake/Inaccuracy/Good/Excellent
    """
    player_wc_before = move.win_chance_before if side == "white" else (1.0 - move.win_chance_before)
    player_wc_after = move.win_chance_after if side == "white" else (1.0 - move.win_chance_after)

    # ============ PRIORITY 1: Delivering Checkmate ============
    if move.san and move.san.endswith('#'):
        move.classification = "Best"
        move.explanation = "Delivered checkmate!"
        return

    # ============ PRIORITY 2: Missed Forced Mate ============
    player_had_mate = (move.eval_before_mate is not None and
                      ((side == "white" and move.eval_before_mate > 0) or
                       (side == "black" and move.eval_before_mate < 0)))

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

        # Player still has mate advantage but didn't play the optimal move.
        # Don't short-circuit to "Best"; fall through for proper classification.
        if move.uci != move.best_move and player_wc_after >= 0.99:
            pass
        elif player_wc_after >= 0.99:
            move.classification = "Best"
            move.explanation = "Winning position maintained."
            return

    # ============ PRIORITY 2.5: Winning Position After (no mate context) ============
    if player_wc_after >= 0.99:
        if not (player_had_mate and move.uci != move.best_move):
            move.classification = "Best"
            move.explanation = "Winning position maintained."
            return

    # ============ PRIORITY 3: Best Move Check ============
    is_best_choice = (move.uci == move.best_move)
    # Disqualify only if player was clearly winning and still dropped equity.
    # When player_wc_before < 0.70, the position is complex or worse, so the
    # engine's best move can still be correct even with high WPL.
    if is_best_choice and wpl >= 0.05 and player_wc_before >= 0.70:
        is_best_choice = False

    if is_best_choice:
        # Multi-PV: check if the best move is significantly better than alternatives
        if move.uci == move.best_move and multi_pvs and len(multi_pvs) > 1:
            sb_data = multi_pvs[1]
            sb_cp = sb_data.get("cp")
            sb_mate = sb_data.get("mate")

            if sb_cp is not None or sb_mate is not None:
                norm_sb_cp = sb_cp
                norm_sb_mate = sb_mate

                if side == "black":
                    if norm_sb_cp is not None: norm_sb_cp = -norm_sb_cp
                    if norm_sb_mate is not None: norm_sb_mate = -norm_sb_mate

                sb_wp = get_win_probability(norm_sb_cp, norm_sb_mate)
                player_sb_wp = sb_wp if side == "white" else (1.0 - sb_wp)
                player_best_wp = player_wc_after

                diff = player_best_wp - player_sb_wp

                position_improved = player_wc_after > player_wc_before + 0.10
                not_already_winning = player_wc_before < 0.90
                strong_after = player_wc_after >= 0.50

                if diff > 0.40 and position_improved and not_already_winning and strong_after:
                    move.classification = "Brilliant"
                    move.explanation = f"Brilliant! Only winning move. Alternatives were {diff*100:.0f}% worse."
                    return

                if diff > 0.15:
                    move.classification = "Great"
                    move.explanation = f"Only good move! Alternatives were {diff*100:.0f}% worse."
                    return

        move.classification = "Best"
        move.explanation = "Engine's top choice."
        return

    # ============ PRIORITY 4: Missed Winning/Better Position ============
    # Was completely winning and dropped significantly
    if player_wc_before > 0.80 and player_wc_after < 0.60:
        move.classification = "Miss"
        move.explanation = f"Missed win (dropped from {player_wc_before*100:.0f}% to {player_wc_after*100:.0f}%)."
        return

    # Was winning and lost significant equity
    if player_wc_before > 0.70 and wpl > 0.15:
        move.classification = "Miss"
        move.explanation = f"Missed winning opportunity (lost {wpl*100:.0f}% winning chances)."
        return

    # Had advantage and dropped to equal/worse
    if player_wc_before >= 0.60 and player_wc_after < 0.50 and wpl >= 0.10:
        move.classification = "Miss"
        move.explanation = f"Missed opportunity (dropped from {player_wc_before*100:.0f}% to {player_wc_after*100:.0f}%)."
        return

    # Lost a very large amount of equity from a winning/advantageous position
    if wpl >= 0.30 and player_wc_before > 0.50:
        move.classification = "Miss"
        move.explanation = f"Missed (lost {wpl*100:.0f}% winning chances)."
        return

    # ============ PRIORITY 5: Blunder Check ============
    if wpl >= 0.25 and (player_wc_after < 0.50 or wpl >= 0.35):
        move.classification = "Blunder"
        move.explanation = f"Lost {wpl*100:.1f}% winning chances."
        return

    # ============ PRIORITY 6: WPL-Based Classification ============
    if wpl >= 0.12:
        move.classification = "Mistake"
        move.explanation = f"Lost {wpl*100:.1f}% winning chances."
    elif wpl >= 0.05:
        move.classification = "Inaccuracy"
        move.explanation = f"Slight inaccuracy ({wpl*100:.1f}% loss)."
    elif wpl >= 0.02:
        move.classification = "Good"
        move.explanation = "Solid move."
    else:
        move.classification = "Excellent"
        move.explanation = "Excellent move."
