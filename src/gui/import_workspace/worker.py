"""Bulk import worker for adding selected games to history unanalyzed."""

from PyQt6.QtCore import QThread, pyqtSignal

from src.backend.storage.game_history import GameHistoryManager
from src.backend.storage.pgn_parser import PGNParser
from src.utils.logger import logger

from .batch import GameCandidate


class GameImportWorker(QThread):
    """Parse selected games as lightweight stubs and insert them in batches."""

    progress = pyqtSignal(int, int)  # (done, total)
    completed = pyqtSignal(int, int)  # (inserted, skipped)
    failed = pyqtSignal(str)

    def __init__(
        self,
        candidates: list[GameCandidate],
        history_manager: GameHistoryManager,
    ):
        super().__init__(None)
        self._candidates = candidates
        self._history_manager = history_manager

    def run(self) -> None:
        total = len(self._candidates)
        inserted = skipped = 0
        batch = []
        try:
            for position, candidate in enumerate(self._candidates, start=1):
                if candidate.in_history:
                    skipped += 1
                else:
                    try:
                        stub = PGNParser.parse_game_stub(candidate.pgn_text())
                    except Exception:
                        logger.exception(
                            "Failed to parse import candidate %s",
                            candidate.candidate_id,
                        )
                        stub = None
                    if stub is None:
                        skipped += 1
                    else:
                        batch.append(stub)

                if len(batch) >= 200:
                    saved, duplicates = (
                        self._history_manager.save_unanalyzed_games_bulk(batch)
                    )
                    inserted += saved
                    skipped += duplicates
                    batch.clear()

                if position % 10 == 0 or position == total:
                    self.progress.emit(position, total)

            if batch:
                saved, duplicates = (
                    self._history_manager.save_unanalyzed_games_bulk(batch)
                )
                inserted += saved
                skipped += duplicates
        except Exception as exc:
            logger.exception("Bulk game import failed")
            self.failed.emit(str(exc))
            return
        self.completed.emit(inserted, skipped)
