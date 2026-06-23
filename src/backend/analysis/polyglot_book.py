"""Stateful opening book traversal using Polyglot binary book (.bin) files."""
import os
import chess
import chess.polyglot
from typing import Optional, List
from src.utils.logger import logger
from .local_book import BookResult


class PolyglotBookManager:
    """Manages traversal state and queries for a Polyglot opening book."""

    def __init__(self, book_path: Optional[str] = None):
        self.book_path = book_path
        self.reader: Optional[chess.polyglot.MemoryMappedReader] = None
        self._count = 0
        self._exited = False
        self._exit_move: Optional[int] = None

    def set_book_path(self, path: Optional[str]):
        """Close existing reader and set a new book path."""
        if self.book_path != path:
            self.close()
            self.book_path = path

    def open(self) -> bool:
        """Lazy open the reader. Returns True if reader is open and valid."""
        if self.reader is not None:
            return True
        if not self.book_path:
            return False
        try:
            if not os.path.exists(self.book_path) or not os.path.isfile(self.book_path):
                logger.warning(f"Polyglot book path is invalid: {self.book_path}")
                return False
            self.reader = chess.polyglot.open_reader(self.book_path)
            logger.info(f"Opened Polyglot opening book: {self.book_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to open Polyglot opening book at {self.book_path}: {e}")
            self.reader = None
            return False

    def close(self):
        """Close the Polyglot reader if open."""
        if self.reader is not None:
            try:
                self.reader.close()
                logger.info(f"Closed Polyglot opening book reader.")
            except Exception as e:
                logger.error(f"Error closing Polyglot reader: {e}")
            finally:
                self.reader = None

    def is_available(self) -> bool:
        """Check if reader is open or can be opened."""
        return self.open()

    def reset(self):
        """Reset traversal state for a new game."""
        self._count = 0
        self._exited = False
        self._exit_move = None

    def process_move(self, fen_before: str, uci: str, move_number: int) -> BookResult:
        """
        Check if the played move is a book move in the Polyglot book.
        Returns a BookResult.
        """
        if self._exited:
            return BookResult(
                is_book=False,
                book_move_count=self._count,
                book_exit_move=self._exit_move,
            )

        if not self.is_available():
            self._exited = True
            self._exit_move = move_number
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

        try:
            # Query candidate moves from the position AFTER the move.
            # In Polyglot, if a position is in the book, it has entries (i.e. moves to play from this position).
            # If there are entries, it means the played move led to a valid book position.
            entries = list(self.reader.find_all(board))
            if entries:
                self._count += 1
                candidate_moves = [entry.move.uci() for entry in entries]
                return BookResult(
                    is_book=True,
                    book_move_count=self._count,
                    candidate_moves=candidate_moves,
                )
            else:
                self._exited = True
                self._exit_move = move_number
                return BookResult(
                    is_book=False,
                    book_move_count=self._count,
                    book_exit_move=self._exit_move,
                )
        except Exception as e:
            logger.error(f"Error querying Polyglot book: {e}")
            self._exited = True
            self._exit_move = move_number
            return BookResult(
                is_book=False,
                book_move_count=self._count,
                book_exit_move=self._exit_move,
            )

    def __del__(self):
        self.close()
