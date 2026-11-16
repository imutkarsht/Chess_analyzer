# SPDX-License-Identifier: GPL-3.0-only
"""MainWindow orchestration for the persisted History batch queue."""

from __future__ import annotations

from PyQt6.QtWidgets import QDialog, QHBoxLayout, QMessageBox, QVBoxLayout

from src.backend.analysis.batch import reconcile_batch
from src.backend.models.analysis_batch import (
    BATCH_CANCELLED,
    BATCH_COMPLETED,
    BATCH_FAILED,
    BATCH_PAUSED,
    BATCH_RUNNING,
    INTENT_ANALYZE,
    INTENT_RESUME,
    INTENT_SKIP,
    OUTCOME_NOT_STARTED,
    OUTCOME_PENDING,
    AnalysisBatch,
    AnalysisBatchItem,
)
from src.gui.analysis.batch_analysis_worker import BatchAnalysisWorker
from src.gui.analysis.coordinator import AnalysisCoordinator
from src.gui.components import Button, ButtonVariant, Label, TextRole, TextTone
from src.gui.styles import Styles
from src.gui.utils.gui_utils import confirm_dialog
from src.gui.utils.worker_registry import register_worker, remove_worker
from src.utils.logger import logger


class BatchAnalysisMixin:
    """Own the batch queue lifecycle, gating, and History/Metrics refresh."""

    def _init_batch_analysis(self) -> None:
        self.analysis_coordinator = AnalysisCoordinator()
        self._batch_worker: BatchAnalysisWorker | None = None
        self._batch_active_label = ""
        self.history_view.batch_analysis_requested.connect(self.start_batch_analysis)
        self.history_view.batch_control_requested.connect(self._on_batch_control)
        self._recover_persisted_batch()

    # ------------------------------------------------------------------
    # Startup recovery
    # ------------------------------------------------------------------

    def _recover_persisted_batch(self) -> None:
        try:
            if self.history_manager.pause_interrupted_analysis_batch():
                logger.info("Recovered a running batch as paused")
            batch = self.history_manager.get_analysis_batch()
            if batch is None:
                return
            if batch.total == 0:
                self.history_manager.delete_analysis_batch()
                return
            if batch.state in (BATCH_RUNNING, BATCH_PAUSED):
                batch = reconcile_batch(batch, self._batch_statuses(batch))
                self.history_manager.save_analysis_batch_items(batch.items)
                if not batch.actionable_items():
                    batch.state = BATCH_COMPLETED
                    self.history_manager.set_analysis_batch_state(BATCH_COMPLETED)
                else:
                    batch.state = BATCH_PAUSED
                    self.history_manager.set_analysis_batch_state(BATCH_PAUSED)
            self.analysis_coordinator.restore_batch(
                batch.state,
                batch.total,
                {item.game_id for item in batch.actionable_items()},
            )
            self.history_view.set_batch_queue(batch)
        except Exception as e:
            logger.error("Failed to restore the batch queue: %s", e, exc_info=True)

    # ------------------------------------------------------------------
    # Start / resume
    # ------------------------------------------------------------------

    def start_batch_analysis(self, game_ids) -> None:
        ids = list(dict.fromkeys(game_ids or []))
        coordinator = self.analysis_coordinator
        if not coordinator.can_start_batch():
            message = (
                "A batch analysis is already running."
                if coordinator.batch_running
                else "An analysis is already running. Stop it before starting a batch."
            )
            QMessageBox.warning(self, "Analysis in Progress", message)
            return
        if self._batch_worker is not None and self._batch_worker.isRunning():
            QMessageBox.warning(
                self, "Analysis in Progress", "The previous batch is still finishing."
            )
            return
        if getattr(self, "worker", None) is not None and self.worker.isRunning():
            QMessageBox.warning(
                self, "Analysis in Progress", "An analysis is already running."
            )
            return

        existing = self.history_manager.get_analysis_batch()
        if existing is not None:
            if existing.state == BATCH_RUNNING:
                QMessageBox.warning(
                    self, "Batch in Progress", "A batch analysis is already running."
                )
                return
            if existing.state == BATCH_PAUSED and existing.actionable_items():
                choice = self._resolve_paused_batch_conflict()
                if choice == "resume":
                    self._resume_batch()
                    return
                if choice == "cancel":
                    return
            self.history_manager.delete_analysis_batch()
            self.history_view.hide_batch_queue()

        if not ids:
            return
        if not self._ensure_engine_ready():
            return

        try:
            rows = self.history_manager.fetch_game_rows_by_ids(ids)
        except Exception as e:
            logger.error("Failed to prepare batch rows: %s", e)
            self.show_toast(f"Could not prepare batch: {e}", "error")
            return
        by_id = {row["id"]: row for row in rows}
        valid_ids = [game_id for game_id in ids if game_id in by_id]
        if not valid_ids:
            self.show_toast("Those games are no longer in History.", "warning")
            return

        items = [
            AnalysisBatchItem(
                game_id=game_id,
                position=position,
                intent=_intent_for_status(by_id[game_id].get("analysis_status")),
            )
            for position, game_id in enumerate(valid_ids, start=1)
        ]
        batch = AnalysisBatch(state=BATCH_RUNNING, items=items)
        try:
            batch = self.history_manager.save_analysis_batch(batch)
        except Exception as e:
            logger.error("Failed to create batch queue: %s", e)
            self.show_toast(f"Could not create batch queue: {e}", "error")
            return

        if not coordinator.begin_batch(
            [item.game_id for item in items], total=batch.total
        ):
            QMessageBox.warning(
                self, "Analysis in Progress", "An analysis is already running."
            )
            return

        self.history_view.on_batch_started(batch)
        self._start_batch_worker(batch)

    def _resume_batch(self) -> None:
        coordinator = self.analysis_coordinator
        if not coordinator.can_start_batch():
            QMessageBox.warning(
                self,
                "Analysis in Progress",
                "An analysis is already running. Finish it before resuming the batch.",
            )
            return
        if self._batch_worker is not None and self._batch_worker.isRunning():
            QMessageBox.warning(
                self, "Analysis in Progress", "The previous batch is still finishing."
            )
            return
        if getattr(self, "worker", None) is not None and self.worker.isRunning():
            QMessageBox.warning(
                self, "Analysis in Progress", "An analysis is already running."
            )
            return
        batch = self.history_manager.get_analysis_batch()
        if batch is None or batch.state != BATCH_PAUSED:
            return
        batch = reconcile_batch(batch, self._batch_statuses(batch))
        self.history_manager.save_analysis_batch_items(batch.items)
        if not batch.actionable_items():
            batch.state = BATCH_COMPLETED
            self.history_manager.set_analysis_batch_state(BATCH_COMPLETED)
            self.history_view.refresh_batch_queue()
            return
        if not self._ensure_engine_ready():
            return

        batch.state = BATCH_RUNNING
        self.history_manager.set_analysis_batch_state(BATCH_RUNNING)
        if not coordinator.begin_batch(
            [item.game_id for item in batch.actionable_items()], total=batch.total
        ):
            QMessageBox.warning(
                self, "Analysis in Progress", "An analysis is already running."
            )
            return
        self.history_view.on_batch_started(batch)
        self._start_batch_worker(batch)
        self._set_status("Resuming batch analysis", "progress")

    def _start_batch_worker(self, batch: AnalysisBatch) -> None:
        if self._batch_worker is not None and self._batch_worker.isRunning():
            return
        worker = BatchAnalysisWorker(
            self.analyzer, batch, self.history_manager, parent=self
        )
        worker.game_started.connect(self._on_batch_game_started)
        worker.game_progress.connect(self._on_batch_game_progress)
        worker.game_outcome.connect(self._on_batch_game_outcome)
        worker.batch_paused.connect(self._on_batch_paused)
        worker.batch_cancelled.connect(self._on_batch_cancelled)
        worker.batch_finished.connect(self._on_batch_finished)
        worker.batch_failed.connect(self._on_batch_failed)
        worker.finished.connect(lambda: self._release_batch_worker(worker))
        self._batch_worker = worker
        self._batch_active_label = ""
        register_worker(worker)

        self._stop_replay()
        self._exit_variation()
        self._set_batch_engine_lock(True)
        self._set_engine_state("calculating", "Starting...")
        self._set_status("Starting batch analysis...", "progress")
        worker.start()

    # ------------------------------------------------------------------
    # Worker callbacks
    # ------------------------------------------------------------------

    def _on_batch_game_started(
        self, game_id, position, total, action, label, _total_moves
    ) -> None:
        self._batch_active_label = label
        batch = self._current_batch()
        queued = {item.game_id for item in (batch.pending_items() if batch else [])}
        queued.discard(game_id)
        self.analysis_coordinator.set_batch_runtime(
            game_id, position, total, queued_game_ids=queued
        )
        self.history_view.set_batch_active(
            game_id, label, position, total, queued, batch=batch
        )
        self._set_engine_state("calculating", f"{position}/{total}")
        self._set_status(f"Batch {position}/{total} · {label}", "progress")
        self._update_analyze_button(running=False)

    def _on_batch_game_progress(self, game_id, current, total_moves) -> None:
        if self.analysis_coordinator.active_game_id == game_id:
            self.history_view.update_batch_move_progress(current, total_moves)

    def _on_batch_game_outcome(self, game_id, _outcome, error) -> None:
        if error:
            logger.warning("Batch game %s failed: %s", game_id, error)
        self.history_view.refresh_game(game_id)
        batch = self._current_batch()
        if batch is not None:
            queued = {item.game_id for item in batch.pending_items()}
            queued.discard(self.analysis_coordinator.active_game_id)
            self.analysis_coordinator.set_batch_runtime(
                self.analysis_coordinator.active_game_id,
                self.analysis_coordinator.active_position,
                self.analysis_coordinator.batch_total,
                queued_game_ids=queued,
            )
            self.history_view.set_batch_queue(
                batch,
                active_label=self._batch_active_label,
                position=self.analysis_coordinator.active_position,
            )
        if self.metrics_view is not None:
            self.metrics_view.mark_dirty()

    def _on_batch_paused(self, _summary) -> None:
        self._finish_batch_state(BATCH_PAUSED, "Batch paused", "info")

    def _on_batch_cancelled(self, _summary) -> None:
        self._finish_batch_state(BATCH_CANCELLED, "Batch cancelled", "info")

    def _on_batch_finished(self, _summary) -> None:
        self._finish_batch_state(BATCH_COMPLETED, "Batch complete", "success")

    def _on_batch_failed(self, _summary, error) -> None:
        self._finish_batch_state(BATCH_FAILED, f"Batch stopped: {error}", "error")

    def _finish_batch_state(self, state: str, message: str, kind: str) -> None:
        self.analysis_coordinator.end_batch(state)
        self._batch_active_label = ""
        self._set_batch_engine_lock(False)
        self.history_view.set_batch_running(False)
        self.history_view.load_history()
        self.history_view.refresh_batch_queue()
        self._set_engine_state("ready")
        self._set_status(message, kind)
        self._update_analyze_button(running=False)
        if self.metrics_view is not None:
            self.metrics_view.mark_dirty()
            if self.stack.currentIndex() == 3:
                self.metrics_view.refresh(force=True)
        if state == BATCH_FAILED:
            self.show_toast(message, "error")

    # ------------------------------------------------------------------
    # Controls
    # ------------------------------------------------------------------

    def _on_batch_control(self, action: str) -> None:
        if action == "pause":
            if self._batch_worker is not None and self._batch_worker.isRunning():
                self.history_view.batch_queue_card.btn_pause.setEnabled(False)
                self.history_view.batch_queue_card.btn_pause.setText("Pausing…")
                self._set_status("Pausing batch...", "warning")
                self._batch_worker.pause()
            return
        if action == "resume":
            self._resume_batch()
            return
        if action == "cancel":
            self._cancel_batch()
            return
        if action == "dismiss":
            self._dismiss_batch()

    def _cancel_batch(self) -> None:
        batch = self._current_batch()
        if batch is None:
            return
        worker = self._batch_worker
        if worker is not None and worker.isRunning():
            if not confirm_dialog(
                self,
                "Cancel Batch",
                "Cancel this batch? The current game's partial analysis will be saved, "
                "and remaining games will not be analyzed.",
                confirm_label="Cancel batch",
            ):
                return
            self.history_view.batch_queue_card.btn_cancel.setEnabled(False)
            self._set_status("Cancelling batch...", "warning")
            worker.cancel()
            return
        if batch.state != BATCH_PAUSED:
            return
        if not confirm_dialog(
            self,
            "Discard Paused Batch",
            "Discard this paused batch? Partial analysis stays in History, and "
            "remaining games will not be analyzed.",
            confirm_label="Discard batch",
        ):
            return
        items = [
            item.with_outcome(OUTCOME_NOT_STARTED)
            if item.outcome == OUTCOME_PENDING
            else item
            for item in batch.items
        ]
        self.history_manager.save_analysis_batch_items(items)
        self.history_manager.set_analysis_batch_state(BATCH_CANCELLED)
        self._finish_batch_state(BATCH_CANCELLED, "Batch cancelled", "info")

    def _dismiss_batch(self) -> None:
        batch = self._current_batch()
        if batch is None or batch.state == BATCH_RUNNING:
            return
        self.history_manager.delete_analysis_batch()
        self.history_view.hide_batch_queue()
        self.analysis_coordinator.reset()
        self._update_analyze_button(running=False)

    # ------------------------------------------------------------------
    # External single-analysis sync
    # ------------------------------------------------------------------

    def _sync_paused_batch(self, game_id: str | None = None) -> None:
        batch = self._current_batch()
        if batch is None or batch.state != BATCH_PAUSED:
            return
        try:
            batch = reconcile_batch(batch, self._batch_statuses(batch))
            self.history_manager.save_analysis_batch_items(batch.items)
            if not batch.actionable_items():
                batch.state = BATCH_COMPLETED
                self.history_manager.set_analysis_batch_state(BATCH_COMPLETED)
            self.analysis_coordinator.restore_batch(
                batch.state,
                batch.total,
                {item.game_id for item in batch.actionable_items()},
            )
            self.history_view.refresh_batch_queue()
            if game_id:
                self.history_view.refresh_game(game_id)
        except Exception as e:
            logger.error("Failed to sync paused batch: %s", e)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _batch_statuses(self, batch: AnalysisBatch) -> dict[str, str | None]:
        return {
            item.game_id: self.history_manager.get_game_analysis_status(item.game_id)
            for item in batch.items
        }

    def _current_batch(self) -> AnalysisBatch | None:
        try:
            return self.history_manager.get_analysis_batch()
        except Exception as e:
            logger.debug("Failed to load batch queue: %s", e)
            return None

    def _set_batch_engine_lock(self, locked: bool) -> None:
        if hasattr(self, "move_list_panel"):
            self.move_list_panel.set_analysis_locked(locked)
        if hasattr(self, "explorer_view"):
            self.explorer_view.set_analysis_locked(locked)
        if hasattr(self, "analysis_panel"):
            self.analysis_panel.toggle_checkbox.setEnabled(not locked)
        if hasattr(self, "btn_analyze"):
            self._update_analyze_button(running=False)

    def _release_batch_worker(self, worker) -> None:
        if self._batch_worker is worker:
            self._batch_worker = None
        remove_worker(worker)

    def _stop_batch_for_exit(self) -> None:
        worker = self._batch_worker
        if worker is not None and worker.isRunning():
            worker.pause()
            worker.wait()
        self._batch_worker = None
        try:
            self.analyzer.engine_manager.stop_engine()
        except Exception as e:  # pragma: no cover - defensive
            logger.debug("Failed to stop engine on exit: %s", e)

    def _resolve_paused_batch_conflict(self) -> str:
        dlg = QDialog(self)
        dlg.setWindowTitle("Batch Already Paused")
        dlg.setModal(True)
        dlg.setMinimumWidth(430)
        dlg.setStyleSheet(f"QDialog {{ {Styles.get_dialog_surface_style()} }}")
        root = QVBoxLayout(dlg)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(14)
        root.addWidget(
            Label("A paused batch is waiting.", role=TextRole.SUBHEADING, weight=700)
        )
        root.addWidget(
            Label(
                "Resume it, discard it and start the new selection, or cancel.",
                role=TextRole.BODY,
                tone=TextTone.SECONDARY,
                wrap=True,
            )
        )
        row = QHBoxLayout()
        row.addStretch()
        cancel = Button(
            "Cancel", ButtonVariant.HOLLOW, on_click=dlg.reject
        )
        discard = Button(
            "Discard and start new",
            ButtonVariant.DANGER,
            on_click=lambda: dlg.done(2),
        )
        resume = Button(
            "Resume", ButtonVariant.PRIMARY, on_click=lambda: dlg.done(1)
        )
        row.addWidget(cancel)
        row.addWidget(discard)
        row.addWidget(resume)
        root.addLayout(row)
        code = dlg.exec()
        return {1: "resume", 2: "discard"}.get(code, "cancel")


def _intent_for_status(status: str | None) -> str:
    value = str(status or "").strip().lower()
    if value == "completed":
        return INTENT_SKIP
    if value == "paused":
        return INTENT_RESUME
    return INTENT_ANALYZE
