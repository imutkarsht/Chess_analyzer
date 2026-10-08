"""
API Worker thread for background network requests.
"""
from PyQt6.QtCore import QThread, pyqtSignal

from src.utils.logger import logger

_RUNNING_WORKERS = []

def register_worker(worker):
    _RUNNING_WORKERS.append(worker)

def remove_worker(worker):
    if worker in _RUNNING_WORKERS:
        try:
            _RUNNING_WORKERS.remove(worker)
        except ValueError:
            pass

class ApiWorker(QThread):
    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, api_func, *args, **kwargs):
        parent = kwargs.pop('parent', None)
        super().__init__(parent)
        self.api_func = api_func
        self.args = args
        self.kwargs = kwargs
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        func_name = getattr(self.api_func, "__name__", str(self.api_func))
        logger.debug(f"ApiWorker started: {func_name}")
        try:
            res = self.api_func(*self.args, **self.kwargs)
            if self._cancelled:
                logger.debug(f"ApiWorker cancelled: {func_name}")
                return
            logger.debug(f"ApiWorker completed: {func_name}")
            self.finished.emit(res)
        except Exception as e:
            if not self._cancelled:
                logger.error(f"ApiWorker failed ({func_name}): {e}")
                self.error.emit(str(e))
