"""Shared base for settings cards that run work off the UI thread."""

from collections.abc import Callable

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QGroupBox

from ...components.toast import ToastHandle, ToastManager
from ...styles import Styles
from .background_worker import BackgroundTaskWorker

# Workers are deliberately not parented to their card: Qt destroys children
# with the widget, and destroying a running QThread aborts the process. This
# registry keeps an in-flight task alive if the page closes mid-operation.
_ACTIVE_WORKERS: set[BackgroundTaskWorker] = set()


def _retire_worker(worker: BackgroundTaskWorker) -> None:
    _ACTIVE_WORKERS.discard(worker)
    worker.deleteLater()


class BackgroundTaskCard(QGroupBox):
    """A settings card that runs at most one background task at a time.

    Slow work (VACUUM, backup, profile fetch, token check) is dispatched to a
    worker thread while the card's action buttons are disabled, so a second
    click cannot start a competing pass.
    """

    data_changed = pyqtSignal()

    def __init__(self, title: str, parent=None):
        super().__init__(title, parent)
        self._worker: BackgroundTaskWorker | None = None
        self._busy_widgets = []
        self._task_toast: ToastHandle | None = None
        self.setStyleSheet(Styles.get_group_box_style())

    def register_busy_widgets(self, *widgets) -> None:
        """Buttons disabled while a task is running."""
        self._busy_widgets.extend(widget for widget in widgets if widget is not None)

    def is_busy(self) -> bool:
        return bool(self._worker is not None and self._worker.isRunning())

    def run_task(
        self,
        task: Callable[[], object],
        on_success: Callable[[object], None],
        on_error: Callable[[str], None] | None = None,
        *,
        loading_message: str | None = None,
    ) -> None:
        if self.is_busy():
            return
        self._set_busy(True)
        if loading_message:
            # Long local operations read as a loading toast that morphs into
            # the card's success message instead of blocking silently.
            self._task_toast = ToastManager.loading(
                self, loading_message, duration=0
            )
        worker = BackgroundTaskWorker(task)
        _ACTIVE_WORKERS.add(worker)
        worker.completed.connect(on_success)
        worker.failed.connect(on_error or self._report_error)
        worker.finished.connect(self._on_task_finished)
        worker.finished.connect(lambda: _retire_worker(worker))
        self._worker = worker
        worker.start()

    def _on_task_finished(self) -> None:
        self._set_busy(False)
        if self._task_toast is not None and self._task_toast.active:
            # The callback produced no message; do not leave a spinner behind.
            self._task_toast.dismiss()
        self._task_toast = None
        worker = self.sender()
        if worker is self._worker:
            self._worker = None

    def _set_busy(self, busy: bool) -> None:
        for widget in self._busy_widgets:
            widget.setEnabled(not busy)

    def _toast(self, message: str, variant: str = "success") -> None:
        """Report a finished task through the toast that was already showing."""
        if self._task_toast is not None and self._task_toast.active:
            self._task_toast.update(message, variant=variant)
            self._task_toast = None
            return
        ToastManager.show(self, message, variant)

    def _report_error(self, message: str) -> None:
        message = message or "Operation failed."
        if self._task_toast is not None and self._task_toast.active:
            self._task_toast.update(message, variant="error")
            self._task_toast = None
            return
        ToastManager.error(self, message)
