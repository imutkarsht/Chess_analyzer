"""Mini-board data helpers and the visible-row FEN worker."""

from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtCore import QThread, pyqtSignal

from src.backend.storage.pgn_metadata import extract_pgn_metadata
from src.utils.logger import logger


@dataclass(frozen=True)
class MiniBoardPosition:
    fen: str | None = None
    last_move_uci: str | None = None


def final_position_from_pgn(pgn: str) -> MiniBoardPosition:
    metadata = extract_pgn_metadata(pgn, require_moves=True)
    if metadata is None:
        return MiniBoardPosition()
    return MiniBoardPosition(metadata.last_fen, metadata.last_move_uci)


class MiniBoardFenWorker(QThread):
    """Compute final positions for the rows currently visible in the table."""

    completed = pyqtSignal(int, object)  # (token, {candidate_id: MiniBoardPosition})

    def __init__(self, token: int, items: list[tuple[int, str]]):
        super().__init__(None)
        self._token = token
        self._items = items

    def run(self) -> None:
        try:
            results = {
                candidate_id: final_position_from_pgn(pgn)
                for candidate_id, pgn in self._items
            }
        except Exception:
            logger.exception("Mini-board FEN worker failed")
            self.completed.emit(self._token, {})
            return
        self.completed.emit(self._token, results)
