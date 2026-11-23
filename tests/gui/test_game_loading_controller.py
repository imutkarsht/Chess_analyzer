"""Lifecycle contract for the MainWindow game-loading controller."""

from __future__ import annotations

from PyQt6.QtCore import QObject
from PyQt6.QtWidgets import QWidget

from src.gui.app.game_loading_controller import GameLoadingController


class _StubIndexWorker(QObject):
    def __init__(self) -> None:
        super().__init__()
        self.cancelled = False
        self._running = True

    def cancel(self) -> None:
        self.cancelled = True

    def isRunning(self) -> bool:
        return self._running

    def wait(self) -> None:
        self._running = False


def test_controller_attaches_and_shutdown_cancels_the_drop_worker(qapp):
    host = QWidget()
    controller = GameLoadingController()
    worker = _StubIndexWorker()

    controller.attach(host)
    controller._pgn_drop_worker = worker

    controller.shutdown()

    assert controller.parent() is host
    assert worker.cancelled is True
    assert controller._pgn_drop_worker is None

    host.deleteLater()
