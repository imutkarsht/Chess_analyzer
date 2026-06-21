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
    2. Best move (matches engine) -> Best/Great
    3. Missed forced mate -> Miss
    4. Missed winning position -> Miss  
    5. WPL thresholds -> Blunder/Mistake/Inaccuracy/Good/Excellent
    """
    # Calculate player-relative win chances
    player_wc_before = move.win_chance_before if side == "white" else (1.0 - move.win_chance_before)
    player_wc_after = move.win_chance_after if side == "white" else (1.0 - move.win_chance_after)
    
    # ============ PRIORITY 1: Delivering Checkmate ============
    # If player delivered checkmate, this is always "Best"
    if move.san and move.san.endswith('#'):
        move.classification = "Best"
        move.explanation = "Delivered checkmate!"
        return
    
    # ============ PRIORITY 1.5: Missed Forced Mate ============
    # Player had mate before but delayed it or lost it
    player_had_mate = (move.eval_before_mate is not None and 
                      ((side == "white" and move.eval_before_mate > 0) or
                       (side == "black" and move.eval_before_mate < 0)))
    
    if player_had_mate:
        missed_mate = False
        if side == "white":
            if (move.eval_after_mate is None or 
                move.eval_after_mate < 0 or 
                move.eval_after_mate > move.eval_before_mate):
                missed_mate = True
        else: # black
            if (move.eval_after_mate is None or 
                move.eval_after_mate > 0 or 
                move.eval_after_mate < move.eval_before_mate):
                missed_mate = True
                
        if missed_mate:
            move.classification = "Miss"
            move.explanation = "Missed a forced checkmate."
            return

    # Also check if position after is completely won (mate in X)
    if player_wc_after >= 0.99:
        move.classification = "Best"
        move.explanation = "Winning position maintained."
        return
        
    # ============ PRIORITY 2: Best Move Check ============
    is_best_choice = (move.uci == move.best_move) or (wpl <= 0.012)
    if is_best_choice:
        # Check for "Brilliant" or "Great" move - significantly better than alternatives
        # Only check if it is exactly the engine's top choice
        if move.uci == move.best_move and multi_pvs and len(multi_pvs) > 1:
            sb_data = multi_pvs[1]
            sb_cp = sb_data.get("cp")
            sb_mate = sb_data.get("mate")
            
            if sb_cp is not None or sb_mate is not None:
                # Normalize second-best score to player's perspective
                norm_sb_cp = sb_cp
                norm_sb_mate = sb_mate
                
                if side == "black":
                    if norm_sb_cp is not None: norm_sb_cp = -norm_sb_cp
                    if norm_sb_mate is not None: norm_sb_mate = -norm_sb_mate
                    
                sb_wp = get_win_probability(norm_sb_cp, norm_sb_mate)
                player_sb_wp = sb_wp if side == "white" else (1.0 - sb_wp)
                player_best_wp = player_wc_after
                
                # Calculate gap between best and second-best
                diff = player_best_wp - player_sb_wp
                
                # Brilliant: Extremely rare - only for truly exceptional moves
                # Requirements:
                # 1. Massive gap (>40%) between best and second-best move
                # 2. Move must improve position by at least 10%
                # 3. Player wasn't already completely winning (under 90% before)
                # 4. Position after must be strong (at least 50% win chance)
                position_improved = player_wc_after > player_wc_before + 0.10
                not_already_winning = player_wc_before < 0.90
                strong_after = player_wc_after >= 0.50
                
                if diff > 0.40 and position_improved and not_already_winning and strong_after:
                    move.classification = "Brilliant"
                    move.explanation = f"Brilliant! Only winning move. Alternatives were {diff*100:.0f}% worse."
                    return
                
                # Great: Significant gap (>15%) between best and second-best
                if diff > 0.15:
                    move.classification = "Great"
                    move.explanation = f"Only good move! Alternatives were {diff*100:.0f}% worse."
                    return

        move.classification = "Best"
        move.explanation = "Engine's top choice."
        return
        
    # ============ PRIORITY 3: Missed Winning/Better Position ============
    if wpl < 0.30:
        # Was clearly winning (>80%) and now not winning (<60%)
        if player_wc_before > 0.80 and player_wc_after < 0.60:
            move.classification = "Miss"
            move.explanation = f"Missed win (dropped from {player_wc_before*100:.0f}% to {player_wc_after*100:.0f}%)."
            return
        
        # Was winning (>70%) and lost significant equity (>20%)
        if player_wc_before > 0.70 and wpl > 0.20:
            move.classification = "Miss"
            move.explanation = f"Missed winning opportunity (lost {wpl*100:.0f}% winning chances)."
            return

        # Had a solid advantage (>=65%) and dropped to equal/worse (between 50% and 55%) with a significant loss (>=10%)
        if player_wc_before >= 0.65 and 0.50 <= player_wc_after < 0.55 and wpl >= 0.10:
            move.classification = "Miss"
            move.explanation = f"Missed opportunity to gain a significant advantage (dropped from {player_wc_before*100:.0f}% to {player_wc_after*100:.0f}%)."
            return

    # ============ PRIORITY 4: Blunder Check ============
    # Blunder leads to a losing position (win chance < 50%) or has an extreme drop (WPL >= 30%)
    if wpl >= 0.20 and (player_wc_after < 0.50 or wpl >= 0.30):
        move.classification = "Blunder"
        move.explanation = f"Lost {wpl*100:.1f}% winning chances."
        return

    # ============ PRIORITY 6: WPL-Based Classification ============
    # Thresholds tuned to match Chess.com more closely
    # Raised thresholds to reduce over-classification of inaccuracies
    if wpl >= 0.20:
        # If it reached here, it didn't trigger the Blunder check (since it was not a losing position)
        move.classification = "Mistake"
        move.explanation = f"Lost {wpl*100:.1f}% winning chances."
    elif wpl >= 0.10:
        move.classification = "Mistake"
        move.explanation = f"Lost {wpl*100:.1f}% winning chances."
    elif wpl >= 0.06:
        move.classification = "Inaccuracy"
        move.explanation = f"Slight inaccuracy ({wpl*100:.1f}% loss)."
    elif wpl >= 0.03:
        move.classification = "Good"
        move.explanation = "Solid move."
    else:
        move.classification = "Excellent"
        move.explanation = "Excellent move."
