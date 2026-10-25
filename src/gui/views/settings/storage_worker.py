"""Background worker for slow storage operations (VACUUM, backup, restore)."""

from collections.abc import Callable

from PyQt6.QtCore import QThread, pyqtSignal

from src.utils.logger import logger


class StorageTaskWorker(QThread):
    """Run one storage task off the UI thread.

    VACUUM, backups, and restores can all block for seconds on a large archive,
    so they must never run in a click handler.
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
            logger.error(f"Storage task failed: {e}")
            self.failed.emit(str(e))
            return
        self.completed.emit(result)
