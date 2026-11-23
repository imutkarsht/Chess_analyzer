# SPDX-License-Identifier: GPL-3.0-only
"""MainWindow adapter for the single-game analysis controller.

The workflow lives in ``src.gui.app.analysis_controller``. This mixin keeps the
existing window surface as thin delegates while call sites migrate.
"""

from __future__ import annotations

from src.gui.app.analysis_controller import AnalysisController


class AnalysisMixin:
    """Thin window adapter around :class:`AnalysisController`."""

    @property
    def analysis_controller(self) -> AnalysisController:
        controller = getattr(self, "_analysis_controller", None)
        if controller is None:
            controller = AnalysisController()
            controller.attach(self)
            self._analysis_controller = controller
        return controller

    # ------------------------------------------------------------------
    # Lifecycle delegates
    # ------------------------------------------------------------------

    def start_analysis(self, resume: bool | None = None):
        self.analysis_controller.start_analysis(resume)

    def stop_analysis(self):
        self.analysis_controller.stop_analysis()

    def _ensure_engine_ready(self) -> bool:
        """Batch analysis shares the same engine readiness gate."""
        return self.analysis_controller._ensure_engine_ready()

    def on_analysis_progress(self, current, total):
        self.analysis_controller.on_analysis_progress(current, total)

    def on_move_analyzed(self, move_index, data):
        self.analysis_controller.on_move_analyzed(move_index, data)

    def on_analysis_finished(self, game):
        self.analysis_controller.on_analysis_finished(game)

    def on_analysis_cancelled(self, game):
        self.analysis_controller.on_analysis_cancelled(game)

    def on_analysis_error(self, error_msg):
        self.analysis_controller.on_analysis_error(error_msg)

    def _set_analysis_follow(self, enabled: bool, *, jump: bool = False) -> None:
        self.analysis_controller._set_analysis_follow(enabled, jump=jump)

    def _on_follow_toggled(self, checked: bool) -> None:
        self.analysis_controller._on_follow_toggled(checked)

    def _flush_analysis_updates(self, *, force: bool = False) -> None:
        self.analysis_controller._flush_analysis_updates(force=force)

    def _update_analyze_button(self, running: bool) -> None:
        self.analysis_controller._update_analyze_button(running)

    def _on_sidebar_animation_changed(self, active: bool) -> None:
        self.analysis_controller._on_sidebar_animation_changed(active)

    def _prepare_analysis_end(self, game) -> int:
        return self.analysis_controller._prepare_analysis_end(game)

    # ------------------------------------------------------------------
    # State proxies (kept until call sites move to the controller)
    # ------------------------------------------------------------------

    @property
    def worker(self):
        return self.analysis_controller.worker

    @worker.setter
    def worker(self, value):
        self.analysis_controller.worker = value

    @property
    def _full_analysis_running(self) -> bool:
        return self.analysis_controller._full_analysis_running

    @_full_analysis_running.setter
    def _full_analysis_running(self, value: bool) -> None:
        self.analysis_controller._full_analysis_running = value

    @property
    def _analysis_follow(self) -> bool:
        return self.analysis_controller._analysis_follow

    @_analysis_follow.setter
    def _analysis_follow(self, value: bool) -> None:
        self.analysis_controller._analysis_follow = value

    @property
    def _latest_analyzed_index(self) -> int:
        return self.analysis_controller._latest_analyzed_index

    @_latest_analyzed_index.setter
    def _latest_analyzed_index(self, value: int) -> None:
        self.analysis_controller._latest_analyzed_index = value

    @property
    def _pending_analysis_updates(self) -> dict:
        return self.analysis_controller._pending_analysis_updates

    @_pending_analysis_updates.setter
    def _pending_analysis_updates(self, value: dict) -> None:
        self.analysis_controller._pending_analysis_updates = value

    @property
    def _pending_analysis_progress(self):
        return self.analysis_controller._pending_analysis_progress

    @_pending_analysis_progress.setter
    def _pending_analysis_progress(self, value) -> None:
        self.analysis_controller._pending_analysis_progress = value

    @property
    def _analysis_progress_final(self) -> bool:
        return self.analysis_controller._analysis_progress_final

    @_analysis_progress_final.setter
    def _analysis_progress_final(self, value: bool) -> None:
        self.analysis_controller._analysis_progress_final = value

    @property
    def _analysis_ui_timer(self):
        return self.analysis_controller._analysis_ui_timer

    @property
    def _analysis_toast(self):
        return self.analysis_controller._analysis_toast

    # ------------------------------------------------------------------
    # Window-level handlers that stay outside the controller
    # ------------------------------------------------------------------

    def on_history_changed(self, *_):
        if self.metrics_view is not None:
            self.metrics_view.mark_dirty()
            if self.stack.currentIndex() == 3:
                self.metrics_view.refresh(force=True)

    def explore_current_position(self):
        """Switches to the Explorer tab and loads the current board position."""
        if not self.current_game:
            self._set_status("Load a game first before exploring", "warning")
            return
        if hasattr(self, "variation") and self.variation.is_active:
            self.variation.exit()
        if hasattr(self, "board_widget"):
            self.sidebar.set_active(1)
            self.switch_page(1)

            moves = self.current_game.moves if self.current_game else None
            self.explorer_view.load_board_state(
                self.board_widget.board,
                moves,
                chess960=self.current_game.metadata.chess960,
                starting_fen=self.current_game.metadata.starting_fen,
                move_index=self.board_widget.current_move_index,
            )

    def on_cache_toggled(self, checked):
        self.config_manager.set("use_cache", bool(checked))
        if getattr(self, "analyzer", None):
            self.analyzer.config["use_cache"] = bool(checked)
        if hasattr(self, "settings_view"):
            self.settings_view.sync_analysis_shortcuts()

    def on_engine_lines_toggled(self, checked):
        self.config_manager.set("engine_lines_enabled", bool(checked))
        if hasattr(self, "settings_view"):
            self.settings_view.sync_analysis_shortcuts()

    def sync_analysis_prefs(self):
        """Mirror the settings-page analysis shortcuts into the live panel."""
        if not hasattr(self, "analysis_panel"):
            return
        use_cache = self.config_manager.use_cache
        engine_lines = self.config_manager.engine_lines_enabled
        if getattr(self, "analyzer", None):
            self.analyzer.config["use_cache"] = use_cache
        for checkbox, value in (
            (self.analysis_panel.cache_checkbox, use_cache),
            (self.analysis_panel.toggle_checkbox, engine_lines),
        ):
            checkbox.blockSignals(True)
            checkbox.setChecked(value)
            checkbox.blockSignals(False)
        if (
            hasattr(self, "move_list_panel")
            and self.move_list_panel.engine_lines_enabled != engine_lines
        ):
            self.move_list_panel.set_engine_lines_enabled(engine_lines)
