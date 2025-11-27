from PyQt6.QtCore import QThread, pyqtSignal
from ..backend.analyzer import Analyzer
from ..backend.models import GameAnalysis

class AnalysisWorker(QThread):
    progress = pyqtSignal(int, int) # current, total
    finished = pyqtSignal(object) # GameAnalysis
    error = pyqtSignal(str)

    def __init__(self, analyzer: Analyzer, game: GameAnalysis):
        super().__init__()
        self.analyzer = analyzer
        self.game = game
        self._is_running = True

    def run(self):
        try:
            # We need to modify the analyzer to accept a check for cancellation
            # For now, we just pass the callback
            def callback(current, total):
                if not self._is_running:
                    raise InterruptedError("Analysis cancelled")
                self.progress.emit(current, total)

            self.analyzer.analyze_game(self.game, callback=callback)
            self.finished.emit(self.game)
        except InterruptedError:
            pass # Just stop
        except Exception as e:
            self.error.emit(str(e))

    def stop(self):
        self._is_running = False
