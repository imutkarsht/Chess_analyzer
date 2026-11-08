"""Mini-board data helpers and the visible-row FEN worker."""

from __future__ import annotations

import io
from dataclasses import dataclass

import chess.pgn
from PyQt6.QtCore import QThread, pyqtSignal

from src.utils.logger import logger

_RUNNING_WORKERS: set[QThread] = set()


def register_worker(worker: QThread) -> None:
    _RUNNING_WORKERS.add(worker)


def remove_worker(worker: QThread) -> None:
    _RUNNING_WORKERS.discard(worker)
    worker.deleteLater()


@dataclass(frozen=True)
class PgnSummary:
    move_count: int | None = None
    last_fen: str | None = None
    termination: str | None = None
    eco: str | None = None
    event: str = ""
    opening: str | None = None
    variant: str | None = None
    white_rating_diff: str | None = None
    black_rating_diff: str | None = None
    time_control: str = ""


def summarize_pgn(pgn: str) -> PgnSummary:
    """Return metadata from a single mainline parse."""
    if not pgn:
        return PgnSummary()
    try:
        game = chess.pgn.read_game(io.StringIO(pgn))
        if game is None or game.next() is None:
            return PgnSummary()
        board = game.end().board()
        headers = game.headers
        return PgnSummary(
            move_count=(len(board.move_stack) + 1) // 2,
            last_fen=board.fen(),
            termination=headers.get("Termination"),
            eco=headers.get("ECO"),
            event=headers.get("Event", ""),
            opening=headers.get("Opening"),
            variant=headers.get("Variant"),
            white_rating_diff=headers.get("WhiteRatingDiff"),
            black_rating_diff=headers.get("BlackRatingDiff"),
            time_control=headers.get("TimeControl", ""),
        )
    except Exception:
        return PgnSummary()


def final_fen_from_pgn(pgn: str) -> str | None:
    return summarize_pgn(pgn).last_fen


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
