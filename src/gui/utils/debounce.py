"""Small single-shot debouncer for UI work that must not run per event.

Search boxes, filter changes and re-renders fired from ``textChanged`` are the
usual culprits: they rebuild whole widget trees once per keystroke. Coalescing
them into one deferred call keeps the UI responsive without every view owning
its own timer plumbing.
"""

from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtCore import QObject, QTimer


class Debouncer(QObject):
    """Coalesces repeated ``call`` invocations into one deferred callback."""

    def __init__(self, parent: QObject | None = None, interval: int = 150):
        super().__init__(parent)
        self._callback: Callable[[], None] | None = None
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(interval)
        self._timer.timeout.connect(self.flush)

    @property
    def interval(self) -> int:
        return self._timer.interval()

    @interval.setter
    def interval(self, value: int) -> None:
        self._timer.setInterval(value)

    def call(self, callback: Callable[[], None]) -> None:
        """Schedule ``callback``, replacing any callback still pending."""
        self._callback = callback
        self._timer.start()

    def flush(self) -> None:
        """Run the pending callback immediately (also used by tests)."""
        self._timer.stop()
        callback, self._callback = self._callback, None
        if callback is not None:
            callback()

    def cancel(self) -> None:
        self._timer.stop()
        self._callback = None
