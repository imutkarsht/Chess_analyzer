"""Mini-board data helpers and the visible-row FEN worker."""

from __future__ import annotations

import io

import chess.pgn
from PyQt6.QtCore import QThread, pyqtSignal

from src.utils.logger import logger

_RUNNING_WORKERS: set[QThread] = set()


def register_worker(worker: QThread) -> None:
    _RUNNING_WORKERS.add(worker)


def remove_worker(worker: QThread) -> None:
    _RUNNING_WORKERS.discard(worker)
    worker.deleteLater()


def summarize_pgn(pgn: str) -> tuple[int | None, str | None]:
    """Return (full-move count, final FEN) with only one mainline replay."""
    if not pgn:
        return None, None
    try:
        game = chess.pgn.read_game(io.StringIO(pgn))
        if game is None or game.next() is None:
            return None, None
        board = game.end().board()
        return (len(board.move_stack) + 1) // 2, board.fen()
    except Exception:
        return None, None


def final_fen_from_pgn(pgn: str) -> str | None:
    return summarize_pgn(pgn)[1]


class MiniBoardFenWorker(QThread):
    """Compute final FENs for the rows currently visible in the table."""

    completed = pyqtSignal(int, object)  # (batch token, {candidate_id: fen})

    def __init__(self, token: int, items: list[tuple[int, str]]):
        super().__init__(None)
        self._token = token
        self._items = items

    def run(self) -> None:
        try:
            results = {
                candidate_id: final_fen_from_pgn(pgn)
                for candidate_id, pgn in self._items
            }
        except Exception:
            logger.exception("Mini-board FEN worker failed")
            self.completed.emit(self._token, {})
            return
        self.completed.emit(self._token, results)
