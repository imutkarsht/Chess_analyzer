"""
API Worker thread for background network requests.
"""
from PyQt6.QtCore import QThread, pyqtSignal

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

    def run(self):
        try:
            res = self.api_func(*self.args, **self.kwargs)
            self.finished.emit(res)
        except Exception as e:
            self.error.emit(str(e))
