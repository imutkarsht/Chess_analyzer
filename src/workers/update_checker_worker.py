# SPDX-License-Identifier: GPL-3.0-only
"""Background GitHub release checker for the GUI."""

from PyQt6.QtCore import QThread, pyqtSignal

from src.backend.updater.update_checker import UpdateChecker


class UpdateCheckerWorker(QThread):
    """Background worker — runs UpdateChecker without blocking the UI."""

    update_checked = pyqtSignal(object)  # Emits UpdateInfo

    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        if self._is_cancelled:
            return
        result = UpdateChecker.check_for_updates()
        if not self._is_cancelled:
            self.update_checked.emit(result)


__all__ = ["UpdateCheckerWorker"]
