from PyQt6.QtCore import QThread, pyqtSignal
from src.backend.analysis.analyzer import Analyzer
from src.backend.storage.models import GameAnalysis

class AnalysisWorker(QThread):
    progress = pyqtSignal(int, int) # current, total
    move_analyzed = pyqtSignal(int, object) # move_index, data_dict
    finished = pyqtSignal(object) # GameAnalysis
    error = pyqtSignal(str)

    def __init__(self, analyzer: Analyzer, game: GameAnalysis):
        super().__init__()
        self.analyzer = analyzer
        self.game = game
        self._is_running = True

    def run(self):
        try:
            def callback(current, total, move_data=None):
                if not self._is_running:
                    raise InterruptedError("Analysis cancelled")
                self.progress.emit(current, total)
                if move_data is not None:
                    move_index = move_data.get("index", current - 1)
                    self.move_analyzed.emit(move_index, move_data)

            self.analyzer.analyze_game(self.game, callback=callback)
            self.finished.emit(self.game)
        except InterruptedError:
            pass
        except Exception as e:
            self.error.emit(str(e))

    def stop(self):
        self._is_running = False
