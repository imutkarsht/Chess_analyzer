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
                # Mate is 0 (Immediate checkmate).
                # This should physically imply the game is over.
                # If we are strictly evaluating a position where someone HAS been checkmated, 
                # the side whose turn it is loses.
                # The score is usually relative to side to move (which is the loser).
                # So relative mate is -0 (or 0 but implies loss).
                # We return 0.0 (Win prob for side to move is 0).
                return 0.0

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

    @staticmethod
    def _get_cp(cp, mate):
        """Convert score to centipawns, capping mate values."""
        if mate is not None:
            return 2000 if mate > 0 else -2000
        return cp if cp is not None else 0

    def analyze_game(self, game_analysis: GameAnalysis, callback=None):
        """
        Analyzes a game structure in-place.
        """
        try:
            # 1. Analyze positions (Engine work)
            summary_counts = self._analyze_positions(game_analysis, callback)
            
            # 2. Populate stats
            game_analysis.summary = summary_counts
            
            # 3. Save to history
            if game_analysis.pgn_content:
                self.history_manager.save_game(game_analysis, game_analysis.pgn_content)
            
            logger.info("Analysis complete.")

        except Exception as e:
            logger.error(f"Analysis failed: {e}", exc_info=True)
            raise e
        finally:
            self.engine_manager.stop_engine()

    def _analyze_positions(self, game_analysis: GameAnalysis, callback=None) -> Dict:
        """
        Runs the engine analysis loop for all moves in the game.
        Returns the raw summary counts/stats.
        """
        logger.info(f"Starting analysis for game: {game_analysis.game_id}")
        self.engine_manager.start_engine()
        
        board = chess.Board()
        total_moves = len(game_analysis.moves)
        
        # Initialize stats container
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
        
        in_book = True
        opening_name = "Unknown Opening"

        for i, move_data in enumerate(game_analysis.moves):
            if callback:
                callback(i, total_moves)
            
            if i % 20 == 0:
                logger.debug(f"Analyzing move {i+1}/{total_moves}")
            
            # 1. Analyze position BEFORE move
            board.set_fen(move_data.fen_before)
            is_white_turn = board.turn
            
            # Get Engine/Cache Analysis for this position
            info_list = self._get_position_analysis(board, move_data)
            
            # Process analysis results
            self._process_analysis_results(move_data, info_list, is_white_turn)
            
        # Analyze FINAL position
        final_score = self._analyze_final_position(game_analysis, board)
        
        # Classify moves and calculate stats
        self._classify_and_calculate_stats(game_analysis, summary_counts, final_score)
        
        # Calculate final accuracy
        self._calculate_final_accuracy(summary_counts)
        
        return summary_counts
        
    def _get_position_analysis(self, board, move_data) -> List:
        """Gets analysis from cache or engine for the current position."""
        # Check cache
        if self.config.get("use_cache", True):
            cached_result = self.cache.get_analysis(move_data.fen_before, self.config)
            if cached_result:
                logger.debug("Analysis cache hit.")
                return cached_result
            else:
                logger.debug("Analysis cache miss.")
        
        # Engine analysis
        info_list = self.engine_manager.analyze_position(
            board, 
            time_limit=self.config["time_per_move"],
            depth=self.config["depth"],
            multi_pv=self.config["multi_pv"]
        )
        
        # Ensure list
        if not isinstance(info_list, list):
            info_list = [info_list]
        
        # Serialize and cache
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
            
        return info_list

    def _process_analysis_results(self, move_data: MoveAnalysis, info_list: List, is_white_turn: bool):
        """Processes raw engine analysis into move data."""
        # Normalize info
        best_pv_uci = []
        score_cp = None
        score_mate = None
        
        # Process Multi-PVs
        move_data.multi_pvs = []
        
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
            
            # Convert PV to SAN (simplified for robustness)
            pv_data["pv_san"] = " ".join(pv_uci)
            
            pv_data["score_value"] = f"M{mate}" if mate is not None else f"{cp/100:.2f}" if cp is not None else "?"
            
            move_data.multi_pvs.append(pv_data)
            
            if idx == 0:
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

    def _analyze_final_position(self, game_analysis: GameAnalysis, board: chess.Board):
        """Analyzes the final position of the game."""
        if not game_analysis.moves:
            return None
            
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
            
    def _classify_and_calculate_stats(self, game_analysis: GameAnalysis, summary_counts: Dict, final_score):
        """Iterates through moves to calculate win probabilities, classification, and ACPL."""
        board = chess.Board() # For turn tracking
        temp_board = chess.Board() # For FEN checks
        
        in_book = True
        
        for i, move in enumerate(game_analysis.moves):
            # Determine side
            temp_board.set_fen(move.fen_before)
            side = "white" if temp_board.turn == chess.WHITE else "black"
            
            # S1 (Eval before)
            s1_cp = move.eval_before_cp
            s1_mate = move.eval_before_mate
            
            # S2 (Eval after)
            s2_cp, s2_mate = self._get_next_eval(game_analysis, i, final_score, board)

            # Store eval_after
            move.eval_after_cp = s2_cp
            move.eval_after_mate = s2_mate
            
            # Win Probabilities
            wp_before = self.get_win_probability(s1_cp, s1_mate)
            wp_after = self.get_win_probability(s2_cp, s2_mate)
            
            move.win_chance_before = wp_before
            move.win_chance_after = wp_after
            
            # Win Probability Loss
            if side == "white":
                wpl = wp_before - wp_after
            else:
                wpl = wp_after - wp_before
            
            if wpl < 0: wpl = 0
            
            # Classification
            self._classify_move(move, wpl, side, move.multi_pvs)
            
            # Update counts
            summary_counts[side][move.classification] += 1
            summary_counts[side]["move_count"] += 1
            
            # ACPL
            self._update_acpl(summary_counts, side, s1_cp, s1_mate, s2_cp, s2_mate)
            
            # Book Check
            if in_book:
                in_book, opening_name = self._check_book_move(move, side, summary_counts)
                if opening_name:
                    game_analysis.metadata.opening = opening_name
                    
            # Accuracy
            player_wp_before = wp_before if side == "white" else (1.0 - wp_before)
            player_wp_after = wp_after if side == "white" else (1.0 - wp_after)
            move_acc = self._calculate_move_accuracy(player_wp_before, player_wp_after)
            summary_counts[side]["accuracies"].append(move_acc)
            
            # Advance board for turn tracking for next move logic
            board.set_fen(move.fen_before)
            board.push_uci(move.uci)

    def _get_next_eval(self, game_analysis, index, final_score, current_board_context):
        """Determines the evaluation of the position AFTER the move."""
        if index < len(game_analysis.moves) - 1:
            next_move = game_analysis.moves[index+1]
            return next_move.eval_before_cp, next_move.eval_before_mate
        else:
            # Final position
            if final_score:
                if final_score.is_mate():
                    s2_mate = final_score.relative.mate()
                    s2_cp = None
                else:
                    s2_cp = final_score.relative.score(mate_score=10000)
                    s2_mate = None
                    
                # Normalize (relative to side to move after last move)
                if current_board_context.turn == chess.BLACK:
                        if s2_cp is not None: s2_cp = -s2_cp
                        if s2_mate is not None: s2_mate = -s2_mate
                return s2_cp, s2_mate
            else:
                return None, None

    def _update_acpl(self, summary_counts, side, s1_cp, s1_mate, s2_cp, s2_mate):
        """Calculates and updates ACPL stats."""
        val_s1 = self._get_cp(s1_cp, s1_mate)
        val_s2 = self._get_cp(s2_cp, s2_mate)
        
        if side == "white":
            cp_loss = val_s1 - val_s2
        else:
            cp_loss = val_s2 - val_s1
        
        if cp_loss < 0: cp_loss = 0
        if cp_loss > 1000: cp_loss = 1000
        
        summary_counts[side]["acpl"] += cp_loss

    def _check_book_move(self, move, side, summary_counts):
        """Checks and updates book move status. Returns (in_book, opening_name)."""
        name = self.book_manager.get_opening_name(move.fen_before, move.uci)
        if name:
            summary_counts[side][move.classification] -= 1
            move.classification = "Book"
            summary_counts[side]["Book"] += 1
            return True, name
        return False, None

    def _calculate_final_accuracy(self, summary_counts):
        """Calculates final game accuracy based on ACPL."""
        for side in ["white", "black"]:
            mc = summary_counts[side]["move_count"]
            if mc > 0:
                summary_counts[side]["acpl"] /= mc
                acpl = summary_counts[side]["acpl"]
                accuracy = 100 * math.exp(-0.004 * acpl)
                summary_counts[side]["accuracy"] = accuracy
                logger.debug(f"Side: {side}, Avg ACPL: {acpl}, Accuracy: {accuracy}")
            else:
                summary_counts[side]["accuracy"] = 0




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
