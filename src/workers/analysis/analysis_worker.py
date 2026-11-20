import threading

from PyQt6.QtCore import QThread, pyqtSignal

from src.backend.analysis.analyzer import Analyzer
from src.backend.storage.models import GameAnalysis
from src.utils.logger import logger


class AnalysisWorker(QThread):
    progress = pyqtSignal(int, int)  # current, total
    move_analyzed = pyqtSignal(int, object)  # move_index, data_dict
    finished = pyqtSignal(object)  # GameAnalysis
    cancelled = pyqtSignal(object)  # GameAnalysis (partial)
    error = pyqtSignal(str)

    def __init__(self, analyzer: Analyzer, game: GameAnalysis, resume: bool = True):
        super().__init__()
        self.analyzer = analyzer
        self.game = game
        self.resume = resume
        self._is_running = True
        self._cancel_token = threading.Event()

    def run(self):
        logger.info(
            "AnalysisWorker thread started for game: %s (resume=%s)",
            self.game.game_id,
            self.resume,
        )
        try:

            def callback(current, total, move_data=None):
                if not self._is_running or self._cancel_token.is_set():
                    raise InterruptedError("Analysis cancelled")
                self.progress.emit(current, total)
                if move_data is not None:
                    move_index = move_data.get("index", current - 1)
                    self.move_analyzed.emit(move_index, move_data)

            self.analyzer.analyze_game(
                self.game,
                callback=callback,
                cancel_token=self._cancel_token,
                resume=self.resume,
            )
            if self._cancel_token.is_set():
                logger.info(
                    "AnalysisWorker stopped by user with partial results for game: %s",
                    self.game.game_id,
                )
                self.cancelled.emit(self.game)
            else:
                logger.info("AnalysisWorker finished successfully for game: %s", self.game.game_id)
                self.finished.emit(self.game)
        except InterruptedError:
            logger.info("AnalysisWorker cancelled by user for game: %s", self.game.game_id)
            self.cancelled.emit(self.game)
        except Exception as e:
            if self._cancel_token.is_set():
                logger.info("AnalysisWorker stopped during execution: %s", e)
                self.cancelled.emit(self.game)
            else:
                logger.error(
                    "AnalysisWorker failed for game %s: %s",
                    self.game.game_id,
                    e,
                    exc_info=True,
                )
                self.error.emit(str(e))

    def cancel(self):
        """Request immediate cancellation of engine analysis and stop computation."""
        self._is_running = False
        self._cancel_token.set()
        try:
            self.analyzer.cancel()
        except Exception as e:
            logger.debug("Error while cancelling analyzer: %s", e)

    def stop(self):
        """Alias for cancel."""
        self.cancel()
