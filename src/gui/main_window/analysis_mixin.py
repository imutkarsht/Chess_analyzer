import qtawesome as qta
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QDialog, QMessageBox

from src.backend.analysis.analyzer import Analyzer
from src.backend.analysis.engine import EngineManager, invalidate_engine_cache, resolve_engine_path
from src.gui.analysis.analysis_worker import AnalysisWorker
from src.gui.dialogs.engine_error_dialog import EngineNotFoundDialog
from src.gui.dialogs.feedback_dialog import FeedbackDialog
from src.gui.dialogs.review_prompt_dialog import ReviewPromptDialog
from src.gui.main_window.navigation_mixin import compute_clock_times
from src.gui.styles import Styles
from src.utils.logger import logger


class AnalysisMixin:
    """Full Stockfish analysis orchestration, worker callbacks, and review triggers."""

    def start_analysis(self, resume: bool | None = None):
        if not self.current_game:
            return

        if hasattr(self, "worker") and self.worker and self.worker.isRunning():
            QMessageBox.warning(self, "Analysis in Progress", "An analysis is already running.")
            return

        # Auto-detect engine if the configured path doesn't work.
        resolved = resolve_engine_path(self.config_manager, deep_probe=True)
        if resolved:
            if resolved != self.engine_path:
                self.engine_path = resolved
                self.analyzer = Analyzer(
                    EngineManager(self.engine_path, config_manager=self.config_manager)
                )
        else:
            logger.warning(f"Engine not found (configured: {self.engine_path})")
            dialog = EngineNotFoundDialog(self)
            if hasattr(self, "config_manager"):
                dialog.config_manager = lambda: self.config_manager
            if dialog.exec() == QDialog.DialogCode.Accepted:
                new_path = dialog.engine_path()
                if new_path:
                    self.config_manager.config["engine_path"] = new_path
                    self.config_manager.save_config()
                    self.engine_path = new_path
                    self.analyzer = Analyzer(
                        EngineManager(self.engine_path, config_manager=self.config_manager)
                    )
                    invalidate_engine_cache()
                    logger.info(f"Engine path set to {new_path} via error dialog")
                    self._refresh_engine_status()
            else:
                # Cancel navigates to Settings (index 4) where the engine can be configured
                self.sidebar.set_active(4)
                self.switch_page(4)
            return

        if resume is None:
            resume = getattr(self.current_game, "status", "") == "paused"

        logger.info("Starting analysis (resume=%s)...", resume)

        # If starting fresh or cache turned off, clear previous move evaluations
        if not resume or not self.analyzer.config.get("use_cache", True):
            for move in self.current_game.moves:
                move.eval_before_cp = None
                move.eval_before_mate = None
                move.eval_after_cp = None
                move.eval_after_mate = None
                move.classification = None
                move.best_move = None
                move.multi_pvs = []
                move.win_chance_before = None
                move.win_chance_after = None
                move.is_book_move = False
                move.book_move_count = 0
                move.book_exit_move = False
                move.candidate_continuations = []
            self.current_game.summary = {}
            self.current_game.ai_summary = ""

            if hasattr(self, "move_list_panel"):
                self.move_list_panel.set_game(self.current_game)
            if hasattr(self, "analysis_panel"):
                self.analysis_panel.set_game(self.current_game)

        self.worker = AnalysisWorker(self.analyzer, self.current_game, resume=resume)
        self.worker.progress.connect(self.on_analysis_progress)
        self.worker.move_analyzed.connect(self.on_move_analyzed)
        self.worker.finished.connect(self.on_analysis_finished)
        self.worker.cancelled.connect(self.on_analysis_cancelled)
        self.worker.error.connect(self.on_analysis_error)

        self._full_analysis_running = True
        self._update_analyze_button(running=True)
        self._set_engine_state("calculating", "Starting...")
        self._set_status("Starting analysis...", "progress")
        self.analysis_panel.set_analysis_running(True)

        if hasattr(self, "history_view") and self.current_game:
            self.history_view.set_analyzing_game_id(getattr(self.current_game, "game_id", None))

        if hasattr(self, "move_list_panel") and hasattr(self.move_list_panel, "live_worker"):
            self.move_list_panel.live_worker.stop()

        self.worker.start()

    def stop_analysis(self):
        """Immediately stop running analysis and preserve partial results."""
        if not getattr(self, "_full_analysis_running", False):
            return
        logger.info("MainWindow: stop_analysis requested by user.")
        self._set_status("Stopping analysis...", "warning")
        if hasattr(self, "btn_analyze"):
            self.btn_analyze.setEnabled(False)

        if hasattr(self, "worker") and self.worker and self.worker.isRunning():
            self.worker.cancel()

    def _update_analyze_button(self, running: bool):
        """Toggle the toolbar button between Analyze, Resume, Reanalyze and Stop."""
        if not hasattr(self, "btn_analyze"):
            return

        try:
            self.btn_analyze.clicked.disconnect()
        except (TypeError, RuntimeError):
            pass

        if running:
            self.btn_analyze.setText("  Stop Analysis")
            self.btn_analyze.setStyleSheet(Styles.get_danger_button_style())
            try:
                self.btn_analyze.setIcon(qta.icon("fa5s.stop", color="#ffffff"))
            except Exception:
                pass
            self.btn_analyze.clicked.connect(self.stop_analysis)
            self.btn_analyze.setEnabled(True)
        else:
            game_status = (
                getattr(self.current_game, "status", "not_started")
                if self.current_game
                else "not_started"
            )
            if game_status == "paused":
                analyzed = getattr(self.current_game, "analyzed_moves_count", 0)
                total = getattr(self.current_game, "total_moves_count", 0) or len(
                    getattr(self.current_game, "moves", [])
                )
                self.btn_analyze.setText(f"  Resume ({analyzed}/{total})")
                self.btn_analyze.setStyleSheet(Styles.get_button_style())
                try:
                    self.btn_analyze.setIcon(qta.icon("fa5s.play", color="#ffffff"))
                except Exception:
                    pass
                self.btn_analyze.clicked.connect(lambda: self.start_analysis(resume=True))
            elif game_status == "completed":
                self.btn_analyze.setText("  Reanalyze Game")
                self.btn_analyze.setStyleSheet(Styles.get_button_style())
                try:
                    self.btn_analyze.setIcon(qta.icon("fa5s.sync-alt", color="#ffffff"))
                except Exception:
                    pass
                self.btn_analyze.clicked.connect(lambda: self.start_analysis(resume=False))
            else:
                self.btn_analyze.setText("  Analyze Game")
                self.btn_analyze.setStyleSheet(Styles.get_button_style())
                try:
                    self.btn_analyze.setIcon(qta.icon("fa5s.play", color="#ffffff"))
                except Exception:
                    pass
                self.btn_analyze.clicked.connect(lambda: self.start_analysis(resume=False))
            self.btn_analyze.setEnabled(True)

    def on_analysis_progress(self, current, total):
        if current > total:
            self._set_engine_state("calculating", "Final...")
            self._set_status("Analyzing final position...", "progress")
        else:
            self._set_engine_state("calculating", f"{current}/{total}")
            self._set_status(f"Analyzing move {current} of {total}", "progress")

    def on_move_analyzed(self, move_index, data):
        """Called when a move's eval/classification data becomes available."""
        if not self.current_game:
            return
        if 0 <= move_index < len(self.current_game.moves):
            move = self.current_game.moves[move_index]
            classification = data.get("classification", move.classification)
            if classification:
                move.classification = classification
            eval_cp = data.get("eval_after_cp")
            eval_mate = data.get("eval_after_mate")
            if eval_cp is not None:
                move.eval_after_cp = eval_cp
            if eval_mate is not None:
                move.eval_after_mate = eval_mate

            self.move_list_panel.update_move_cell(move_index, classification, eval_cp, eval_mate)
            self.move_list_panel.select_move(move_index)
            self.board_widget.set_position(move_index)

            # Update clocks and captured pieces as moves stream in
            moves = self.current_game.moves
            fen = (
                moves[move_index + 1].fen_before
                if move_index + 1 < len(moves)
                else getattr(self.board_widget.board, "fen", lambda: None)()
            )
            if hasattr(self, "captured_white") and hasattr(self, "captured_black"):
                self.captured_white.update_captured(fen)
                self.captured_black.update_captured(fen)
                white_time, black_time = compute_clock_times(moves, move_index)
                self.captured_white.update_clock(white_time)
                self.captured_black.update_clock(black_time)

            if hasattr(self, "analysis_panel") and hasattr(self.analysis_panel, "graph_widget"):
                self.analysis_panel.graph_widget.plot_partial(self.current_game.moves, move_index)
                self.analysis_panel.graph_widget.set_current_move(move_index)

    def on_analysis_cancelled(self, game):
        """Handle analysis cancellation while preserving partial results."""
        self._full_analysis_running = False
        self.analysis_panel.set_analysis_running(False)
        self._set_engine_state("ready")
        self._set_status("Analysis stopped", "info")
        self.show_toast("Analysis stopped", "info")
        logger.info("Analysis cancelled; partial results preserved.")
        self.current_game = game
        if game and game.pgn_content:
            try:
                self.history_manager.save_game(game, game.pgn_content, force_overwrite=True)
            except Exception as e:
                logger.error(f"Failed saving paused game to history: {e}")
        self._update_analyze_button(running=False)

        if hasattr(self, "move_list_panel") and hasattr(self.move_list_panel, "live_worker"):
            self.move_list_panel.live_worker.start()
        self.move_list_panel.set_game(game)
        self.analysis_panel.set_game(game)

        # Find the last analyzed move to position the board
        analyzed_indices = [idx for idx, m in enumerate(game.moves) if bool(m.classification)]
        if analyzed_indices:
            last_analyzed = analyzed_indices[-1]
            self.on_move_selected(last_analyzed)
            if hasattr(self, "analysis_panel") and hasattr(self.analysis_panel, "graph_widget"):
                self.analysis_panel.graph_widget.plot_partial(game.moves, last_analyzed)
                self.analysis_panel.graph_widget.set_current_move(last_analyzed)

        if hasattr(self, "metrics_view"):
            self.metrics_view.mark_dirty()
            if self.stack.currentIndex() == 3:
                self.metrics_view.refresh(force=True)
        if hasattr(self, "history_view"):
            self.history_view.set_analyzing_game_id(None)
            self.history_view.load_history()

    def on_history_changed(self, *_):
        if hasattr(self, "metrics_view"):
            self.metrics_view.mark_dirty()
            if self.stack.currentIndex() == 3:
                self.metrics_view.refresh(force=True)

    def on_analysis_finished(self, game):
        self._full_analysis_running = False
        self.analysis_panel.set_analysis_running(False)
        self._set_engine_state("ready")
        self._set_status("Analysis complete", "success")
        self.show_toast("Analysis complete!", "success")
        logger.info("Analysis finished successfully.")
        self.current_game = game
        self._update_analyze_button(running=False)
        if hasattr(self, "move_list_panel") and hasattr(self.move_list_panel, "live_worker"):
            self.move_list_panel.live_worker.start()
        self.move_list_panel.set_game(game)
        self.analysis_panel.set_game(game)
        if game.moves and any(m.classification for m in game.moves):
            self.on_move_selected(len(game.moves) - 1)
        if hasattr(self, "metrics_view"):
            self.metrics_view.mark_dirty()
            if self.stack.currentIndex() == 3:
                self.metrics_view.refresh(force=True)
        if hasattr(self, "history_view"):
            self.history_view.set_analyzing_game_id(None)
            self.history_view.load_history()

        # Track analyzed games count and check for in-app review prompt
        count = self.config_manager.get("games_analyzed_count", 0) + 1
        self.config_manager.set("games_analyzed_count", count)

        next_prompt = self.config_manager.get("review_next_prompt_count", 3)
        reviewed = self.config_manager.get("review_submitted", False)
        dismissed = self.config_manager.get("review_prompt_dismissed", False)

        if count >= next_prompt and not reviewed and not dismissed:
            QTimer.singleShot(1500, lambda: self._prompt_review_if_active(count))

    def _prompt_review_if_active(self, count: int):
        """Display the review prompt if the main window is active."""
        if self.isVisible() and not getattr(self, "_full_analysis_running", False):
            dialog = ReviewPromptDialog(self, games_count=count)
            dialog.exec()

    def on_analysis_error(self, error_msg):
        self._full_analysis_running = False
        self._update_analyze_button(running=False)
        self.analysis_panel.set_analysis_running(False)
        self._set_engine_state("ready")
        self._set_status(f"Analysis failed: {error_msg}", "error")
        logger.error(f"Analysis error: {error_msg}")
        if hasattr(self, "move_list_panel") and hasattr(self.move_list_panel, "live_worker"):
            self.move_list_panel.live_worker.start()
        if hasattr(self, "history_view"):
            self.history_view.set_analyzing_game_id(None)
            self.history_view.load_history()

        # Show error dialog with quick option to report bug
        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Icon.Critical)
        msg_box.setWindowTitle("Analysis Error")
        msg_box.setText("An error occurred during engine analysis.")
        msg_box.setInformativeText(str(error_msg))
        report_btn = msg_box.addButton("Report Issue", QMessageBox.ButtonRole.ActionRole)
        close_btn = msg_box.addButton("Close", QMessageBox.ButtonRole.RejectRole)
        msg_box.setDefaultButton(close_btn)
        msg_box.exec()

        if msg_box.clickedButton() == report_btn:
            dialog = FeedbackDialog(
                self,
                initial_tab="bug",
                initial_title="Analysis Engine Error",
                initial_message=f"Analysis failed with error:\n{error_msg}",
            )
            dialog.exec()

    def explore_current_position(self):
        """Switches to the Explorer tab and loads the current board position."""
        if not self.current_game:
            self._set_status("Load a game first before exploring", "warning")
            return
        if hasattr(self, "board_widget"):
            self.sidebar.set_active(1)
            self.switch_page(1)

            moves = self.current_game.moves if self.current_game else None
            self.explorer_view.load_board_state(
                self.board_widget.board,
                moves,
                chess960=self.current_game.metadata.chess960,
                starting_fen=self.current_game.metadata.starting_fen,
            )

    def on_cache_toggled(self, checked):
        self.analyzer.config["use_cache"] = checked
