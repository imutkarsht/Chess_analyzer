"""Lifecycle contract for the MainWindow analysis controller."""

from __future__ import annotations

from PyQt6.QtCore import QObject, QTimer, pyqtSignal
from PyQt6.QtWidgets import QWidget

from src.gui.app.analysis_controller import AnalysisController


class _StubWorker(QObject):
    progress = pyqtSignal(int, int)
    move_analyzed = pyqtSignal(int, dict)
    finished = pyqtSignal(object)
    cancelled = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self) -> None:
        super().__init__()
        self.stopped = False
        self._running = True

    def isRunning(self) -> bool:
        return self._running

    def stop(self) -> None:
        self.stopped = True
        self._running = False

    def wait(self, *_args) -> None:
        pass


def test_controller_attaches_to_the_window_and_shutdown_releases_state(qapp):
    host = QWidget()
    controller = AnalysisController()
    worker = _StubWorker()
    timer = QTimer()

    controller.attach(host)
    controller.worker = worker
    controller._analysis_ui_timer = timer

    controller.shutdown()

    assert controller.parent() is host
    assert worker.stopped is True
    assert controller.worker is None
    assert controller._analysis_ui_timer is None

    host.deleteLater()
