import chess
import chess.engine
from .models import GameAnalysis, MoveAnalysis
from .engine import EngineManager
from .cache import AnalysisCache
from .book import BookManager
from ..utils.logger import logger
from typing import Optional, Tuple, List
import math
import statistics

class Analyzer:
    def __init__(self, engine_manager: EngineManager):
        self.engine_manager = engine_manager
        self.cache = AnalysisCache()
        self.book_manager = BookManager()
        self.config = {
            "time_per_move": 0.1,
            "depth": None,
            "multi_pv": 3,
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
        logger.info(f"Starting analysis for game: {game_analysis.game_id}")
        self.engine_manager.start_engine()
        try:
            board = chess.Board()
            
            # We need to replay the game to get board states
            
            for i, move_data in enumerate(game_analysis.moves):
                if callback:
                    callback(i, len(game_analysis.moves))
                
                # Log progress every 10 moves
                if i % 10 == 0:
                    logger.debug(f"Analyzing move {i+1}/{len(game_analysis.moves)}")
                
                # 1. Analyze position BEFORE move
                board.set_fen(move_data.fen_before)
                is_white_turn = board.turn
                
                # Check cache
                cached_result = None
                if self.config.get("use_cache", True):
                    cached_result = self.cache.get_analysis(move_data.fen_before, self.config)
                
                if cached_result:
                    info_list = cached_result
                else:
                    info_list = self.engine_manager.analyze_position(
                        board, 
                        time_limit=self.config["time_per_move"],
                        depth=self.config["depth"],
                        multi_pv=self.config["multi_pv"]
                    )
                    
                    # Ensure it's a list
                    if not isinstance(info_list, list):
                        info_list = [info_list]
                    
                    # Serialize for cache
                    serializable_list = []
                    for info in info_list:
                        s_info = {}
                        score = info.get("score")
                        if score:
                            if score.is_mate():
                                s_info["mate"] = score.relative.mate()
                            else:
                                s_info["cp"] = score.relative.score(mate_score=10000)
                        
                        pv = info.get("pv", [])
                        s_info["pv"] = [m.uci() for m in pv]
                        serializable_list.append(s_info)
                    
                    if self.config.get("use_cache", True):
                        self.cache.save_analysis(move_data.fen_before, self.config, serializable_list)
                
                # Normalize info
                best_pv_uci = []
                score_cp = None
                score_mate = None
                
                # Process Multi-PVs
                move_data.multi_pvs = []
                
                # If cached, it's already a list of dicts. If fresh, it's a list of InfoDicts.
                # We need to unify this.
                
                # Let's assume info_list contains the data we need.
                # If it came from cache, it's list[dict].
                # If it came from engine, it's list[InfoDict].
                
                primary_info = None
                
                for idx, item in enumerate(info_list):
                    pv_data = {}
                    
                    if isinstance(item, dict) and "pv" in item and isinstance(item["pv"], list) and len(item["pv"]) > 0 and isinstance(item["pv"][0], str):
                        # Cached format
                        pv_uci = item.get("pv", [])
                        cp = item.get("cp")
                        mate = item.get("mate")
                    else:
                        # Engine format
                        pv_moves = item.get("pv", [])
                        pv_uci = [m.uci() for m in pv_moves]
                        score = item.get("score")
                        cp = None
                        mate = None
                        if score:
                            if score.is_mate():
                                mate = score.relative.mate()
                            else:
                                cp = score.relative.score(mate_score=10000)
                                
                    pv_data["pv"] = pv_uci
                    pv_data["cp"] = cp
                    pv_data["mate"] = mate
                    
                    # Convert PV to SAN
                    # We need to use the board state to generate SAN
                    # The board is currently at the position BEFORE the move.
                    # But for Multi-PV, the lines are variations from this position.
                    # So board.variation_san(pv_moves) should work if pv_moves are Move objects.
                    
                    san_pv = ""
                    try:
                        # Re-parse UCI moves to Move objects for this board state
                        # Note: pv_moves from engine might be Move objects or strings depending on library version/usage
                        # In our code above: pv_moves = item.get("pv", [])
                        # If from engine (python-chess), they are Move objects.
                        # If from cache (dict), they are UCI strings.
                        
                        real_pv_moves = []
                        for m in pv_moves:
                            if isinstance(m, str):
                                real_pv_moves.append(chess.Move.from_uci(m))
                            else:
                                real_pv_moves.append(m)
                                
                        san_pv = board.variation_san(real_pv_moves)
                    except Exception as e:
                        # Fallback to UCI if SAN generation fails
                        san_pv = " ".join(pv_uci)
                        
                    pv_data["pv_san"] = san_pv
                    
                    # Normalize score to White perspective for display/storage if needed?
                    # Actually, for MoveAnalysis.multi_pvs, we usually want relative to side to move, 
                    # OR we store it as is and UI handles it.
                    # The existing logic stores eval_before_cp relative to side to move (then normalized later).
                    
                    # Let's store RAW relative score in multi_pvs
                    pv_data["score_value"] = f"M{mate}" if mate is not None else f"{cp/100:.2f}" if cp is not None else "?"
                    
                    move_data.multi_pvs.append(pv_data)
                    
                    if idx == 0:
                        primary_info = pv_data
                        best_pv_uci = pv_uci
                        score_cp = cp
                        score_mate = mate

                # Store RAW engine score (relative to side to move)
                
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
            final_info_list = self.engine_manager.analyze_position(board, time_limit=self.config["time_per_move"])
            
            if isinstance(final_info_list, list):
                final_info = final_info_list[0] if final_info_list else {}
            else:
                final_info = final_info_list
                
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
            
            # Create a board for move verification
            temp_board = chess.Board()
            
            # Track opening
            opening_name = "Unknown Opening"
            in_book = True

            for i, move in enumerate(game_analysis.moves):
                # Determine side from FEN for robustness
                temp_board.set_fen(move.fen_before)
                side = "white" if temp_board.turn == chess.WHITE else "black"
                
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
                
                # Book Move Check
                if in_book:
                    name = self.book_manager.get_opening_name(move.fen_before, move.uci)
                    if name:
                        move.classification = "Book"
                        opening_name = name
                        # Book moves are perfect
                        summary_counts[side]["Book"] += 1
                    else:
                        in_book = False
                        
                # Accuracy Calculation

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
                    
                    # ACPL-based Accuracy
                    # Formula: 100 * exp(-0.004 * acpl)
                    # This ensures better play (lower ACPL) always gives higher accuracy.
                    acpl = summary_counts[side]["acpl"]
                    accuracy = 100 * math.exp(-0.004 * acpl)
                    summary_counts[side]["accuracy"] = accuracy
                    
                else:
                    summary_counts[side]["accuracy"] = 0
                
                # Clean up temp list
                # del summary_counts[side]["accuracies"] # Keep for debugging

            # Populate summary
            game_analysis.summary = summary_counts
            game_analysis.metadata.opening = opening_name
            logger.info("Analysis complete.")

        except Exception as e:
            logger.error(f"Analysis failed: {e}", exc_info=True)
            raise e
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
            
        # Check Book Move (handled in analyze_game loop now, but good to have helper check if needed)
        # Actually, classification is overwritten in analyze_game loop if Book.
        # But we should probably check it here if we want clean logic.
        # However, we don't have access to book_manager here easily unless we pass it or use self.
        # Let's rely on the loop check for Book.
            
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
