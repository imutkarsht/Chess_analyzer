# SPDX-License-Identifier: GPL-3.0-only
"""Persisted History batch queue: lifecycle, gating, timing, and recovery."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from PyQt6.QtCore import QObject, QTimer, pyqtSignal
from PyQt6.QtWidgets import QDialog, QHBoxLayout, QVBoxLayout

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
    BatchSummary,
)
from src.gui.analysis.coordinator import AnalysisCoordinator
from src.gui.components import (
    Button,
    ButtonVariant,
    Label,
    TextRole,
    TextTone,
    confirm_dialog,
)
from src.gui.styles import Styles
from src.gui.utils.worker_registry import register_worker, remove_worker
from src.gui.views.history_batch import UpNextEntry
from src.utils.logger import logger
from src.workers.analysis import BatchAnalysisWorker

if TYPE_CHECKING:
    from src.gui.main_window.window import MainWindow


class BatchController(QObject):
    """Own the batch queue lifecycle, gating, and History/Metrics refresh."""

    batch_started = pyqtSignal(object)
    batch_paused = pyqtSignal()
    batch_completed = pyqtSignal()
    batch_cancelled = pyqtSignal()
    batch_failed = pyqtSignal(str)
    batch_state_changed = pyqtSignal(str)
    batch_progress = pyqtSignal(int, int)

    def __init__(self) -> None:
        super().__init__()
        self.host: MainWindow | None = None
        self._batch_worker: BatchAnalysisWorker | None = None
        self._batch_closing = False
        self._batch_active_label = ""
        self._batch_elapsed_base = 0.0
        self._batch_session_started_at: float | None = None
        self._batch_game_started_at: float | None = None
        self._batch_current_move = 0
        self._batch_current_total = 0
        self._batch_snapshot: AnalysisBatch | None = None
        self._batch_summary: BatchSummary | None = None
        self._batch_up_next_cache: dict[str, UpNextEntry] = {}
        self._batch_eta_timer = QTimer(self)
        self._batch_eta_timer.setInterval(1000)
        self._batch_eta_timer.timeout.connect(self._tick_batch_timing)
        self._initialized = False

    def attach(self, host: MainWindow) -> None:
        self.host = host
        self.setParent(host)

    def init(self) -> None:
        """Wire History signals and recover any persisted queue."""
        if self._initialized:
            return
        self._initialized = True
        self.host.analysis_coordinator = AnalysisCoordinator()
        self.host.history_view.batch_analysis_requested.connect(
            self.start_batch_analysis
        )
        self.host.history_view.batch_control_requested.connect(self._on_batch_control)
        self.host.history_view.batch_reorder_requested.connect(self._on_batch_reorder)
        self.host.history_view.batch_remove_requested.connect(self._on_batch_remove)
        self.host.history_view.batch_up_next_refresh_requested.connect(
            self._refresh_up_next
        )
        self.host.history_view.history_cleared.connect(self._on_batch_history_cleared)
        self._recover_persisted_batch()

    def shutdown(self) -> None:
        self._stop_batch_for_exit()

    def _recover_persisted_batch(self) -> None:
        try:
            if self.host.history_manager.pause_interrupted_analysis_batch():
                logger.info("Recovered a running batch as paused")
            batch = self.host.history_manager.get_analysis_batch()
            if batch is None:
                return
            if batch.total == 0:
                self.host.history_manager.delete_analysis_batch()
                return
            if batch.state in (BATCH_RUNNING, BATCH_PAUSED):
                batch = reconcile_batch(batch, self._batch_statuses(batch))
                self.host.history_manager.save_analysis_batch_items(batch.items)
                if not batch.actionable_items():
                    batch.state = BATCH_COMPLETED
                    self.host.history_manager.set_analysis_batch_state(BATCH_COMPLETED)
                else:
                    batch.state = BATCH_PAUSED
                    self.host.history_manager.set_analysis_batch_state(BATCH_PAUSED)
            self._batch_elapsed_base = max(0.0, float(batch.elapsed_seconds or 0.0))
            self._batch_session_started_at = None
            self._set_batch_snapshot(batch)
            self.host.analysis_coordinator.restore_batch(
                batch.state,
                batch.total,
                {item.game_id for item in batch.actionable_items()},
            )
            self.host.history_view.set_batch_queue(batch)
            self._load_up_next_cache(batch)
            self._refresh_up_next()
        except Exception as e:
            logger.error("Failed to restore the batch queue: %s", e, exc_info=True)

    # ------------------------------------------------------------------
    # Start / resume
    # ------------------------------------------------------------------

    def start_batch_analysis(self, game_ids) -> None:
        ids = list(dict.fromkeys(game_ids or []))
        coordinator = self.host.analysis_coordinator
        if not coordinator.can_start_batch():
            message = (
                "A batch analysis is already running."
                if coordinator.batch_running
                else "An analysis is already running. Stop it before starting a batch."
            )
            self.host.show_toast(message, "warning")
            return
        if self._batch_worker is not None:
            self.host.show_toast("The previous batch is still finishing.", "warning")
            return
        if self.host.analysis_controller.is_running:
            self.host.show_toast("An analysis is already running.", "warning")
            return

        existing = self.host.history_manager.get_analysis_batch()
        if existing is not None:
            if existing.state == BATCH_RUNNING:
                self.host.show_toast("A batch analysis is already running.", "warning")
                return
            if existing.state == BATCH_PAUSED and existing.actionable_items():
                choice = self._resolve_paused_batch_conflict()
                if choice == "resume":
                    self._resume_batch()
                    return
                if choice == "cancel":
                    return
            self.host.history_manager.delete_analysis_batch()
            self.host.history_view.hide_batch_queue()

        if not ids:
            return
        if not self.host.analysis_controller._ensure_engine_ready():
            return

        try:
            rows = self.host.history_manager.fetch_game_rows_by_ids(ids)
        except Exception as e:
            logger.error("Failed to prepare batch rows: %s", e)
            self.host.show_toast(f"Could not prepare batch: {e}", "error")
            return
        by_id = {row["id"]: row for row in rows}
        valid_ids = [game_id for game_id in ids if game_id in by_id]
        if not valid_ids:
            self.host.show_toast("Those games are no longer in History.", "warning")
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
            batch = self.host.history_manager.save_analysis_batch(batch)
        except Exception as e:
            logger.error("Failed to create batch queue: %s", e)
            self.host.show_toast(f"Could not create batch queue: {e}", "error")
            return

        if not coordinator.begin_batch(
            [item.game_id for item in items], total=batch.total
        ):
            self.host.show_toast("An analysis is already running.", "warning")
            return

        self.host.history_view.on_batch_started(batch)
        self._start_batch_worker(batch)
        self.batch_started.emit(batch)
        self.batch_state_changed.emit(BATCH_RUNNING)

    def _resume_batch(self) -> None:
        coordinator = self.host.analysis_coordinator
        if not coordinator.can_start_batch():
            self.host.show_toast(
                "An analysis is already running. Finish it before resuming the batch.",
                "warning",
            )
            return
        if self._batch_worker is not None:
            self.host.show_toast("The previous batch is still finishing.", "warning")
            return
        if self.host.analysis_controller.is_running:
            self.host.show_toast("An analysis is already running.", "warning")
            return
        batch = self.host.history_manager.get_analysis_batch()
        if batch is None or batch.state != BATCH_PAUSED:
            return
        batch = reconcile_batch(batch, self._batch_statuses(batch))
        self.host.history_manager.save_analysis_batch_items(batch.items)
        if not batch.actionable_items():
            batch.state = BATCH_COMPLETED
            self.host.history_manager.set_analysis_batch_state(BATCH_COMPLETED)
            self.host.history_view.refresh_batch_queue()
            return
        if not self.host.analysis_controller._ensure_engine_ready():
            return

        batch.state = BATCH_RUNNING
        self.host.history_manager.set_analysis_batch_state(BATCH_RUNNING)
        if not coordinator.begin_batch(
            [item.game_id for item in batch.actionable_items()], total=batch.total
        ):
            self.host.show_toast("An analysis is already running.", "warning")
            return
        self.host.history_view.on_batch_started(batch)
        self._start_batch_worker(batch)
        self.host._set_status("Resuming batch analysis", "progress")
        self.batch_started.emit(batch)
        self.batch_state_changed.emit(BATCH_RUNNING)

    def _start_batch_worker(self, batch: AnalysisBatch) -> None:
        if self._batch_worker is not None and self._batch_worker.isRunning():
            return
        self._set_batch_snapshot(batch)
        self._load_up_next_cache(batch)
        self._refresh_up_next()
        worker = BatchAnalysisWorker(
            self.host.analyzer, batch, self.host.history_manager, parent=self.host
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
        self._batch_elapsed_base = max(0.0, float(batch.elapsed_seconds or 0.0))
        self._batch_session_started_at = time.monotonic()
        self._batch_game_started_at = None
        self._batch_current_move = 0
        self._batch_current_total = 0
        self.host.history_view.set_batch_timing(self._batch_total_elapsed(), None)
        self._batch_eta_timer.start()
        register_worker(worker)

        self.host._stop_replay()
        self.host._exit_variation()
        self._set_batch_engine_lock(True)
        self.host._set_engine_state("calculating", "Starting...")
        self.host._set_status("Starting batch analysis...", "progress")
        worker.start()

    # ------------------------------------------------------------------
    # Worker callbacks
    # ------------------------------------------------------------------

    def _on_batch_game_started(
        self, game_id, position, total, action, label, total_moves
    ) -> None:
        if self._batch_closing:
            return
        self._batch_active_label = label
        self._batch_game_started_at = time.monotonic()
        self._batch_current_move = 0
        self._batch_current_total = max(0, int(total_moves))
        batch = self._current_batch()
        queued = {item.game_id for item in (batch.pending_items() if batch else [])}
        queued.discard(game_id)
        self.host.analysis_coordinator.set_batch_runtime(
            game_id, position, total, queued_game_ids=queued
        )
        self._batch_up_next_cache.pop(game_id, None)
        self.host.history_view.remove_batch_up_next(game_id)
        self._refresh_up_next()
        self.host.history_view.set_batch_active(
            game_id,
            label,
            position,
            total,
            queued,
            batch=batch,
            total_moves=self._batch_current_total,
            depth=self.host.analyzer.config.get("depth"),
        )
        self.host._set_engine_state("calculating", f"{position}/{total}")
        self.host._set_status(f"Batch {position}/{total} · {label}", "progress")
        self.host.analysis_controller._update_analyze_button(running=False)
        self._tick_batch_timing()

    def _on_batch_game_progress(self, game_id, current, total_moves) -> None:
        if self._batch_closing:
            return
        if self.host.analysis_coordinator.active_game_id != game_id:
            return
        self._batch_current_move = max(0, int(current))
        self._batch_current_total = max(0, int(total_moves))
        game_elapsed = (
            max(0.0, time.monotonic() - self._batch_game_started_at)
            if self._batch_game_started_at is not None
            else 0.0
        )
        self.host.history_view.update_batch_move_progress(
            current, total_moves, self._current_game_eta(), game_elapsed
        )
        self._tick_batch_timing()
        self.batch_progress.emit(current, total_moves)

    def _on_batch_game_outcome(self, game_id, _outcome, error) -> None:
        if self._batch_closing:
            return
        if error:
            logger.warning("Batch game %s failed: %s", game_id, error)
        self._persist_batch_elapsed()
        if game_id == self.host.analysis_coordinator.active_game_id:
            self._batch_game_started_at = None
            self._batch_current_move = 0
        self.host.history_view.refresh_game(game_id)
        self._batch_up_next_cache.pop(game_id, None)
        self.host.history_view.remove_batch_up_next(game_id)
        batch = self._current_batch()
        self._set_batch_snapshot(batch)
        if batch is not None:
            queued = {item.game_id for item in batch.pending_items()}
            queued.discard(self.host.analysis_coordinator.active_game_id)
            self.host.analysis_coordinator.set_batch_runtime(
                self.host.analysis_coordinator.active_game_id,
                self.host.analysis_coordinator.active_position,
                self.host.analysis_coordinator.batch_total,
                queued_game_ids=queued,
            )
            self.host.history_view.set_batch_queue(
                batch,
                active_label=self._batch_active_label,
                position=self.host.analysis_coordinator.active_position,
            )
        self._refresh_up_next()
        if self.host.metrics_view is not None:
            self.host.metrics_view.mark_dirty()

    def _on_batch_paused(self, _summary) -> None:
        if self._batch_closing:
            return
        self._finish_batch_state(BATCH_PAUSED, "Batch paused", "info")

    def _on_batch_cancelled(self, _summary) -> None:
        if self._batch_closing:
            return
        self._finish_batch_state(BATCH_CANCELLED, "Batch cancelled", "info")

    def _on_batch_finished(self, _summary) -> None:
        if self._batch_closing:
            return
        self._finish_batch_state(BATCH_COMPLETED, "Batch complete", "success")

    def _on_batch_failed(self, _summary, error) -> None:
        if self._batch_closing:
            return
        self._finish_batch_state(BATCH_FAILED, f"Batch stopped: {error}", "error")

    def _finish_batch_state(self, state: str, message: str, kind: str) -> None:
        elapsed = self._batch_total_elapsed()
        self._batch_eta_timer.stop()
        self._persist_batch_elapsed(elapsed)
        self._batch_elapsed_base = elapsed
        self._batch_session_started_at = None
        self._batch_game_started_at = None
        self._batch_current_move = 0
        self.host.analysis_coordinator.end_batch(state)
        self._batch_active_label = ""
        self.host.history_view.set_batch_timing(elapsed, None)
        if self._batch_worker is None or not self._batch_worker.isRunning():
            self._set_batch_engine_lock(False)
        self.host.history_view.set_batch_running(False)
        self.host.history_view.load_history()
        self.host.history_view.refresh_batch_queue()
        self._refresh_batch_snapshot()
        self._refresh_up_next()
        self.host._set_engine_state("ready")
        self.host._set_status(message, kind)
        self.host.analysis_controller._update_analyze_button(running=False)
        if self.host.metrics_view is not None:
            self.host.metrics_view.mark_dirty()
            if self.host.stack.currentIndex() == 3:
                self.host.metrics_view.refresh(force=True)
        if state == BATCH_FAILED:
            self.host.show_toast(message, "error")
        self.batch_state_changed.emit(state)
        if state == BATCH_PAUSED:
            self.batch_paused.emit()
        elif state == BATCH_CANCELLED:
            self.batch_cancelled.emit()
        elif state == BATCH_COMPLETED:
            self.batch_completed.emit()
        elif state == BATCH_FAILED:
            self.batch_failed.emit(message)

    # ------------------------------------------------------------------
    # Controls
    # ------------------------------------------------------------------

    def _on_batch_control(self, action: str) -> None:
        if self._batch_closing:
            return
        if action == "pause":
            if self._batch_worker is not None and self._batch_worker.isRunning():
                self.host.history_view.batch_queue_card.btn_pause.setEnabled(False)
                self.host.history_view.batch_queue_card.btn_pause.setText("Pausing…")
                self.host._set_status("Pausing batch...", "warning")
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
                self.host,
                "Cancel Batch",
                "Cancel this batch? The current game's partial analysis will be saved, "
                "and remaining games will not be analyzed.",
                confirm_label="Cancel batch",
            ):
                return
            self.host.history_view.batch_queue_card.btn_cancel.setEnabled(False)
            self.host._set_status("Cancelling batch...", "warning")
            worker.cancel()
            return
        if batch.state != BATCH_PAUSED:
            return
        if not confirm_dialog(
            self.host,
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
        self.host.history_manager.save_analysis_batch_items(items)
        self.host.history_manager.set_analysis_batch_state(BATCH_CANCELLED)
        self._finish_batch_state(BATCH_CANCELLED, "Batch cancelled", "info")

    def _dismiss_batch(self) -> None:
        batch = self._current_batch()
        if batch is None or batch.state == BATCH_RUNNING:
            return
        self._batch_eta_timer.stop()
        self.host.history_manager.delete_analysis_batch()
        self.host.history_view.hide_batch_queue()
        self.host.analysis_coordinator.reset()
        self._set_batch_snapshot(None)
        self._batch_up_next_cache.clear()
        self._batch_elapsed_base = 0.0
        self._batch_session_started_at = None
        self._batch_game_started_at = None
        self.host.analysis_controller._update_analyze_button(running=False)

    # ------------------------------------------------------------------
    # External single-analysis sync
    # ------------------------------------------------------------------

    def _sync_paused_batch(self, game_id: str | None = None) -> None:
        batch = self._current_batch()
        if batch is None or batch.state != BATCH_PAUSED:
            return
        try:
            batch = reconcile_batch(batch, self._batch_statuses(batch))
            self.host.history_manager.save_analysis_batch_items(batch.items)
            if not batch.actionable_items():
                batch.state = BATCH_COMPLETED
                self.host.history_manager.set_analysis_batch_state(BATCH_COMPLETED)
            self._set_batch_snapshot(batch)
            self.host.analysis_coordinator.restore_batch(
                batch.state,
                batch.total,
                {item.game_id for item in batch.actionable_items()},
            )
            self.host.history_view.refresh_batch_queue()
            if game_id:
                self.host.history_view.refresh_game(game_id)
        except Exception as e:
            logger.error("Failed to sync paused batch: %s", e)

    # ------------------------------------------------------------------
    # Queue ordering
    # ------------------------------------------------------------------

    def _on_batch_reorder(self, game_ids) -> None:
        if self._batch_closing:
            return
        if (
            self.host.history_manager.reorder_analysis_batch_items(
                list(game_ids), active_game_id=self.host.analysis_coordinator.active_game_id
            )
            is False
        ):
            logger.debug("Batch reorder no longer matched the persisted queue")
        self._refresh_batch_snapshot()

    def _on_batch_remove(self, game_id: str) -> None:
        if self._batch_closing:
            return
        if game_id == self.host.analysis_coordinator.active_game_id:
            return
        self.host.history_manager.remove_analysis_batch_item(game_id)
        self._batch_up_next_cache.pop(game_id, None)
        batch = self._refresh_batch_snapshot()
        if batch is not None:
            self.host.history_view.set_batch_queue(
                batch, active_label=self._batch_active_label
            )
        self._refresh_up_next()

    def _load_up_next_cache(self, batch: AnalysisBatch) -> None:
        self._batch_up_next_cache = {}
        self._ensure_up_next_cache(
            batch,
            [
                item.game_id
                for item in batch.items
                if item.outcome == OUTCOME_PENDING
            ],
        )

    def _ensure_up_next_cache(
        self, batch: AnalysisBatch, game_ids: list[str]
    ) -> None:
        missing = [
            game_id
            for game_id in game_ids
            if game_id not in self._batch_up_next_cache
        ]
        if not missing:
            return
        try:
            rows = self.host.history_manager.fetch_game_rows_by_ids(missing)
        except Exception as e:  # pragma: no cover - defensive
            logger.debug("Failed to load Up next rows: %s", e)
            return
        by_id = {row.get("id"): row for row in rows}
        for game_id in missing:
            row = by_id.get(game_id)
            if row is None:
                continue
            item = batch.item(game_id)
            self._batch_up_next_cache[game_id] = UpNextEntry(
                game_id=game_id,
                label=f"{row.get('white', '?')} vs {row.get('black', '?')}",
                moves=int(row.get("move_count") or 0),
                number=item.position if item is not None else 0,
            )

    def _refresh_up_next(self) -> None:
        if self._batch_closing:
            return
        batch = self._batch_snapshot
        if batch is None:
            batch = self._refresh_batch_snapshot()
        if batch is None or batch.state not in (BATCH_RUNNING, BATCH_PAUSED):
            self._batch_up_next_cache.clear()
            self.host.history_view.set_batch_up_next([])
            return
        active_id = self.host.analysis_coordinator.active_game_id
        pending = [
            item
            for item in batch.items
            if item.outcome == OUTCOME_PENDING and item.game_id != active_id
        ]
        if not pending:
            self.host.history_view.set_batch_up_next([])
            return
        self._ensure_up_next_cache(batch, [item.game_id for item in pending])
        seconds_per_move = self._estimated_seconds_per_move()
        entries = []
        for item in pending:
            cached = self._batch_up_next_cache.get(item.game_id)
            if cached is None:
                continue
            entries.append(
                UpNextEntry(
                    game_id=cached.game_id,
                    label=cached.label,
                    moves=cached.moves,
                    eta_seconds=seconds_per_move * max(1, cached.moves * 2),
                    number=int(item.position),
                )
            )
        self.host.history_view.set_batch_up_next(entries)

    def _estimated_seconds_per_move(self) -> float:
        if self._batch_current_move > 0 and self._batch_game_started_at is not None:
            elapsed = max(0.0, time.monotonic() - self._batch_game_started_at)
            if elapsed > 0:
                return elapsed / self._batch_current_move
        try:
            return float(self.host.analyzer.config.get("time_per_move") or 1.0)
        except (TypeError, ValueError):
            return 1.0

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _on_batch_history_cleared(self) -> None:
        if self._batch_worker is not None:
            return
        self._batch_eta_timer.stop()
        self._set_batch_snapshot(None)
        self._batch_up_next_cache.clear()
        self.host.analysis_coordinator.reset()

    def _batch_statuses(self, batch: AnalysisBatch) -> dict[str, str | None]:
        game_ids = [item.game_id for item in batch.items]
        try:
            rows = self.host.history_manager.fetch_game_rows_by_ids(game_ids)
        except Exception as e:  # pragma: no cover - defensive
            logger.debug("Failed to load batch statuses: %s", e)
            rows = []
        by_id = {row.get("id"): row for row in rows}
        statuses: dict[str, str | None] = {}
        legacy_ids = []
        for game_id in game_ids:
            row = by_id.get(game_id)
            if row is None:
                statuses[game_id] = None
            elif row.get("analysis_status"):
                statuses[game_id] = str(row["analysis_status"])
            else:
                legacy_ids.append(game_id)
        for game_id in legacy_ids:
            statuses[game_id] = self.host.history_manager.get_game_analysis_status(game_id)
        return statuses

    def _current_batch(self) -> AnalysisBatch | None:
        try:
            return self.host.history_manager.get_analysis_batch()
        except Exception as e:
            logger.debug("Failed to load batch queue: %s", e)
            return None

    def _set_batch_snapshot(self, batch: AnalysisBatch | None) -> None:
        self._batch_snapshot = batch
        self._batch_summary = batch.summary() if batch is not None else None

    def _refresh_batch_snapshot(self) -> AnalysisBatch | None:
        batch = self._current_batch()
        self._set_batch_snapshot(batch)
        return batch

    def _set_batch_engine_lock(self, locked: bool) -> None:
        if hasattr(self.host, "move_list_panel"):
            self.host.move_list_panel.set_analysis_locked(locked)
        if hasattr(self.host, "explorer_view"):
            self.host.explorer_view.set_analysis_locked(locked)
        if hasattr(self.host, "analysis_panel"):
            self.host.analysis_panel.toggle_checkbox.setEnabled(not locked)
        if hasattr(self.host, "btn_analyze"):
            self.host.analysis_controller._update_analyze_button(running=False)

    def _batch_total_elapsed(self) -> float:
        if self._batch_session_started_at is None:
            return max(0.0, self._batch_elapsed_base)
        return max(
            0.0,
            self._batch_elapsed_base
            + (time.monotonic() - self._batch_session_started_at),
        )

    def _current_game_eta(self) -> float | None:
        if (
            self._batch_game_started_at is None
            or self._batch_current_move <= 0
            or self._batch_current_total <= 0
        ):
            return None
        elapsed = max(0.0, time.monotonic() - self._batch_game_started_at)
        seconds_per_move = elapsed / max(1, self._batch_current_move)
        remaining = max(
            0, self._batch_current_total - min(self._batch_current_move, self._batch_current_total)
        )
        return remaining * seconds_per_move

    def _estimate_batch_eta(self) -> float | None:
        if not self.host.analysis_coordinator.batch_running:
            return None
        current_eta = self._current_game_eta()
        if current_eta is None:
            return None
        summary = self._batch_summary
        if summary is None or self._batch_snapshot is None:
            return None
        position = self.host.analysis_coordinator.active_position or (summary.processed + 1)
        future_games = sum(
            1
            for item in self._batch_snapshot.items
            if item.position > position and item.outcome == OUTCOME_PENDING
        )
        if future_games == 0:
            return current_eta

        analyzed_games = summary.completed + summary.failed
        if analyzed_games > 0:
            average_game = self._batch_total_elapsed() / analyzed_games
        else:
            seconds_per_move = (
                time.monotonic() - self._batch_game_started_at
            ) / max(1, self._batch_current_move)
            average_game = seconds_per_move * self._batch_current_total
        return current_eta + future_games * average_game

    def _tick_batch_timing(self) -> None:
        if not self.host.analysis_coordinator.batch_running:
            return
        self.host.history_view.set_batch_timing(
            self._batch_total_elapsed(), self._estimate_batch_eta()
        )

    def _persist_batch_elapsed(self, seconds: float | None = None) -> None:
        try:
            self.host.history_manager.set_analysis_batch_elapsed(
                self._batch_total_elapsed() if seconds is None else seconds
            )
        except Exception as e:  # pragma: no cover - defensive
            logger.debug("Failed to persist batch elapsed time: %s", e)

    def _release_batch_worker(self, worker) -> None:
        if self._batch_worker is worker:
            self._batch_worker = None
        if not self._batch_closing:
            self._set_batch_engine_lock(False)
        remove_worker(worker)

    def _stop_batch_for_exit(self) -> None:
        if self._batch_closing:
            return
        self._batch_closing = True
        self._batch_eta_timer.stop()
        worker = self._batch_worker
        if worker is not None:
            # Do not let queued progress/finished slots run after wait() while
            # the window is being torn down.
            worker.blockSignals(True)
            if worker.isRunning():
                logger.info(
                    "Pausing batch before exit (active game: %s, elapsed %.1fs)",
                    self.host.analysis_coordinator.active_game_id,
                    self._batch_total_elapsed(),
                )
                worker.pause()
                worker.wait()
            remove_worker(worker)
        elapsed = self._batch_total_elapsed()
        self._persist_batch_elapsed(elapsed)
        self._batch_elapsed_base = elapsed
        self._batch_session_started_at = None
        self._batch_worker = None
        try:
            self.host.analyzer.engine_manager.stop_engine()
        except Exception as e:  # pragma: no cover - defensive
            logger.debug("Failed to stop engine on exit: %s", e)

    def _resolve_paused_batch_conflict(self) -> str:
        dlg = QDialog(self.host)
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
