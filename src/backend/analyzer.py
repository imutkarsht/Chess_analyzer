import chess
import chess.engine
from .models import GameAnalysis, MoveAnalysis
from .engine import EngineManager
from .cache import AnalysisCache
from .book import BookManager
from .game_history import GameHistoryManager
from ..utils.logger import logger
from typing import Optional, List, Dict
import math

class Analyzer:
    def __init__(self, engine_manager: EngineManager):
        self.engine_manager = engine_manager
        self.cache = AnalysisCache()
        self.book_manager = BookManager()
        self.history_manager = GameHistoryManager()
        self.config = {
            "time_per_move": None,
            "depth": 18,
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
        if mate is not None and mate != 0:
            # Mate in X. 
            if mate > 0:
                return 1.0
            elif mate < 0:
                return 0.0
            # If mate is 0, fall through to cp logic (which will have large value)

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
            total_moves = len(game_analysis.moves)
            
            for i, move_data in enumerate(game_analysis.moves):
                if callback:
                    callback(i, total_moves)
                
                # Log progress less frequently
                if i % 20 == 0:
                    logger.debug(f"Analyzing move {i+1}/{total_moves}")
                
                # 1. Analyze position BEFORE move
                board.set_fen(move_data.fen_before)
                is_white_turn = board.turn
                
                # Check cache
                cached_result = None
                if self.config.get("use_cache", True):
                    cached_result = self.cache.get_analysis(move_data.fen_before, self.config)
                    if cached_result:
                        logger.debug("Analysis cache hit.")
                    else:
                        logger.debug("Analysis cache miss.")
                
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
                                cp = score.relative.score(mate_score=100000)
                            else:
                                cp = score.relative.score(mate_score=100000)
                                
                    pv_data["pv"] = pv_uci
                    pv_data["cp"] = cp
                    pv_data["mate"] = mate
                    
                    # Convert PV to SAN
                    san_pv = ""
                    try:
                        # Optimization: Only convert if needed or use lighter method?
                        # For now, keep as is but catch errors silently
                        real_pv_moves = []
                        for m in pv_uci: # Use UCI strings which are available in both cases
                             real_pv_moves.append(chess.Move.from_uci(m))
                                
                        san_pv = board.variation_san(real_pv_moves)
                    except Exception:
                        san_pv = " ".join(pv_uci)
                        
                    pv_data["pv_san"] = san_pv
                    
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
            if game_analysis.moves:
                board.set_fen(game_analysis.moves[-1].fen_before)
                board.push_uci(game_analysis.moves[-1].uci)
                final_info_list = self.engine_manager.analyze_position(
                    board, 
                    time_limit=self.config["time_per_move"],
                    depth=self.config["depth"],
                    multi_pv=self.config["multi_pv"]
                )
                
                if isinstance(final_info_list, list):
                    final_info = final_info_list[0] if final_info_list else {}
                else:
                    final_info = final_info_list
                    
                final_score = final_info.get("score")
            else:
                final_score = None
            
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
                
                self._classify_move(move, wpl, side, move_data.multi_pvs)
                
                # Update stats
                summary_counts[side][move.classification] += 1
                summary_counts[side]["move_count"] += 1
                
                # ACPL
                # CP Loss relative to player
                cp_loss = 0
                
                # Helper to convert score to CP
                def get_cp(cp, mate):
                    if mate is not None:
                        # Mate in X. Positive mate = Winning.
                        # We cap at 2000 CP for calculation
                        return 2000 if mate > 0 else -2000
                    return cp if cp is not None else 0

                val_s1 = get_cp(s1_cp, s1_mate)
                val_s2 = get_cp(s2_cp, s2_mate)
                
                if side == "white":
                    cp_loss = val_s1 - val_s2
                else:
                    cp_loss = val_s2 - val_s1
                
                # Clamp loss to 0 (we don't count improvements as negative loss for ACPL)
                if cp_loss < 0: cp_loss = 0
                
                # Cap single move loss to avoid skewing (e.g. 1000)
                if cp_loss > 1000: cp_loss = 1000
                
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
                    # Formula: 100 * exp(-0.005 * acpl)
                    # This ensures better play (lower ACPL) always gives higher accuracy.
                    acpl = summary_counts[side]["acpl"]
                    accuracy = 100 * math.exp(-0.004 * acpl)
                    summary_counts[side]["accuracy"] = accuracy
                    logger.debug(f"Side: {side}, Avg ACPL: {acpl}, Accuracy: {accuracy}")
                    
                else:
                    summary_counts[side]["accuracy"] = 0
                
            # Populate summary
            game_analysis.summary = summary_counts
            game_analysis.metadata.opening = opening_name
            
            # Save to history
            if game_analysis.pgn_content:
                self.history_manager.save_game(game_analysis, game_analysis.pgn_content)
            
            logger.info("Analysis complete.")

        except Exception as e:
            logger.error(f"Analysis failed: {e}", exc_info=True)
            raise e
        finally:
            self.engine_manager.stop_engine()

        # Thresholds for WPL (tuned for Chess.com-like feel)
        if wpl >= 0.20:
            move.classification = "Blunder"
        elif wpl >= 0.09:
            move.classification = "Mistake"
        elif wpl >= 0.04:
            move.classification = "Inaccuracy"
        elif wpl >= 0.01:
            move.classification = "Good"
        elif wpl >= 0.00:
            # If it's effectively 0 loss but not the absolute best move (engine nuance), it's Excellent
            # If it is the best move (checked above), it returns early.
            # But wait, we return early for "Best".
            # So here we are strictly worse than Best.
            move.classification = "Excellent"
        else:
            move.classification = "Best"



    def _classify_move(self, move: MoveAnalysis, wpl: float, side: str, multi_pvs: List[Dict] = None):
        """
        Classifies a move based on Win Probability Loss (WPL).
        """
        # Special Case: Missed Win
        # If we had a winning position (> 80%) and dropped to Drawish or Losing (< 60%)
        player_wc_before = move.win_chance_before if side == "white" else (1.0 - move.win_chance_before)
        player_wc_after = move.win_chance_after if side == "white" else (1.0 - move.win_chance_after)
        
        if player_wc_before > 0.80 and player_wc_after < 0.60:
            move.classification = "Miss"
            move.explanation = f"Missed win (Win chance dropped by {wpl*100:.1f}%)"
            return
            
        # Checkmate Check
        # If this move delivers checkmate (win chance after is 1.0 and mate is detected)
        # We need to check if the move itself is a mate.
        # The engine analysis for THIS move (s2) should show mate.
        if move.eval_after_mate is not None and move.eval_after_mate > 0:
             # It is a winning mate for the side that moved
             move.classification = "Best" # Or Brilliant if it was hard to find?
             return

        # If it's the best move
        if move.uci == move.best_move:
            # Check for "Great" move
            # If this is the only good move (second best move is significantly worse)
            if multi_pvs and len(multi_pvs) > 1:
                # Calculate WPL for second best move
                # We need s1 (current position) and s2 (second best move)
                # s1 is already known implicitly, but we need to recalculate or pass it?
                # Actually, we can just compare win probabilities of best vs second best.
                # wp_best = move.win_chance_after
                
                # Get second best score
                sb_data = multi_pvs[1]
                sb_cp = sb_data.get("cp")
                sb_mate = sb_data.get("mate")
                
                # If sb_cp is None and sb_mate is None, we can't judge.
                if sb_cp is not None or sb_mate is not None:
                    # Calculate wp for second best
                    # Note: These scores are from engine, so they are relative to side to move (which is 'side')
                    # We need to convert to white perspective for get_win_probability?
                    # No, get_win_probability takes raw cp/mate.
                    # Wait, get_win_probability expects absolute CP? 
                    # No, the formula uses CP. If CP is positive, win% > 50.
                    # So we should pass CP relative to the side to move?
                    # In analyze_game loop:
                    # s2_cp = next_move.eval_before_cp (Normalized to White)
                    # Here sb_cp is from multi_pvs, which is usually relative to side to move.
                    # Let's normalize to White perspective.
                    
                    norm_sb_cp = sb_cp
                    norm_sb_mate = sb_mate
                    
                    if side == "black":
                        if norm_sb_cp is not None: norm_sb_cp = -norm_sb_cp
                        if norm_sb_mate is not None: norm_sb_mate = -norm_sb_mate
                        
                    sb_wp = self.get_win_probability(norm_sb_cp, norm_sb_mate)
                    
                    # Win prob relative to player
                    player_sb_wp = sb_wp if side == "white" else (1.0 - sb_wp)
                    player_best_wp = move.win_chance_after if side == "white" else (1.0 - move.win_chance_after)
                    
                    # Difference
                    diff = player_best_wp - player_sb_wp
                    
                    # If difference is significant (e.g. > 15%) and best move is winning/good
                    if diff > 0.15:
                        move.classification = "Great"
                        return

            move.classification = "Best"
            return
            
        # Thresholds for WPL
        
        # Missed Mate
        # If we had a forced mate and lost it
        if move.eval_before_mate is not None and move.eval_before_mate > 0:
            if move.eval_after_mate is None or move.eval_after_mate <= 0:
                move.classification = "Miss"
                move.explanation = "Missed a forced checkmate."
                return

        # Missed Win (Miss)
        # If we were winning (>80%) and now we are not (<60%)
        # Or if we were winning (>70%) and lost significant advantage (>20%)
        if (move.win_chance_before > 0.8 and move.win_chance_after < 0.6) or \
           (move.win_chance_before > 0.7 and wpl > 0.20):
            move.classification = "Miss"
            move.explanation = "Missed a winning opportunity."
            return

        if wpl >= 0.20:
            move.classification = "Blunder"
        elif wpl >= 0.09:
            move.classification = "Mistake"
        elif wpl >= 0.04:
            move.classification = "Inaccuracy"
        elif wpl >= 0.01:
            move.classification = "Good"
        else:
            move.classification = "Excellent"
            
        move.explanation = f"Win chance dropped by {wpl*100:.1f}%"
