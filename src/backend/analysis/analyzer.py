import chess
import chess.engine
import os
from src.backend.storage.models import GameAnalysis, MoveAnalysis
from .engine import EngineManager
from src.backend.storage.cache import AnalysisCache
from .local_book import LocalBookManager
from .opening_db import OpeningDB
from src.backend.storage.game_history import GameHistoryManager
from src.utils.logger import logger
from src.utils.config import ConfigManager
from src.utils.path_utils import get_resource_path, get_user_data_dir
from typing import Optional, List, Dict
import math

from .math_utils import (
    get_win_probability,
    calculate_move_accuracy,
    get_cp,
    calculate_volatility_weights,
    weighted_mean,
    harmonic_mean
)
from .move_classifier import classify_move

class Analyzer:
    def __init__(self, engine_manager: EngineManager):
        self.engine_manager = engine_manager
        self.cache = AnalysisCache()
        self.history_manager = GameHistoryManager()
        self.config_manager = ConfigManager()

        tsv_dir = get_resource_path("assets/openings")
        db_path = os.path.join(get_user_data_dir(), "openings.db")
        self._opening_db = OpeningDB(db_path)
        try:
            self._opening_db.initialize(tsv_dir)
        except FileNotFoundError:
            logger.warning(f"Opening TSV files not found in {tsv_dir}; book detection disabled")
        self.local_book = LocalBookManager(self._opening_db)
        logger.info(f"Opening book initialized: local SQLite at {db_path} ({'populated' if self._opening_db.is_populated() else 'empty'})")
        self.config = {
            "time_per_move": None,
            "depth": self.config_manager.get("analysis_depth", 18),
            # multi_pv is read from user config (default 1) so the same
            # default applies to the Game Analysis tab.  See issue #5:
            # the previous hard-coded 3 was identified as a primary cause
            # of laptop overheating because evaluating 3 PVs roughly
            # triples the search tree.
            "multi_pv": self.config_manager.get("multi_pv", 1),
            "use_cache": True
        }

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
        # Refresh configuration from global settings before starting
        self.config["depth"] = self.config_manager.get("analysis_depth", 18)
        self.config["multi_pv"] = self.config_manager.get("multi_pv", 1)
        
        logger.info(f"Starting analysis for game: {game_analysis.game_id} (Depth: {self.config['depth']}, Multi-PV: {self.config['multi_pv']})")
        self.engine_manager.start_engine()
        
        is_chess960 = game_analysis.metadata.chess960
        if is_chess960:
            self.engine_manager.set_chess960_mode(True)
        
        board = chess.Board(chess960=is_chess960)
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
            move_idx = i + 1
            if move_idx == 1 or move_idx % 10 == 0 or move_idx == total_moves:
                logger.info(f"Analyzing move {move_idx}/{total_moves}...")
            
            if callback:
                callback(i+1, total_moves)
            
            # 1. Analyze position BEFORE move
            board.set_fen(move_data.fen_before)
            is_white_turn = board.turn
            
            # Get Engine/Cache Analysis for this position
            info_list = self._get_position_analysis(board, move_data)
            
            # Process analysis results
            self._process_analysis_results(move_data, info_list, is_white_turn, board)
            
        # Analyze FINAL position
        logger.info("Analyzing final position...")
        if callback:
            callback(total_moves + 1, total_moves)
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
            s_info["depth"] = info.get("depth", self.config["depth"])
            serializable_list.append(s_info)
        
        if self.config.get("use_cache", True):
            self.cache.save_analysis(move_data.fen_before, self.config, serializable_list)
            
        return info_list

    def _process_analysis_results(self, move_data: MoveAnalysis, info_list: List, is_white_turn: bool, board: chess.Board):
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
                depth = item.get("depth", "?")
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
                depth = item.get("depth", "?")
                        
            pv_data["pv"] = pv_uci
            pv_data["cp"] = cp
            pv_data["mate"] = mate
            pv_data["depth"] = depth
            
            # Convert PV to SAN
            try:
                pv_moves_obj = [chess.Move.from_uci(uci) for uci in pv_uci]
                pv_data["pv_san"] = board.variation_san(pv_moves_obj)
            except Exception:
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
        
        if board.is_game_over():
            if board.is_checkmate():
                return chess.engine.PovScore(chess.engine.Mate(0), board.turn)
            else:
                return chess.engine.PovScore(chess.engine.Cp(0), board.turn)
                
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
        is_chess960 = game_analysis.metadata.chess960
        board = chess.Board(chess960=is_chess960) # For turn tracking
        temp_board = chess.Board(chess960=is_chess960) # For FEN checks
        
        # Rebuild FEN history to detect repetitions in drawn games
        is_draw = game_analysis.metadata.result in ["1/2-1/2", "Draw"]
        clean_fens = []
        if is_draw and game_analysis.moves:
            rep_board = chess.Board(chess960=is_chess960)
            clean_fens.append(" ".join(rep_board.fen().split()[:4]))
            for m in game_analysis.moves:
                rep_board.set_fen(m.fen_before)
                try:
                    rep_board.push_uci(m.uci)
                    clean_fens.append(" ".join(rep_board.fen().split()[:4]))
                except Exception:
                    clean_fens.append("")
            
            # Count occurrences of each clean FEN
            fen_counts = {}
            for fen in clean_fens:
                if fen:
                    fen_counts[fen] = fen_counts.get(fen, 0) + 1
        else:
            fen_counts = {}
            
        self.local_book.reset()
        has_recorded_exit = False

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
            wp_before = get_win_probability(s1_cp, s1_mate)
            
            # Check if this move is checkmate
            is_checkmate_move = move.san.endswith('#') if move.san else False
            if is_checkmate_move:
                wp_after = 1.0 if side == "white" else 0.0
            else:
                wp_after = get_win_probability(s2_cp, s2_mate)
                
            # Check if this move is protected due to drawing repetition
            is_protected_repetition = False
            if is_draw and clean_fens:
                fen_before = clean_fens[i]
                # 1. FEN before has occurred more than once in the game
                if fen_before and fen_counts.get(fen_before, 0) > 1:
                    is_protected_repetition = True
                else:
                    # 2. Within 2 plies of a repeated FEN
                    for offset in range(-2, 3):
                        idx = i + offset
                        if 0 <= idx < len(clean_fens):
                            f = clean_fens[idx]
                            if f and fen_counts.get(f, 0) > 1:
                                player_wp_before = wp_before if side == "white" else (1.0 - wp_before)
                                if player_wp_before < 0.70:
                                    is_protected_repetition = True
                                    break
                                    
            if is_protected_repetition:
                wp_after = wp_before
            
            move.win_chance_before = wp_before
            move.win_chance_after = wp_after
            
            # Win Probability Loss
            if side == "white":
                wpl = wp_before - wp_after
            else:
                wpl = wp_after - wp_before
            
            if wpl < 0: wpl = 0
            
            # Classification
            classify_move(move, wpl, side, move.multi_pvs)
            
            # Update counts
            summary_counts[side][move.classification] += 1
            summary_counts[side]["move_count"] += 1
            
            # ACPL
            self._update_acpl(summary_counts, side, s1_cp, s1_mate, s2_cp, s2_mate)
            
            # Book Check (do this before accuracy so we can adjust accuracy for book moves)
            is_book_move = self._check_book_move(move, side, summary_counts, game_analysis)
            if not is_book_move and not has_recorded_exit and not move.book_exit_move:
                move.book_exit_move = True
                has_recorded_exit = True
                    
            # Accuracy Calculation
            player_wp_before = wp_before if side == "white" else (1.0 - wp_before)
            player_wp_after = wp_after if side == "white" else (1.0 - wp_after)
            
            # Calculate raw accuracy
            move_acc = calculate_move_accuracy(player_wp_before, player_wp_after)
            
            # Override accuracy for special cases:
            # 1. Book moves get 100% (theoretical opening theory)
            # 2. Checkmate moves get 100% (delivering mate is optimal)
            # 3. Moves leading to forced mate get 100%
            # 4. All moves get minimum 5% floor (prevent harmonic mean collapse)
            is_checkmate_move = move.san.endswith('#') if move.san else False
            is_mating_move = (move.eval_after_mate is not None and 
                             ((side == "white" and move.eval_after_mate > 0) or
                              (side == "black" and move.eval_after_mate < 0)))
            
            if is_book_move:
                move_acc = 100.0
            elif is_checkmate_move or is_mating_move:
                move_acc = 100.0
            
            # Apply minimum floor to prevent harmonic mean collapse from outliers
            move_acc = max(move_acc, 5.0)
            
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
            # Final position - need to figure out whose turn it is AFTER the last move
            if final_score:
                # Get the FEN after the last move to determine whose turn it is
                last_move = game_analysis.moves[index]
                temp_board = chess.Board(chess960=game_analysis.metadata.chess960)
                temp_board.set_fen(last_move.fen_before)
                temp_board.push_uci(last_move.uci)
                turn_after_last = temp_board.turn  # Who to move in final position
                
                if final_score.is_mate():
                    s2_mate = final_score.relative.mate()
                    s2_cp = None
                else:
                    s2_cp = final_score.relative.score(mate_score=10000)
                    s2_mate = None
                    
                # Normalize: score is relative to side-to-move in final position
                # We need it relative to White for consistency
                if turn_after_last == chess.BLACK:
                    # Score is relative to Black, flip to White's perspective
                    if s2_cp is not None: s2_cp = -s2_cp
                    if s2_mate is not None: s2_mate = -s2_mate
                return s2_cp, s2_mate
            else:
                return None, None
 
    def _update_acpl(self, summary_counts, side, s1_cp, s1_mate, s2_cp, s2_mate):
        """Calculates and updates ACPL stats."""
        val_s1 = get_cp(s1_cp, s1_mate)
        val_s2 = get_cp(s2_cp, s2_mate)
        
        if side == "white":
            cp_loss = val_s1 - val_s2
        else:
            cp_loss = val_s2 - val_s1
        
        if cp_loss < 0: cp_loss = 0
        if cp_loss > 1000: cp_loss = 1000
        
        summary_counts[side]["acpl"] += cp_loss
 
    def _check_book_move(self, move, side, summary_counts, game_analysis):
        """Check move against local opening tree. Returns True if it is a book move."""
        move_number = move.move_number * 2 - (1 if side == "white" else 0)
        result = self.local_book.process_move(move.fen_before, move.uci, move_number)
        if result.is_book:
            summary_counts[side][move.classification] -= 1
            move.classification = "Book"
            move.is_book_move = True
            move.book_move_count = result.book_move_count
            move.eco = result.current_eco or ""
            move.opening_name = result.current_opening or ""
            move.candidate_continuations = result.candidate_moves
            summary_counts[side]["Book"] += 1
            if result.current_opening:
                game_analysis.metadata.opening = result.current_opening
            if result.current_eco:
                game_analysis.metadata.eco = result.current_eco
        return result.is_book
 
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
                    weights = calculate_volatility_weights(win_percents, window_size)
                    
                    # Volatility-weighted mean
                    weighted_mean_val = weighted_mean(capped_accs, weights)
                    
                    # Harmonic mean
                    harmonic_mean_val = harmonic_mean(capped_accs)
                    
                    # Final accuracy = average of both
                    accuracy = (weighted_mean_val + harmonic_mean_val) / 2
                elif len(accuracies) == 1:
                    accuracy = accuracies[0]
                else:
                    accuracy = 0
                
                summary_counts[side]["accuracy"] = max(0, min(100, accuracy))
            else:
                summary_counts[side]["accuracy"] = 0

