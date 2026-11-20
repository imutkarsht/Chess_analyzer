# SPDX-License-Identifier: GPL-3.0-only
"""Background annotated-PGN export for History."""

import json
import os
import tempfile
import time
from pathlib import Path
from threading import Event

from PyQt6.QtCore import QThread, pyqtSignal

from src.backend.storage.annotated_pgn import AnnotatedPGNExporter
from src.backend.storage.game_history import GameHistoryManager
from src.backend.storage.game_query import GameQuery
from src.utils.logger import logger


class AnnotatedPGNExportWorker(QThread):
    """Stream filtered game history to PGN without blocking the History view."""

    exported = pyqtSignal(int, int)  # exported_count, skipped_count
    progress = pyqtSignal(int, int)  # processed_count, total_count
    cancelled = pyqtSignal(int, int)  # exported_count, skipped_count
    error = pyqtSignal(str)
    _BATCH_SIZE = 25
    _YIELD_EVERY = 25

    def __init__(
        self,
        history_manager: GameHistoryManager,
        file_path: str,
        query: GameQuery | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.history_manager = history_manager
        self.file_path = file_path
        self.query = query or GameQuery()
        self._cancel_requested = Event()

    def request_cancel(self) -> None:
        self._cancel_requested.set()

    def run(self) -> None:
        temporary_path: Path | None = None
        try:
            total = self.history_manager.count_games(self.query)
            if not total:
                self.exported.emit(0, 0)
                return

            output_path = Path(self.file_path)
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                newline="\n",
                dir=output_path.parent,
                prefix=f".{output_path.name}.",
                suffix=".tmp",
                delete=False,
            ) as output:
                temporary_path = Path(output.name)
                exported_count = 0
                skipped_count = 0
                processed_count = 0
                has_output = False

                rows = self.history_manager.iter_games_for_export(
                    self.query, self._BATCH_SIZE
                )
                try:
                    for row in rows:
                        if self._cancel_requested.is_set():
                            break
                        try:
                            pgn = row.get("pgn") or ""
                            if self._is_unanalyzed(row):
                                pgn = AnnotatedPGNExporter.validate_unanalyzed_pgn(
                                    str(row.get("id") or ""),
                                    pgn,
                                    row.get("move_count"),
                                )
                            else:
                                game = self.history_manager.row_to_game_analysis(row)
                                pgn = AnnotatedPGNExporter.export_game(game)
                            self._write_game(output, pgn, has_output)
                            has_output = True
                            exported_count += 1
                        except Exception as error:
                            skipped_count += 1
                            logger.warning(
                                "Skipping game %s during annotated PGN export: %s",
                                row.get("id", "<unknown>"),
                                error,
                            )

                        processed_count += 1
                        if processed_count % self._YIELD_EVERY == 0:
                            self.progress.emit(processed_count, total)
                            time.sleep(0)
                finally:
                    close_iterator = getattr(rows, "close", None)
                    if close_iterator is not None:
                        close_iterator()

                self.progress.emit(processed_count, total)
                cancelled = self._cancel_requested.is_set()

            if cancelled:
                self.cancelled.emit(exported_count, skipped_count)
                return

            os.replace(temporary_path, output_path)
            temporary_path = None
            self.exported.emit(exported_count, skipped_count)
        except Exception as e:
            logger.error("Annotated PGN export failed: %s", e, exc_info=True)
            self.error.emit(str(e))
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

    @staticmethod
    def _is_unanalyzed(row: dict) -> bool:
        moves_json = row.get("moves_json")
        if not moves_json:
            return True
        try:
            return not json.loads(moves_json)
        except (json.JSONDecodeError, TypeError, ValueError):
            return False

    @staticmethod
    def _write_game(output, pgn: str, has_output: bool) -> None:
        if has_output:
            output.write("\n")
        output.write(pgn)
        if not pgn.endswith("\n"):
            output.write("\n")


__all__ = ["AnnotatedPGNExportWorker"]
