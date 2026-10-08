from PyQt6.QtCore import QThread, pyqtSignal

from src.backend.analysis.analyzer import Analyzer
from src.backend.storage.models import GameAnalysis
from src.utils.logger import logger


class AnalysisWorker(QThread):
    progress = pyqtSignal(int, int)  # current, total
    move_analyzed = pyqtSignal(int, object)  # move_index, data_dict
    finished = pyqtSignal(object)  # GameAnalysis
    error = pyqtSignal(str)

    def __init__(self, analyzer: Analyzer, game: GameAnalysis):
        super().__init__()
        self.analyzer = analyzer
        self.game = game
        self._is_running = True

    def run(self):
        logger.info("AnalysisWorker thread started for game: %s", self.game.game_id)
        try:
            def callback(current, total, move_data=None):
                if not self._is_running:
                    raise InterruptedError("Analysis cancelled")
                self.progress.emit(current, total)
                if move_data is not None:
                    move_index = move_data.get("index", current - 1)
                    self.move_analyzed.emit(move_index, move_data)

            self.analyzer.analyze_game(self.game, callback=callback)
            logger.info("AnalysisWorker finished successfully for game: %s", self.game.game_id)
            self.finished.emit(self.game)
        except InterruptedError:
            logger.info("AnalysisWorker cancelled by user for game: %s", self.game.game_id)
        except Exception as e:
            logger.error("AnalysisWorker failed for game %s: %s", self.game.game_id, e, exc_info=True)
            self.error.emit(str(e))

    def stop(self):
        self._is_running = False
