# SPDX-License-Identifier: GPL-3.0-only
"""Background CSV import for History."""

from PyQt6.QtCore import QThread, pyqtSignal

from src.backend.storage.game_history import GameHistoryManager
from src.utils.logger import logger


class CsvImportWorker(QThread):
    """Background worker for parsing CSV files and bulk-inserting games off the UI thread."""

    finished = pyqtSignal(int, int)  # imported_count, skipped_count
    error = pyqtSignal(str)

    def __init__(self, history_manager: GameHistoryManager, file_path: str, parent=None):
        super().__init__(parent)
        self.history_manager = history_manager
        self.file_path = file_path

    def run(self):
        try:
            import csv

            max_limit = 2147483647
            try:
                csv.field_size_limit(max_limit)
            except OverflowError:
                csv.field_size_limit(50 * 1024 * 1024)

            existing_ids = self.history_manager.get_all_game_ids()
            rows_to_save = []
            skipped_count = 0

            with open(self.file_path, newline="", encoding="utf-8") as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    game_id = row.get("id")
                    if game_id and game_id in existing_ids:
                        skipped_count += 1
                        continue
                    rows_to_save.append(row)

            imported_count = self.history_manager.save_games_bulk(rows_to_save)
            self.finished.emit(imported_count, skipped_count)
        except Exception as e:
            logger.error(f"Background game import failed: {e}")
            self.error.emit(str(e))


__all__ = ["CsvImportWorker"]
