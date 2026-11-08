"""API worker thread for background network requests."""

from PyQt6.QtCore import QThread, pyqtSignal

from src.utils.logger import logger

from .worker_registry import register_worker, remove_worker

__all__ = ["ApiWorker", "register_worker", "remove_worker"]


class ApiWorker(QThread):
    """Run one API call off the UI thread and report the result safely.

    The custom signal is named ``completed`` (not ``finished``) so the built-in
    ``QThread.finished`` remains available for lifecycle cleanup on every exit
    path, including cancellation and errors.
    """

    completed = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, api_func, *args, **kwargs):
        kwargs.pop("parent", None)
        super().__init__(None)
        self.api_func = api_func
        self.args = args
        self.kwargs = kwargs
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        func_name = getattr(self.api_func, "__name__", str(self.api_func))
        logger.debug(f"ApiWorker started: {func_name}")
        try:
            result = self.api_func(*self.args, **self.kwargs)
        except Exception as exc:
            if not self._cancelled:
                logger.error(f"ApiWorker failed ({func_name}): {exc}")
                self.error.emit(str(exc))
            return

        if self._cancelled:
            logger.debug(f"ApiWorker cancelled: {func_name}")
            return

        logger.debug(f"ApiWorker completed: {func_name}")
        self.completed.emit(result)
