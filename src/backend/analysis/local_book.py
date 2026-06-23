"""Stateful local opening book traversal using FEN-based SQLite lookups."""
import chess
from dataclasses import dataclass, field
from typing import List, Optional
from .opening_db import OpeningDB, _normalize_fen


@dataclass
class BookResult:
    is_book: bool
    current_eco: Optional[str] = None
    current_opening: Optional[str] = None
    book_move_count: int = 0
    book_exit_move: Optional[int] = None
    candidate_moves: List[str] = field(default_factory=list)


class LocalBookManager:
    """Per-game stateful book detector. Call reset() for each new game."""

    def __init__(self, db: OpeningDB):
        self.db = db
        self._count = 0
        self._exited = False
        self._exit_move: Optional[int] = None

    def reset(self):
        """Reset traversal state for a new game."""
        self._count = 0
        self._exited = False
        self._exit_move = None

    def process_move(self, fen_before: str, uci: str, move_number: int) -> BookResult:
        """
        Check if the played move is a book move.
        Returns a BookResult with opening metadata if found.
        """
        if self._exited:
            return BookResult(
                is_book=False,
                book_move_count=self._count,
                book_exit_move=self._exit_move,
            )

        board = chess.Board(fen_before)
        try:
            board.push_uci(uci)
        except Exception:
            self._exited = True
            self._exit_move = move_number
            return BookResult(
                is_book=False,
                book_move_count=self._count,
                book_exit_move=self._exit_move,
            )
        fen_after = _normalize_fen(board.fen())

        node_id = self.db.get_node_by_fen(fen_after)
        if node_id is not None:
            self._count += 1
            openings = self.db.get_openings_at_node(node_id)
            candidates = self.db.get_children(node_id)

            best_eco: Optional[str] = None
            best_name: Optional[str] = None
            if openings:
                best_name = max(openings, key=lambda x: len(x[1]))[1]
                best_eco = max(openings, key=lambda x: len(x[1]))[0]

            return BookResult(
                is_book=True,
                current_eco=best_eco,
                current_opening=best_name,
                book_move_count=self._count,
                candidate_moves=candidates,
            )
        else:
            self._exited = True
            self._exit_move = move_number
            return BookResult(
                is_book=False,
                book_move_count=self._count,
                book_exit_move=self._exit_move,
            )
