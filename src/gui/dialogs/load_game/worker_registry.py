"""Keep background workers alive until they finish.

Workers are intentionally not parented to the panel that starts them: closing
a dialog while work is in flight must not destroy a running QThread.
"""

from PyQt6.QtCore import QThread

_RUNNING_WORKERS: set[QThread] = set()


def register_worker(worker: QThread) -> None:
    _RUNNING_WORKERS.add(worker)


def remove_worker(worker: QThread) -> None:
    _RUNNING_WORKERS.discard(worker)
    worker.deleteLater()
