import chess
import chess.engine
from .models import GameAnalysis, MoveAnalysis
from .engine import EngineManager
from .cache import AnalysisCache
from typing import Optional, Tuple, List
import math
import statistics

class Analyzer:
    def __init__(self, engine_manager: EngineManager):
        self.engine_manager = engine_manager
        self.cache = AnalysisCache()
        self.config = {
            "time_per_move": 0.1,
            "depth": None,
            "multi_pv": 1,
            "use_cache": True
        }
        # Thresholds (centipawns) - NOT USED directly for classification anymore, but kept for reference
        self.thresholds = {
            "brilliant": 800, 
            "great": 0,       
            "best": 10,       
            "excellent": 30,
            "good": 75,
            "inaccuracy": 150,
            "mistake": 300,
            "blunder": float('inf')
        }

    def get_win_probability(self, cp: Optional[int], mate: Optional[int]) -> float:
        """
        Calculates win probability from centipawns or mate score.
        Returns value between 0.0 and 1.0.
        Formula based on Lichess: 50 + 50 * (2 / (1 + exp(-0.00368208 * cp)) - 1)
        """
        if mate is not None:
            # Mate in X. 
            if mate > 0:
                return 1.0
            elif mate < 0:
                return 0.0
            else:
                return 0.5 

        if cp is None:
            return 0.5
            
        try:
            multiplier = -0.00368208 * cp
            # If multiplier is too large/small, exp will overflow/underflow
            if multiplier > 40: 
                return 0.0 
            if multiplier < -40: 
                return 1.0 
                
            win_percent = 50 + 50 * (2 / (1 + math.exp(multiplier)) - 1)
            return win_percent / 100.0
        except OverflowError:
            return 1.0 if cp > 0 else 0.0

    def _calculate_move_accuracy(self, win_prob_before: float, win_prob_after: float) -> float:
        """
        Calculates accuracy of a single move based on Lichess formula.
        Accuracy% = 103.1668 * exp(-0.04354 * (winPercentBefore - winPercentAfter)) - 3.1669
        """
        # Win probabilities are 0.0-1.0 here, but formula likely expects 0-100 scale or similar?
        # Lichess source: 
        # val accuracy = 103.1668 * math.exp(-0.04354 * (winPercentBefore - winPercentAfter)) - 3.1669
        # where winPercent is 0..100.
        
        wp_before = win_prob_before * 100.0
        wp_after = win_prob_after * 100.0
        
        diff = wp_before - wp_after
        if diff < 0: diff = 0 # Improvement is perfect accuracy
        
        accuracy = 103.1668 * math.exp(-0.04354 * diff) - 3.1669
        
        return max(0.0, min(100.0, accuracy))

    def analyze_game(self, game_analysis: GameAnalysis, callback=None):
        """
        Analyzes a game structure in-place.
        """
        self.engine_manager.start_engine()
        try:
            board = chess.Board()
            
            # We need to replay the game to get board states
            
            for i, move_data in enumerate(game_analysis.moves):
                if callback:
                    callback(i, len(game_analysis.moves))
                
                # 1. Analyze position BEFORE move
                board.set_fen(move_data.fen_before)
                is_white_turn = board.turn
                
                # Check cache
                cached_result = None
                if self.config.get("use_cache", True):
                    cached_result = self.cache.get_analysis(move_data.fen_before, self.config)
                
                if cached_result:
                    info = cached_result
                else:
                    info = self.engine_manager.analyze_position(
                        board, 
                        time_limit=self.config["time_per_move"],
                        depth=self.config["depth"],
                        multi_pv=self.config["multi_pv"]
                    )
                    
                    if isinstance(info, list):
                        info = info[0] if info else {}
                    
                    serializable_info = {}
                    score = info.get("score")
                    if score:
                        if score.is_mate():
                            serializable_info["mate"] = score.relative.mate()
                        else:
                            serializable_info["cp"] = score.relative.score(mate_score=10000)
                    
                    pv = info.get("pv", [])
                    serializable_info["pv"] = [m.uci() for m in pv]
                    
                    if self.config.get("use_cache", True):
                        self.cache.save_analysis(move_data.fen_before, self.config, serializable_info)
                
                # Normalize info
                best_pv_uci = []
                score_cp = None
                score_mate = None
                
                if isinstance(info, dict) and "pv" in info and isinstance(info["pv"], list) and len(info["pv"]) > 0 and isinstance(info["pv"][0], str):
                    # Cached format
                    best_pv_uci = info.get("pv", [])
                    score_cp = info.get("cp")
                    score_mate = info.get("mate")
                else:
                    # Engine format
                    pv_moves = info.get("pv", [])
                    best_pv_uci = [m.uci() for m in pv_moves]
                    score = info.get("score")
                    if score:
                        if score.is_mate():
                            score_mate = score.relative.mate()
                        else:
                            score_cp = score.relative.score(mate_score=10000)

                # Store RAW engine score (relative to side to move)
                # But for consistency, we want to store everything from White's perspective in the final object?
                # Actually, standard is usually:
                # CP > 0 -> White advantage
                # CP < 0 -> Black advantage
                # Engine returns score relative to side to move.
                
                final_cp = score_cp
                final_mate = score_mate
                
                if not is_white_turn:
                    if final_cp is not None: final_cp = -final_cp
                    if final_mate is not None: final_mate = -final_mate
                
                move_data.eval_before_cp = final_cp
                move_data.eval_before_mate = final_mate
                move_data.best_move = best_pv_uci[0] if best_pv_uci else None
                move_data.pv = best_pv_uci
                
            # Analyze FINAL position
            board.set_fen(game_analysis.moves[-1].fen_before)
            board.push_uci(game_analysis.moves[-1].uci)
            final_info = self.engine_manager.analyze_position(board, time_limit=self.config["time_per_move"])
            if isinstance(final_info, list):
                final_info = final_info[0] if final_info else {}
            final_score = final_info.get("score")
            
            # Now iterate and classify
            summary_counts = {
                "white": {
                    "Brilliant": 0, "Great": 0, "Best": 0, "Excellent": 0, "Good": 0,
                    "Inaccuracy": 0, "Mistake": 0, "Blunder": 0, "Miss": 0, "Book": 0,
                    "acpl": 0, "move_count": 0, "accuracies": []
                },
                "black": {
                    "Brilliant": 0, "Great": 0, "Best": 0, "Excellent": 0, "Good": 0,
                    "Inaccuracy": 0, "Mistake": 0, "Blunder": 0, "Miss": 0, "Book": 0,
                    "acpl": 0, "move_count": 0, "accuracies": []
                }
            }
            
            for i, move in enumerate(game_analysis.moves):
                side = "white" if i % 2 == 0 else "black"
                
                # Get S1 (Eval before) - already normalized to White perspective
                s1_cp = move.eval_before_cp
                s1_mate = move.eval_before_mate
                
                # Get S2 (Eval of next position) - need to normalize to White perspective
                if i < len(game_analysis.moves) - 1:
                    next_move = game_analysis.moves[i+1]
                    s2_cp = next_move.eval_before_cp
                    s2_mate = next_move.eval_before_mate
                else:
                    # Use final_score
                    if final_score:
                        if final_score.is_mate():
                            s2_mate = final_score.relative.mate()
                            s2_cp = None
                        else:
                            s2_cp = final_score.relative.score(mate_score=10000)
                            s2_mate = None
                            
                        # Normalize final score (it's relative to side to move after last move)
                        # If last move was White, now it's Black's turn.
                        if board.turn == chess.BLACK:
                             if s2_cp is not None: s2_cp = -s2_cp
                             if s2_mate is not None: s2_mate = -s2_mate
                    else:
                        s2_cp = None
                        s2_mate = None
                
                # Store eval_after (White perspective)
                move.eval_after_cp = s2_cp
                move.eval_after_mate = s2_mate
                
                # Calculate Win Probabilities (White perspective)
                wp_before = self.get_win_probability(s1_cp, s1_mate)
                wp_after = self.get_win_probability(s2_cp, s2_mate)
                
                move.win_chance_before = wp_before
                move.win_chance_after = wp_after
                
                # Determine Win Probability Loss relative to the player who moved
                if side == "white":
                    # White wants to maximize win prob. Loss = Before - After
                    wpl = wp_before - wp_after
                else:
                    # Black wants to minimize win prob (maximize Black win prob).
                    # Black win prob = 1 - White win prob.
                    # Loss = (1 - wp_before) - (1 - wp_after) = wp_after - wp_before
                    wpl = wp_after - wp_before
                
                if wpl < 0: wpl = 0 # Improvement
                
                self._classify_move(move, wpl, side)
                
                # Update stats
                summary_counts[side][move.classification] += 1
                summary_counts[side]["move_count"] += 1
                
                # ACPL
                # CP Loss relative to player
                cp_loss = 0
                if s1_cp is not None and s2_cp is not None:
                    if side == "white":
                        cp_loss = s1_cp - s2_cp
                    else:
                        cp_loss = s2_cp - s1_cp
                
                if cp_loss > 0:
                    summary_counts[side]["acpl"] += cp_loss

                # Accuracy Calculation
                # Pass win probs from player perspective
                player_wp_before = wp_before if side == "white" else (1.0 - wp_before)
                player_wp_after = wp_after if side == "white" else (1.0 - wp_after)
                
                move_acc = self._calculate_move_accuracy(player_wp_before, player_wp_after)
                summary_counts[side]["accuracies"].append(move_acc)

            # Calculate Game Accuracy
            for side in ["white", "black"]:
                mc = summary_counts[side]["move_count"]
                if mc > 0:
                    summary_counts[side]["acpl"] /= mc
                    
                    accuracies = summary_counts[side]["accuracies"]
                    if not accuracies:
                        summary_counts[side]["accuracy"] = 0
                        continue
                        
                    # Harmonic Mean
                    # mean = n / sum(1/x)
                    # Add small epsilon to avoid div by zero
                    sum_inv = sum(1.0 / (a + 0.001) for a in accuracies)
                    harmonic_mean = len(accuracies) / sum_inv
                    
                    # Power Mean / Weighted Mean (simplified Lichess approach)
                    # Lichess uses standard deviation of win% as weights.
                    # Here we'll just use arithmetic mean for the second component for simplicity,
                    # or standard deviation if possible.
                    
                    arithmetic_mean = statistics.mean(accuracies)
                    
                    # Lichess combines them. Let's use (Harmonic + Arithmetic) / 2 as a robust metric
                    # or just Harmonic mean which punishes blunders heavily.
                    # Let's use Harmonic Mean primarily but blend it to be less harsh.
                    
                    summary_counts[side]["accuracy"] = (harmonic_mean + arithmetic_mean) / 2.0
                    
                else:
                    summary_counts[side]["accuracy"] = 0
                
                # Clean up temp list
                del summary_counts[side]["accuracies"]

            # Populate summary
            game_analysis.summary = summary_counts

        finally:
            self.engine_manager.stop_engine()

    def _classify_move(self, move: MoveAnalysis, wpl: float, side: str):
        """
        Classifies a move based on Win Probability Loss (WPL).
        """
        # If it's the best move (or mate in same number of moves), it's Best
        if move.uci == move.best_move:
            move.classification = "Best"
            return
            
        # Thresholds for WPL
        if wpl >= 0.20:
            move.classification = "Blunder"
        elif wpl >= 0.10:
            move.classification = "Mistake"
        elif wpl >= 0.05:
            move.classification = "Inaccuracy"
        elif wpl >= 0.02:
            move.classification = "Good"
        elif wpl >= 0.005:
            move.classification = "Excellent"
        else:
            move.classification = "Best"
            
        # Special Case: Missed Win
        # If we had a winning position (> 80%) and dropped to Drawish or Losing (< 60%)
        # Need player perspective win chance
        player_wc_before = move.win_chance_before if side == "white" else (1.0 - move.win_chance_before)
        player_wc_after = move.win_chance_after if side == "white" else (1.0 - move.win_chance_after)
        
        if player_wc_before > 0.80 and player_wc_after < 0.60:
            move.classification = "Miss"
            
        move.explanation = f"Win chance dropped by {wpl*100:.1f}%"

