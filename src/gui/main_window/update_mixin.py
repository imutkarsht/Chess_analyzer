from datetime import datetime

from PyQt6.QtCore import QTimer

from src.backend.updater.update_checker import UpdateCheckerWorker
from src.gui.dialogs import UpdateNotificationDialog


class UpdateMixin:
    """Background update checking and notification handling."""

    def check_for_updates(self):
        """Start background update check after a delay (max once per day)."""
        last_check = self.config_manager.get("last_update_check", "")
        today = datetime.now().strftime("%Y-%m-%d")

        if last_check == today:
            return

        self.config_manager.set("last_update_check", today)

        # Delay update check by 2 seconds to ensure splash is gone
        self._update_timer = QTimer(self)
        self._update_timer.setSingleShot(True)
        self._update_timer.timeout.connect(self._start_update_check)
        self._update_timer.start(2000)

    def _start_update_check(self):
        """Actually start the update check."""
        self.update_worker = UpdateCheckerWorker()
        self.update_worker.update_checked.connect(self.on_update_checked)
        self.update_worker.start()

    def on_update_checked(self, update_info):
        """Handle update check result."""
        if update_info.available:
            dialog = UpdateNotificationDialog(update_info, self)
            dialog.exec()
