import chess
import chess.engine
from .models import GameAnalysis, MoveAnalysis
from .engine import EngineManager
from .cache import AnalysisCache
from .book import BookManager
from .game_history import GameHistoryManager
from ..utils.logger import logger
from ..utils.config import ConfigManager
from typing import Optional, List, Dict
import math

class Analyzer:
    def __init__(self, engine_manager: EngineManager):
        self.engine_manager = engine_manager
        self.cache = AnalysisCache()
        self.book_manager = BookManager()
        self.history_manager = GameHistoryManager()
        self.config_manager = ConfigManager()
        self.config = {
            "time_per_move": None,
            "depth": self.config_manager.get("analysis_depth", 18),
            "multi_pv": 3,
            "use_cache": True
        }

    def get_win_probability(self, cp: Optional[int], mate: Optional[int]) -> float:
        """
        Calculates win probability from centipawns or mate score.
        Returns value between 0.0 and 1.0.
        """
        if mate is not None:
            # Mate in X
            if mate > 0:
                return 1.0
            elif mate < 0:
                return 0.0
            else:
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
        Calculates accuracy of a single move.
        Based on Lichess formula but with stricter decay to match Chess.com better.
        """
        wp_before = win_prob_before * 100.0
        wp_after = win_prob_after * 100.0
        
        diff = wp_before - wp_after
        if diff <= 0:
            return 100.0  # Improvement or equal = perfect accuracy
        
        # Moderate decay constant (0.05) - between Lichess and Chess.com
        raw = 103.1668 * math.exp(-0.05 * diff) - 3.1669
        
        return max(0.0, min(100.0, raw))

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
            logger.info(f"Analysis started: {game_analysis.metadata.white} vs {game_analysis.metadata.black}")
            
            # 1. Analyze positions (Engine work)
            summary_counts = self._analyze_positions(game_analysis, callback)
            
            # 2. Populate stats
            game_analysis.summary = summary_counts
            
            # 3. Save to history
            if game_analysis.pgn_content:
                self.history_manager.save_game(game_analysis, game_analysis.pgn_content)
                logger.info("Game saved to history")
            
            logger.info("Analysis complete")

        except Exception as e:
            logger.error(f"Analysis failed: {e}")
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
                "acpl": 0, "move_count": 0, "accuracies": [], "win_percents": []
            },
            "black": {
                "Brilliant": 0, "Great": 0, "Best": 0, "Excellent": 0, "Good": 0,
                "Inaccuracy": 0, "Mistake": 0, "Blunder": 0, "Miss": 0, "Book": 0,
                "acpl": 0, "move_count": 0, "accuracies": [], "win_percents": []
            }
        }
        
        in_book = True
        opening_name = "Unknown Opening"

        for i, move_data in enumerate(game_analysis.moves):
            if callback:
                callback(i, total_moves)
            
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
        
        # Log classification summary
        self._log_classification_summary(summary_counts)
        
        return summary_counts
    
    def _log_classification_summary(self, summary_counts: Dict):
        """Logs a summary of move classifications and accuracy."""
        for side in ["white", "black"]:
            s = summary_counts[side]
            acc = s.get('accuracy', 0)
            acpl = s.get('acpl', 0)
            mc = s['move_count']
            
            # Build compact classification string
            classes = []
            for cls in ["Brilliant", "Great", "Best", "Excellent", "Good", "Book", "Inaccuracy", "Mistake", "Miss", "Blunder"]:
                count = s.get(cls, 0)
                if count > 0:
                    classes.append(f"{cls}:{count}")
            class_str = ", ".join(classes) if classes else "None"
            
            logger.info(f"{side.capitalize()}: {mc} moves, {acc:.1f}% accuracy, ACPL {acpl:.1f} | {class_str}")
        
    def _get_position_analysis(self, board, move_data) -> List:
        """Gets analysis from cache or engine for the current position."""
        # Check cache
        if self.config.get("use_cache", True):
            cached_result = self.cache.get_analysis(move_data.fen_before, self.config)
            if cached_result:
                return cached_result
        
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
        """Analyzes the final position of the game and returns the score."""
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
        
        # Return the score object so it can be used for last move's eval_after
        return final_info.get("score") if final_info else None
            
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
            
            # Book Check (do this before accuracy so we can adjust accuracy for book moves)
            is_book_move = False
            if in_book:
                in_book, opening_name = self._check_book_move(move, side, summary_counts)
                if opening_name:
                    game_analysis.metadata.opening = opening_name
                is_book_move = (move.classification == "Book")
                    
            # Accuracy Calculation
            player_wp_before = wp_before if side == "white" else (1.0 - wp_before)
            player_wp_after = wp_after if side == "white" else (1.0 - wp_after)
            
            # Calculate raw accuracy
            move_acc = self._calculate_move_accuracy(player_wp_before, player_wp_after)
            
            # Override accuracy for special cases:
            # 1. Book moves get 100% (theoretical opening theory)
            # 2. Checkmate moves get 100% (delivering mate is optimal)
            # 3. Moves leading to forced mate get 100%
            # 4. Best moves get at least 80% (engine's top choice)
            # 5. All moves get minimum 10% floor (prevent harmonic mean collapse)
            is_checkmate_move = move.san.endswith('#') if move.san else False
            is_mating_move = (move.eval_after_mate is not None and 
                             ((side == "white" and move.eval_after_mate > 0) or
                              (side == "black" and move.eval_after_mate < 0)))
            
            if is_book_move:
                move_acc = 100.0
            elif is_checkmate_move or is_mating_move:
                move_acc = 100.0
            elif move.classification in ["Best", "Great"]:
                # Engine's best moves should get at least 80% accuracy
                move_acc = max(move_acc, 80.0)
            
            # Apply minimum floor to prevent harmonic mean collapse from outliers
            move_acc = max(move_acc, 10.0)
            
            summary_counts[side]["accuracies"].append(move_acc)
            summary_counts[side]["win_percents"].append(player_wp_before)  # Store for volatility
            
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
        """
        Calculates final game accuracy using Lichess algorithm:
        Average of volatility-weighted mean and harmonic mean.
        
        Source: https://github.com/lichess-org/lila/blob/master/modules/analyse/src/main/AccuracyPercent.scala
        """
        for side in ["white", "black"]:
            accuracies = summary_counts[side]["accuracies"]
            win_percents = summary_counts[side]["win_percents"]
            mc = summary_counts[side]["move_count"]
            
            if mc > 0:
                # Calculate ACPL for stats display
                summary_counts[side]["acpl"] /= mc
                
                if len(accuracies) >= 2:
                    # Cap minimum accuracy to prevent div-by-zero in harmonic mean
                    capped_accs = [max(a, 0.1) for a in accuracies]
                    
                    # Calculate sliding window volatility weights
                    window_size = max(2, min(8, len(accuracies) // 10))
                    weights = self._calculate_volatility_weights(win_percents, window_size)
                    
                    # Volatility-weighted mean
                    weighted_mean = self._weighted_mean(capped_accs, weights)
                    
                    # Harmonic mean
                    harmonic_mean = self._harmonic_mean(capped_accs)
                    
                    # Final accuracy = average of both
                    accuracy = (weighted_mean + harmonic_mean) / 2
                elif len(accuracies) == 1:
                    accuracy = accuracies[0]
                else:
                    accuracy = 0
                
                summary_counts[side]["accuracy"] = max(0, min(100, accuracy))
            else:
                summary_counts[side]["accuracy"] = 0
    
    def _calculate_volatility_weights(self, win_percents: List[float], window_size: int) -> List[float]:
        """
        Calculates volatility weights based on sliding window standard deviation.
        Higher volatility = higher weight (more important positions).
        """
        if len(win_percents) < window_size:
            return [1.0] * len(win_percents)
        
        # Create windows - pad the beginning with copies of the first window
        wp_values = [wp * 100 for wp in win_percents]  # Convert to percentage
        
        windows = []
        # Pad beginning
        first_window = wp_values[:window_size] if len(wp_values) >= window_size else wp_values
        for _ in range(min(window_size - 1, len(wp_values))):
            windows.append(first_window)
        
        # Sliding windows
        for i in range(len(wp_values) - window_size + 1):
            windows.append(wp_values[i:i + window_size])
        
        # Ensure we have exactly the right number of windows
        windows = windows[:len(win_percents)]
        
        # Calculate standard deviation for each window as the weight
        weights = []
        for window in windows:
            std_dev = self._std_dev(window)
            # Clamp weight between 0.5 and 12 (as per Lichess source)
            weight = max(0.5, min(12.0, std_dev))
            weights.append(weight)
        
        return weights
    
    def _weighted_mean(self, values: List[float], weights: List[float]) -> float:
        """Calculates weighted arithmetic mean."""
        if not values or not weights:
            return 0.0
        
        # Ensure same length
        min_len = min(len(values), len(weights))
        values = values[:min_len]
        weights = weights[:min_len]
        
        total_weight = sum(weights)
        if total_weight == 0:
            return sum(values) / len(values) if values else 0.0
        
        weighted_sum = sum(v * w for v, w in zip(values, weights))
        return weighted_sum / total_weight
    
    def _harmonic_mean(self, values: List[float]) -> float:
        """Calculates harmonic mean, handling zeros gracefully."""
        if not values:
            return 0.0
        
        # Filter out zeros/negatives to avoid division errors
        positive_values = [v for v in values if v > 0]
        if not positive_values:
            return 0.0
        
        reciprocal_sum = sum(1.0 / v for v in positive_values)
        return len(positive_values) / reciprocal_sum
    
    def _std_dev(self, values: List[float]) -> float:
        """Calculates standard deviation."""
        if len(values) < 2:
            return 0.0
        
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        return math.sqrt(variance)




    def _classify_move(self, move: MoveAnalysis, wpl: float, side: str, multi_pvs: List[Dict] = None):
        """
        Classifies a move based on Win Probability Loss (WPL).
        
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
        # For white: eval_after_mate > 0 means White has mate
        # For black: eval_after_mate < 0 means Black has mate
        if move.eval_after_mate is not None:
            if (side == "white" and move.eval_after_mate > 0) or \
               (side == "black" and move.eval_after_mate < 0):
                move.classification = "Best"
                move.explanation = "Delivered checkmate!"
                return
        
        # Also check if position after is completely won (mate in X)
        if player_wc_after >= 0.99:
            move.classification = "Best"
            move.explanation = "Winning position maintained."
            return
            
        # ============ PRIORITY 2: Best Move Check ============
        if move.uci == move.best_move:
            # Check for "Brilliant" or "Great" move - significantly better than alternatives
            if multi_pvs and len(multi_pvs) > 1:
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
                        
                    sb_wp = self.get_win_probability(norm_sb_cp, norm_sb_mate)
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
            
        # ============ PRIORITY 3: Missed Forced Mate ============
        # Player had mate before but doesn't after
        player_had_mate = (move.eval_before_mate is not None and 
                          ((side == "white" and move.eval_before_mate > 0) or
                           (side == "black" and move.eval_before_mate < 0)))
        player_has_mate = (move.eval_after_mate is not None and
                          ((side == "white" and move.eval_after_mate > 0) or
                           (side == "black" and move.eval_after_mate < 0)))
        
        if player_had_mate and not player_has_mate:
            move.classification = "Miss"
            move.explanation = "Missed a forced checkmate."
            return

        # ============ PRIORITY 4: Missed Winning Position ============
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

        # ============ PRIORITY 5: WPL-Based Classification ============
        # Thresholds tuned to match Chess.com more closely
        # Raised thresholds to reduce over-classification of inaccuracies
        if wpl >= 0.20:
            move.classification = "Blunder"
            move.explanation = f"Lost {wpl*100:.1f}% winning chances."
        elif wpl >= 0.10:
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

