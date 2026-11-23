# SPDX-License-Identifier: GPL-3.0-only
"""Single-game analysis lifecycle, worker callbacks, and UI coalescing."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import QObject, QTimer, pyqtSignal
from PyQt6.QtWidgets import QDialog

from src.backend.analysis.analyzer import Analyzer
from src.backend.analysis.engine import EngineManager, invalidate_engine_cache, resolve_engine_path
from src.constants import ANALYSIS_UI_FLUSH_MS
from src.gui.components import ToastManager, show_error_dialog
from src.gui.dialogs.engine_error_dialog import EngineNotFoundDialog
from src.gui.dialogs.feedback_dialog import FeedbackDialog
from src.gui.dialogs.review_prompt_dialog import ReviewPromptDialog
from src.utils.logger import logger
from src.workers.analysis import AnalysisWorker

if TYPE_CHECKING:
    from src.gui.main_window.window import MainWindow


class AnalysisController(QObject):
    """Owns the single-game analysis run and its coalesced UI state."""

    analysis_started = pyqtSignal()
    analysis_completed = pyqtSignal(object)
    analysis_cancelled = pyqtSignal(object)
    analysis_failed = pyqtSignal(str)
    running_changed = pyqtSignal(bool)

    def __init__(self) -> None:
        super().__init__()
        self.host: MainWindow | None = None
        self.worker = None
        self._full_analysis_running = False
        self._analysis_follow = False
        self._latest_analyzed_index = -1
        self._pending_analysis_updates: dict[int, dict] = {}
        self._pending_analysis_progress: tuple[int, int] | None = None
        self._analysis_progress_final = False
        self._analysis_ui_timer: QTimer | None = None
        self._analysis_toast = None

    def attach(self, host: MainWindow) -> None:
        self.host = host
        self.setParent(host)

    @property
    def is_running(self) -> bool:
        return self.worker is not None and self.worker.isRunning()

    def shutdown(self) -> None:
        timer, self._analysis_ui_timer = self._analysis_ui_timer, None
        if timer is not None:
            timer.stop()
        toast, self._analysis_toast = self._analysis_toast, None
        if toast is not None and toast.active:
            toast.dismiss(immediate=True)
        worker, self.worker = self.worker, None
        if worker is None:
            return
        for signal in (
            worker.progress,
            worker.move_analyzed,
            worker.finished,
            worker.cancelled,
            worker.error,
        ):
            try:
                signal.disconnect()
            except (TypeError, RuntimeError):
                pass
        if worker.isRunning():
            worker.stop()
            worker.wait()

    def start_analysis(self, resume: bool | None = None):
        if not self.host.current_game:
            return

        coordinator = getattr(self.host, "analysis_coordinator", None)
        if coordinator is not None and coordinator.batch_running:
            self.host._set_status(
                "A batch analysis is running. Pause or cancel it before analyzing.",
                "warning",
            )
            return
        batch_worker = getattr(self.host, "_batch_worker", None)
        if batch_worker is not None:
            self.host._set_status(
                "The batch analysis is still finishing. Try again in a moment.",
                "warning",
            )
            return

        # A running analysis owns the board; never leave replay running underneath it.
        self.host._stop_replay()

        # A running analysis owns the board; never leave a variation underneath it.
        self.host._exit_variation()

        if hasattr(self, "worker") and self.worker and self.worker.isRunning():
            self.host.show_toast("An analysis is already running.", "warning")
            return

        if not self._ensure_engine_ready():
            return

        if resume is None:
            resume = getattr(self.host.current_game, "status", "") == "paused"

        if coordinator is not None and not coordinator.begin_single(
            getattr(self.host.current_game, "game_id", None)
        ):
            self.host.show_toast("An analysis is already running.", "warning")
            return

        logger.info("Starting analysis (resume=%s)...", resume)

        # If starting fresh or cache turned off, clear previous move evaluations
        if not resume or not self.host.analyzer.config.get("use_cache", True):
            for move in self.host.current_game.moves:
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
            self.host.current_game.summary = {}
            self.host.current_game.ai_summary = ""

            if hasattr(self.host, "move_list_panel"):
                self.host.move_list_panel.set_game(self.host.current_game)
            if hasattr(self.host, "analysis_panel"):
                self.host.analysis_panel.set_game(self.host.current_game)

        self._reset_analysis_ui_session()
        self.worker = AnalysisWorker(self.host.analyzer, self.host.current_game, resume=resume)
        self.worker.progress.connect(self.on_analysis_progress)
        self.worker.move_analyzed.connect(self.on_move_analyzed)
        self.worker.finished.connect(self.on_analysis_finished)
        self.worker.cancelled.connect(self.on_analysis_cancelled)
        self.worker.error.connect(self.on_analysis_error)

        self._full_analysis_running = True
        self.running_changed.emit(True)
        self._update_analyze_button(running=True)
        self.host._set_engine_state("calculating", "Starting...")
        self.host._set_status("Starting analysis...", "progress")

        previous_toast = getattr(self, "_analysis_toast", None)
        if previous_toast is not None and previous_toast.active:
            previous_toast.dismiss(immediate=True)
        self._analysis_toast = ToastManager.loading(
            self.host,
            "Analyzing game…",
            action=("Stop", self.stop_analysis),
        )
        self.host.analysis_panel.set_analysis_running(True)

        if hasattr(self.host, "history_view") and self.host.current_game:
            self.host.history_view.set_analyzing_game_id(getattr(self.host.current_game, "game_id", None))

        if hasattr(self.host, "move_list_panel") and hasattr(self.host.move_list_panel, "session"):
            self.host.move_list_panel.session.pause()

        self.worker.start()
        self.analysis_started.emit()

    def _ensure_engine_ready(self) -> bool:
        """Resolve/prepare the engine, returning False when the user backs out."""
        resolved = resolve_engine_path(self.host.config_manager, deep_probe=True)
        if resolved:
            if resolved != self.host.engine_path:
                self.host.engine_path = resolved
                self.host.analyzer = Analyzer(
                    EngineManager(self.host.engine_path, config_manager=self.host.config_manager)
                )
            return True

        logger.warning(f"Engine not found (configured: {self.host.engine_path})")
        dialog = EngineNotFoundDialog(self.host)
        if hasattr(self.host, "config_manager"):
            dialog.config_manager = lambda: self.host.config_manager
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_path = dialog.engine_path()
            if new_path:
                self.host.config_manager.config["engine_path"] = new_path
                self.host.config_manager.save_config()
                self.host.engine_path = new_path
                self.host.analyzer = Analyzer(
                    EngineManager(self.host.engine_path, config_manager=self.host.config_manager)
                )
                invalidate_engine_cache()
                logger.info(f"Engine path set to {new_path} via error dialog")
                self.host._refresh_engine_status()
                return True
        else:
            # Cancel navigates to Settings (index 4) where the engine can be configured
            self.host.sidebar.set_active(4)
            self.host.switch_page(4)
        return False

    def stop_analysis(self):
        """Immediately stop running analysis and preserve partial results."""
        if not getattr(self, "_full_analysis_running", False):
            return
        logger.info("MainWindow: stop_analysis requested by user.")
        self.host._set_status("Stopping analysis...", "warning")
        if hasattr(self.host, "btn_analyze"):
            self.host.btn_analyze.setEnabled(False)

        if hasattr(self, "worker") and self.worker and self.worker.isRunning():
            self.worker.cancel()

    def _finish_analysis_toast(self, message: str, variant: str) -> None:
        """Turn the running analysis toast into its final state."""
        toast = getattr(self, "_analysis_toast", None)
        if toast is not None and toast.active:
            toast.set_progress(None)
            toast.update(message, variant=variant, action=None)
        else:
            self.host.show_toast(message, variant)
        self._analysis_toast = None

    def _update_analyze_button(self, running: bool):
        """Toggle the toolbar button between Analyze, Resume, Reanalyze and Stop."""
        if not hasattr(self.host, "btn_analyze"):
            return

        coordinator = getattr(self.host, "analysis_coordinator", None)
        if coordinator is not None and coordinator.batch_running and not running:
            try:
                self.host.btn_analyze.clicked.disconnect()
            except (TypeError, RuntimeError):
                pass
            current_id = getattr(self.host.current_game, "game_id", None)
            if current_id and current_id == coordinator.active_game_id:
                self.host.btn_analyze.setText(
                    f"In batch ({coordinator.active_position}/{coordinator.batch_total})"
                )
                self.host.btn_analyze.setToolTip(
                    "This game is being analyzed in the batch "
                    f"({coordinator.active_position}/{coordinator.batch_total})."
                )
            else:
                self.host.btn_analyze.setText("Batch analysis running")
                self.host.btn_analyze.setToolTip(
                    "Pause or cancel the batch from History before analyzing another game."
                )
            self.host.btn_analyze.set_danger(False)
            self.host.btn_analyze.set_icon_spec("fa5s.lock")
            self.host.btn_analyze.setEnabled(False)
            return

        self.host.btn_analyze.setToolTip("")
        try:
            self.host.btn_analyze.clicked.disconnect()
        except (TypeError, RuntimeError):
            pass

        if running:
            self.host.btn_analyze.setText("Stop Analysis")
            self.host.btn_analyze.set_danger(True)
            self.host.btn_analyze.set_icon_spec("fa5s.stop")
            self.host.btn_analyze.clicked.connect(self.stop_analysis)
            self.host.btn_analyze.setEnabled(True)
        else:
            game_status = (
                getattr(self.host.current_game, "status", "not_started")
                if self.host.current_game
                else "not_started"
            )
            if game_status == "paused":
                analyzed = getattr(self.host.current_game, "analyzed_moves_count", 0)
                total = getattr(self.host.current_game, "total_moves_count", 0) or len(
                    getattr(self.host.current_game, "moves", [])
                )
                self.host.btn_analyze.setText(f"Resume ({analyzed}/{total})")
                self.host.btn_analyze.set_danger(False)
                self.host.btn_analyze.set_icon_spec("fa5s.play")
                self.host.btn_analyze.clicked.connect(lambda: self.start_analysis(resume=True))
            elif game_status == "completed":
                self.host.btn_analyze.setText("Reanalyze Game")
                self.host.btn_analyze.set_danger(False)
                self.host.btn_analyze.set_icon_spec("fa5s.sync-alt")
                self.host.btn_analyze.clicked.connect(lambda: self.start_analysis(resume=False))
            else:
                self.host.btn_analyze.setText("Analyze Game")
                self.host.btn_analyze.set_danger(False)
                self.host.btn_analyze.set_icon_spec("fa5s.play")
                self.host.btn_analyze.clicked.connect(lambda: self.start_analysis(resume=False))
            self.host.btn_analyze.setEnabled(True)

    # ------------------------------------------------------------------
    # Analysis UI coalescing
    # ------------------------------------------------------------------
    def _ensure_analysis_ui_timer(self) -> None:
        if getattr(self, "_analysis_ui_timer", None) is not None:
            return
        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.setInterval(ANALYSIS_UI_FLUSH_MS)
        timer.timeout.connect(self._flush_analysis_updates)
        self._analysis_ui_timer = timer

    def _schedule_analysis_flush(self) -> None:
        # Keep the sidebar animation smooth: analysis results stay queued and
        # are applied in one pass when the rail settles.
        if getattr(self.host, "_sidebar_animating", False):
            return
        self._ensure_analysis_ui_timer()
        if not self._analysis_ui_timer.isActive():
            self._analysis_ui_timer.start()

    def _on_sidebar_animation_changed(self, active: bool) -> None:
        self.host._sidebar_animating = bool(active)
        timer = getattr(self, "_analysis_ui_timer", None)
        if active:
            if timer is not None:
                timer.stop()
            return
        if (
            getattr(self, "_pending_analysis_updates", None)
            or getattr(self, "_pending_analysis_progress", None) is not None
        ):
            QTimer.singleShot(0, self._flush_analysis_updates)

    def _last_analyzed_index(self) -> int:
        moves = getattr(self.host.current_game, "moves", []) if self.host.current_game else []
        analyzed = [index for index, move in enumerate(moves) if move.classification]
        return analyzed[-1] if analyzed else -1

    def _reset_analysis_ui_session(self) -> None:
        """Start a fresh follow session for the game about to be analysed."""
        self._ensure_analysis_ui_timer()
        self._analysis_ui_timer.stop()
        self._pending_analysis_updates = {}
        self._pending_analysis_progress = None
        self._analysis_progress_final = False
        self._latest_analyzed_index = self._last_analyzed_index()
        self._analysis_follow = True
        self._sync_follow_toggle(visible=True, checked=True)

    def _sync_follow_toggle(
        self, *, visible: bool | None = None, checked: bool | None = None
    ) -> None:
        button = getattr(self.host, "btn_follow", None)
        if button is None:
            return
        if visible is not None:
            button.setVisible(visible)
        if checked is not None:
            button.blockSignals(True)
            button.setChecked(checked)
            button.blockSignals(False)

    def _set_analysis_follow(self, enabled: bool, *, jump: bool = False) -> None:
        self._analysis_follow = bool(enabled)
        self._sync_follow_toggle(checked=self._analysis_follow)
        if jump and self._analysis_follow:
            self._jump_to_latest_analyzed()

    def _on_follow_toggled(self, checked: bool) -> None:
        if checked:
            # The user wants the live position back; replay must not fight it.
            self.host._stop_replay()
            self._analysis_follow = True
            self._jump_to_latest_analyzed()
            return
        self._analysis_follow = False

    def _jump_to_latest_analyzed(self) -> None:
        if self.host.current_game and 0 <= self._latest_analyzed_index < len(
            self.host.current_game.moves
        ):
            self._show_followed_position(self._latest_analyzed_index)
            if hasattr(self.host, "analysis_panel"):
                self.host.analysis_panel.set_selected_move(self._latest_analyzed_index)

    def _show_followed_position(self, move_index: int) -> None:
        """Position the board for analysis follow without rebuilding coach facts."""
        if not self.host.current_game or not 0 <= move_index < len(self.host.current_game.moves):
            return
        self.host.board_widget.set_position(move_index)
        self.host.move_list_panel.select_move(move_index)
        self.host._update_captured_and_clocks(move_index)
        self.host.move_changed.emit(move_index)

    def _flush_analysis_updates(self, *, force: bool = False) -> None:
        """Apply all queued analysis data in one UI pass."""
        if getattr(self.host, "_sidebar_animating", False) and not force:
            return
        timer = getattr(self, "_analysis_ui_timer", None)
        if timer is not None:
            timer.stop()

        updates = getattr(self, "_pending_analysis_updates", None) or {}
        progress = getattr(self, "_pending_analysis_progress", None)
        if not updates and progress is None:
            return
        self._pending_analysis_updates = {}
        self._pending_analysis_progress = None

        game = self.host.current_game
        if game is None:
            return

        if updates:
            valid_indices = []
            for move_index, data in updates.items():
                if not 0 <= move_index < len(game.moves):
                    continue
                move = game.moves[move_index]
                classification = data.get("classification", move.classification)
                if classification:
                    move.classification = classification
                eval_cp = data.get("eval_after_cp")
                eval_mate = data.get("eval_after_mate")
                if eval_cp is not None:
                    move.eval_after_cp = eval_cp
                if eval_mate is not None:
                    move.eval_after_mate = eval_mate
                valid_indices.append(move_index)

            if valid_indices and hasattr(self.host, "move_list_panel"):
                self.host.move_list_panel.update_move_cells(valid_indices)

            if self._analysis_follow and self._latest_analyzed_index >= 0:
                self._show_followed_position(self._latest_analyzed_index)

            if hasattr(self.host, "analysis_panel") and getattr(
                self.host.analysis_panel, "graph_widget", None
            ) is not None:
                current_index = (
                    self._latest_analyzed_index
                    if self._analysis_follow
                    else self.host.board_widget.current_move_index
                )
                self.host.analysis_panel.graph_widget.update_progress(
                    game.moves, self._latest_analyzed_index, current_index
                )

        if progress is not None:
            self._apply_analysis_progress(*progress)

    def _apply_analysis_progress(self, current: int, total: int) -> None:
        if current > total:
            self.host._set_engine_state("calculating", "Final...")
            self.host._set_status("Analyzing final position...", "progress")
        else:
            self.host._set_engine_state("calculating", f"{current}/{total}")
            self.host._set_status(f"Analyzing move {current} of {total}", "progress")

        toast = getattr(self, "_analysis_toast", None)
        if toast is not None and toast.active:
            safe_total = max(1, total)
            toast.update(
                "Analyzing final position…"
                if current > total
                else f"Analyzing move {current} of {total}"
            )
            toast.set_progress(min(1.0, current / safe_total))

    def on_analysis_progress(self, current, total):
        # The final position is announced with current == total + 1; the later
        # classification pass then replays 1..total. Keep the final label.
        if getattr(self, "_analysis_progress_final", False) and current <= total:
            return
        if current > total:
            self._analysis_progress_final = True
        self._pending_analysis_progress = (current, total)
        self._schedule_analysis_flush()

    def on_move_analyzed(self, move_index, data):
        """Queue a move's eval/classification until the next coalesced flush."""
        if not self.host.current_game:
            return
        if not 0 <= move_index < len(self.host.current_game.moves):
            return
        pending = getattr(self, "_pending_analysis_updates", None)
        if pending is None:
            pending = self._pending_analysis_updates = {}
        pending[move_index] = data
        self._latest_analyzed_index = max(self._latest_analyzed_index, move_index)
        self._schedule_analysis_flush()

    def _prepare_analysis_end(self, game) -> int:
        """Flush pending work and return the move index the board should show."""
        self.host.current_game = game
        selected_index = self.host.board_widget.current_move_index
        was_following = getattr(self, "_analysis_follow", False)
        self._analysis_follow = False
        self._flush_analysis_updates(force=True)
        self._sync_follow_toggle(visible=False, checked=False)

        target = self._latest_analyzed_index if was_following else selected_index
        if not game or not game.moves:
            return -1
        return max(-1, min(target, len(game.moves) - 1))

    def _restore_analysis_view(self, game, target_index: int) -> None:
        """Rebuild both analysis panes, then restore the chosen board position."""
        if hasattr(self.host, "move_list_panel") and hasattr(self.host.move_list_panel, "session"):
            self.host.move_list_panel.session.resume()
        self.host.move_list_panel.set_game(game)
        self.host.analysis_panel.set_game(game)
        self.host.on_move_selected(target_index, silent=True, manual=False)

    def on_analysis_cancelled(self, game):
        """Handle analysis cancellation while preserving partial results."""
        coordinator = getattr(self.host, "analysis_coordinator", None)
        if coordinator is not None:
            coordinator.end_single()
        target_index = self._prepare_analysis_end(game)
        self._full_analysis_running = False
        self.running_changed.emit(False)
        self.host.analysis_panel.set_analysis_running(False)
        self.host._set_engine_state("ready")
        self.host._set_status("Analysis stopped", "info")
        self._finish_analysis_toast("Analysis stopped", "info")
        logger.info("Analysis cancelled; partial results preserved.")
        if game and game.pgn_content:
            try:
                self.host.history_manager.save_game(game, game.pgn_content, force_overwrite=True)
            except Exception as e:
                logger.error(f"Failed saving paused game to history: {e}")
        self._update_analyze_button(running=False)
        self._restore_analysis_view(game, target_index)

        if self.host.metrics_view is not None:
            self.host.metrics_view.mark_dirty()
            if self.host.stack.currentIndex() == 3:
                self.host.metrics_view.refresh(force=True)
        if hasattr(self.host, "history_view"):
            self.host.history_view.set_analyzing_game_id(None)
            self.host.history_view.refresh_game(getattr(game, "game_id", None))
        self.analysis_cancelled.emit(game)

    def on_analysis_finished(self, game):
        coordinator = getattr(self.host, "analysis_coordinator", None)
        if coordinator is not None:
            coordinator.end_single()
        target_index = self._prepare_analysis_end(game)
        self._full_analysis_running = False
        self.running_changed.emit(False)
        self.host.analysis_panel.set_analysis_running(False)
        self.host._set_engine_state("ready")
        self.host._set_status("Analysis complete", "success")
        self._finish_analysis_toast("Analysis complete!", "success")
        logger.info("Analysis finished successfully.")
        self._update_analyze_button(running=False)
        self._restore_analysis_view(game, target_index)
        if self.host.metrics_view is not None:
            self.host.metrics_view.mark_dirty()
            if self.host.stack.currentIndex() == 3:
                self.host.metrics_view.refresh(force=True)
        if hasattr(self.host, "history_view"):
            self.host.history_view.set_analyzing_game_id(None)
            self.host.history_view.refresh_game(getattr(game, "game_id", None))

        # Track analyzed games count and check for in-app review prompt
        count = self.host.config_manager.games_analyzed_count + 1
        self.host.config_manager.set("games_analyzed_count", count)

        next_prompt = self.host.config_manager.review_next_prompt_count
        reviewed = self.host.config_manager.review_submitted
        dismissed = self.host.config_manager.review_prompt_dismissed

        if count >= next_prompt and not reviewed and not dismissed:
            QTimer.singleShot(1500, lambda: self._prompt_review_if_active(count))
        self.analysis_completed.emit(game)

    def _prompt_review_if_active(self, count: int):
        """Display the review prompt if the main window is active."""
        if self.host.isVisible() and not getattr(self, "_full_analysis_running", False):
            dialog = ReviewPromptDialog(self.host, games_count=count)
            dialog.exec()

    def on_analysis_error(self, error_msg):
        coordinator = getattr(self.host, "analysis_coordinator", None)
        if coordinator is not None:
            coordinator.end_single()
        self._full_analysis_running = False
        self._analysis_follow = False
        self.running_changed.emit(False)
        self._flush_analysis_updates()
        self._sync_follow_toggle(visible=False, checked=False)
        self._update_analyze_button(running=False)
        self.host.analysis_panel.set_analysis_running(False)
        self.host._set_engine_state("ready")
        self.host._set_status(f"Analysis failed: {error_msg}", "error")
        self._finish_analysis_toast(f"Analysis failed: {error_msg}", "error")
        logger.error(f"Analysis error: {error_msg}")
        if hasattr(self.host, "move_list_panel") and hasattr(self.host.move_list_panel, "session"):
            self.host.move_list_panel.session.resume()
        if hasattr(self.host, "history_view"):
            self.host.history_view.set_analyzing_game_id(None)
            self.host.history_view.load_history()

        def report_issue() -> None:
            dialog = FeedbackDialog(
                self.host,
                initial_tab="bug",
                initial_title="Analysis Engine Error",
                initial_message=f"Analysis failed with error:\n{error_msg}",
            )
            dialog.exec()

        show_error_dialog(
            self.host,
            "Analysis Error",
            f"An error occurred during engine analysis.\n\n{error_msg}",
            action_label="Report Issue",
            on_action=report_issue,
            close_label="Close",
        )
        self.analysis_failed.emit(error_msg)

    # ------------------------------------------------------------------
    # Analysis preferences
    # ------------------------------------------------------------------

    def on_cache_toggled(self, checked) -> None:
        self.host.config_manager.set("use_cache", bool(checked))
        if getattr(self.host, "analyzer", None):
            self.host.analyzer.config["use_cache"] = bool(checked)
        if hasattr(self.host, "settings_view"):
            self.host.settings_view.sync_analysis_shortcuts()

    def on_engine_lines_toggled(self, checked) -> None:
        self.host.config_manager.set("engine_lines_enabled", bool(checked))
        if hasattr(self.host, "settings_view"):
            self.host.settings_view.sync_analysis_shortcuts()

    def sync_analysis_prefs(self) -> None:
        """Mirror the settings-page analysis shortcuts into the live panel."""
        if not hasattr(self.host, "analysis_panel"):
            return
        use_cache = self.host.config_manager.use_cache
        engine_lines = self.host.config_manager.engine_lines_enabled
        if getattr(self.host, "analyzer", None):
            self.host.analyzer.config["use_cache"] = use_cache
        for checkbox, value in (
            (self.host.analysis_panel.cache_checkbox, use_cache),
            (self.host.analysis_panel.toggle_checkbox, engine_lines),
        ):
            checkbox.blockSignals(True)
            checkbox.setChecked(value)
            checkbox.blockSignals(False)
        if (
            hasattr(self.host, "move_list_panel")
            and self.host.move_list_panel.engine_lines_enabled != engine_lines
        ):
            self.host.move_list_panel.set_engine_lines_enabled(engine_lines)
