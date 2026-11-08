"""Background PGN header indexing for the Load Game dialog."""

import threading

from PyQt6.QtCore import QThread, pyqtSignal

from src.backend.storage.pgn_parser import (
    PGNFileTooLargeError,
    PGNImportError,
    PGNParser,
    PGNParsingCancelledError,
    PGNTooManyGamesError,
)
from src.utils.logger import logger


def _format_size(size_bytes: int) -> str:
    if size_bytes >= 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    return f"{size_bytes / 1024:.0f} KB"


class PgnIndexWorker(QThread):
    """Index PGN headers off the UI thread; no games are fully parsed."""

    completed = pyqtSignal(object)  # PGNIndex
    failed = pyqtSignal(str)
    cancelled = pyqtSignal()

    def __init__(self, *, path: str | None = None, text: str | None = None):
        super().__init__(None)
        self._path = path
        self._text = text
        self._cancel = threading.Event()

    def cancel(self) -> None:
        self._cancel.set()

    def run(self) -> None:
        logger.debug(
            "PGN index worker started: %s",
            self._path or f"{len(self._text or '')} chars",
        )
        try:
            if self._path is not None:
                index = PGNParser.index_pgn_file(self._path, cancel=self._cancel)
            else:
                index = PGNParser.index_pgn_text(
                    self._text or "", cancel=self._cancel
                )
        except PGNParsingCancelledError:
            logger.debug("PGN index worker cancelled")
            self.cancelled.emit()
        except PGNFileTooLargeError as exc:
            logger.warning("PGN index rejected oversized file: %s", self._path)
            self.failed.emit(
                f"This PGN is {_format_size(exc.size_bytes)}. "
                f"The limit is {_format_size(exc.limit_bytes)}. "
                "Split it into smaller files and try again."
            )
        except PGNTooManyGamesError as exc:
            logger.warning(
                "PGN index rejected too many games: %s (limit %d)",
                self._path,
                exc.limit,
            )
            self.failed.emit(
                f"This PGN contains more than {exc.limit:,} games. "
                "Split it into smaller files and try again."
            )
        except PGNImportError as exc:
            logger.warning("PGN index failed: %s", exc)
            self.failed.emit(str(exc))
        except Exception:
            logger.exception("PGN indexing failed")
            self.failed.emit(
                "Could not read this PGN. It may be empty or corrupted."
            )
        else:
            logger.debug("PGN index worker completed: %d games", len(index.games))
            self.completed.emit(index)
