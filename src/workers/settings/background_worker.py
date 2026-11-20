"""Background worker for slow settings tasks (storage, network, ...)."""

from collections.abc import Callable

from PyQt6.QtCore import QThread, pyqtSignal

from src.utils.logger import logger


class BackgroundTaskWorker(QThread):
    """Run one task off the UI thread.

    The task may be a VACUUM, a backup, or a network fetch; all of them can
    block for seconds and must never run in a click handler.
    """

    completed = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, task: Callable[[], object], parent=None):
        super().__init__(parent)
        self._task = task

    def run(self) -> None:  # pragma: no cover - exercised through the GUI
        try:
            result = self._task()
        except Exception as e:
            logger.error(f"Background task failed: {e}")
            self.failed.emit(str(e))
            return
        self.completed.emit(result)
