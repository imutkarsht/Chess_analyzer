"""Lifecycle contract for the MainWindow batch controller."""

from __future__ import annotations

from types import SimpleNamespace

from PyQt6.QtCore import QObject
from PyQt6.QtWidgets import QWidget

from src.gui.app.batch_controller import BatchController


class _StubBatchWorker(QObject):
    def __init__(self) -> None:
        super().__init__()
        self.paused = False
        self.blocked = False
        self._running = True

    def blockSignals(self, block: bool) -> bool:
        self.blocked = block
        return True

    def isRunning(self) -> bool:
        return self._running

    def pause(self) -> None:
        self.paused = True

    def wait(self) -> None:
        self._running = False


def test_controller_attaches_and_shutdown_pauses_the_batch_worker(qapp):
    host = QWidget()
    host.history_manager = SimpleNamespace(set_analysis_batch_elapsed=lambda _s: None)
    host.analyzer = SimpleNamespace(
        engine_manager=SimpleNamespace(stop_engine=lambda: None)
    )
    host.analysis_coordinator = SimpleNamespace(active_game_id="game-1")

    controller = BatchController()
    worker = _StubBatchWorker()
    controller.attach(host)
    controller._batch_worker = worker

    controller.shutdown()

    assert controller.parent() is host
    assert controller._batch_closing is True
    assert worker.blocked is True
    assert worker.paused is True
    assert controller._batch_worker is None
    assert controller._batch_eta_timer.isActive() is False

    host.deleteLater()
