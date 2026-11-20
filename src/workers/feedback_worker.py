# SPDX-License-Identifier: GPL-3.0-only
"""Background feedback and review submission worker."""

from PyQt6.QtCore import QThread, pyqtSignal

from src.utils.logger import logger


class FeedbackWorker(QThread):
    """Run a feedback service callable without blocking the Qt event loop."""

    finished = pyqtSignal(bool, str, dict)  # success, message, data

    def __init__(self, target_callable, *args, **kwargs):
        super().__init__()
        self._callable = target_callable
        self._args = args
        self._kwargs = kwargs

    def run(self):
        try:
            success, message, data = self._callable(*self._args, **self._kwargs)
            self.finished.emit(success, message, data)
        except Exception as exc:
            logger.error(f"FeedbackWorker exception: {exc}")
            self.finished.emit(False, f"Error: {exc}", {})


__all__ = ["FeedbackWorker"]
