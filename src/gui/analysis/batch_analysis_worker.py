# SPDX-License-Identifier: GPL-3.0-only
"""Qt worker adapter for the sequential batch-analysis runner."""

from __future__ import annotations

import threading

import chess.engine
from PyQt6.QtCore import QThread, pyqtSignal

from src.backend.analysis.analyzer import Analyzer
from src.backend.analysis.batch import BatchAnalysisRunner
from src.backend.models.analysis_batch import (
    BATCH_CANCELLED,
    BATCH_COMPLETED,
    BATCH_FAILED,
    BATCH_PAUSED,
    BATCH_RUNNING,
    OUTCOME_NOT_STARTED,
    OUTCOME_PENDING,
    AnalysisBatch,
    BatchEvent,
    GameOutcomeEvent,
    GameProgress,
    GameStarted,
)
from src.backend.storage.game_history import GameHistoryManager
from src.utils.logger import logger


class BatchAnalysisWorker(QThread):
    """Run one persisted queue sequentially through the existing Analyzer."""

    game_started = pyqtSignal(str, int, int, str, str, int)
    game_progress = pyqtSignal(str, int, int)
    game_outcome = pyqtSignal(str, str, str)
    batch_paused = pyqtSignal(object)
    batch_cancelled = pyqtSignal(object)
    batch_finished = pyqtSignal(object)
    batch_failed = pyqtSignal(object, str)

    def __init__(
        self,
        analyzer: Analyzer,
        batch: AnalysisBatch,
        history_manager: GameHistoryManager,
        parent=None,
    ):
        super().__init__(parent)
        self._analyzer = analyzer
        self._batch = batch
        self._history_manager = history_manager
        self._cancel_token = threading.Event()
        self._pause_requested = threading.Event()
        self._cancel_requested = threading.Event()

    def run(self) -> None:
        result = None
        try:
            self._history_manager.set_analysis_batch_state(BATCH_RUNNING)
            self._batch = self._history_manager.get_analysis_batch() or self._batch
            runner = BatchAnalysisRunner(
                load_game=self._history_manager.get_game_analysis,
                load_status=self._load_status,
                analyze_game=self._analyze_game,
                is_fatal=self._is_fatal,
            )
            result = runner.run(
                self._batch.items,
                cancel_token=self._cancel_token,
                on_event=self._on_event,
            )
        except Exception as error:  # noqa: BLE001 - reported to the UI
            logger.error("Batch analysis worker failed: %s", error, exc_info=True)
            self._fail_unexpected(error)
            return
        finally:
            engine_manager = getattr(self._analyzer, "engine_manager", None)
            if engine_manager is not None:
                try:
                    engine_manager.stop_engine()
                except Exception as error:  # pragma: no cover - defensive
                    logger.debug("Failed to stop engine after batch: %s", error)

        self._finish(result)

    def pause(self) -> None:
        """Stop the active game safely; the queue remains resumable."""
        if not self.isRunning():
            return
        self._pause_requested.set()
        self._cancel_token.set()
        self._cancel_analyzer()

    def cancel(self) -> None:
        """End the batch; the active game keeps its partial analysis."""
        if not self.isRunning():
            return
        self._cancel_requested.set()
        self._cancel_token.set()
        self._cancel_analyzer()

    def _cancel_analyzer(self) -> None:
        try:
            self._analyzer.cancel()
        except Exception as error:
            logger.debug("Failed to cancel batch analyzer: %s", error)

    def _load_status(self, game_id: str) -> str | None:
        return self._history_manager.get_game_analysis_status(game_id)

    def _analyze_game(self, game, resume, on_progress, cancel_token) -> None:
        self._analyzer.analyze_game(
            game,
            callback=on_progress,
            cancel_token=cancel_token,
            resume=resume,
        )

    @staticmethod
    def _is_fatal(error: BaseException) -> bool:
        return isinstance(
            error,
            (
                chess.engine.EngineError,
                chess.engine.EngineTerminatedError,
                OSError,
            ),
        )

    def _on_event(self, event: BatchEvent) -> None:
        if isinstance(event, GameStarted):
            self.game_started.emit(
                event.game_id,
                event.position,
                event.total,
                event.action,
                event.label,
                event.total_moves,
            )
            return
        if isinstance(event, GameProgress):
            self.game_progress.emit(event.game_id, event.current, event.total_moves)
            return
        if isinstance(event, GameOutcomeEvent):
            item = event.item
            try:
                self._history_manager.set_analysis_batch_item_outcome(
                    item.game_id, item.outcome, item.error
                )
            except Exception as error:  # pragma: no cover - defensive
                logger.error(
                    "Failed to persist batch outcome for %s: %s",
                    item.game_id,
                    error,
                )
            self.game_outcome.emit(item.game_id, item.outcome, item.error or "")

    def _finish(self, result) -> None:
        items = list(result.items)
        if self._cancel_requested.is_set():
            items = _mark_pending_not_started(items)
            state = BATCH_CANCELLED
        elif result.reason == "fatal":
            items = _mark_pending_not_started(items)
            state = BATCH_FAILED
        elif self._pause_requested.is_set() or result.reason == "stopped":
            state = BATCH_PAUSED
        else:
            state = BATCH_COMPLETED

        self._persist_items(items)
        self._persist_state(state)
        batch = AnalysisBatch(state=state, items=items)
        summary = batch.summary()
        if state == BATCH_CANCELLED:
            self.batch_cancelled.emit(summary)
        elif state == BATCH_FAILED:
            self.batch_failed.emit(summary, result.fatal_error or "Batch stopped.")
        elif state == BATCH_PAUSED:
            self.batch_paused.emit(summary)
        else:
            self.batch_finished.emit(summary)

    def _fail_unexpected(self, error: BaseException) -> None:
        batch = None
        try:
            batch = self._history_manager.get_analysis_batch()
        except Exception:  # pragma: no cover - defensive
            pass
        items = _mark_pending_not_started(batch.items if batch else self._batch.items)
        self._persist_items(items)
        self._persist_state(BATCH_FAILED)
        summary = AnalysisBatch(state=BATCH_FAILED, items=items).summary()
        self.batch_failed.emit(summary, str(error))

    def _persist_items(self, items) -> None:
        try:
            self._history_manager.save_analysis_batch_items(list(items))
        except Exception as error:  # pragma: no cover - defensive
            logger.error("Failed to persist batch item outcomes: %s", error)

    def _persist_state(self, state: str) -> None:
        try:
            self._history_manager.set_analysis_batch_state(state)
        except Exception as error:  # pragma: no cover - defensive
            logger.error("Failed to persist batch state %s: %s", state, error)


def _mark_pending_not_started(items):
    return [
        item.with_outcome(OUTCOME_NOT_STARTED)
        if item.outcome == OUTCOME_PENDING
        else item
        for item in items
    ]
