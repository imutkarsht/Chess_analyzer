# SPDX-License-Identifier: GPL-3.0-only
"""Background download worker for in-app updates."""

import os

from PyQt6.QtCore import QThread, pyqtSignal

from src.backend.api.download import DownloadCancelled, download_to_file
from src.utils.logger import logger


class DownloadWorker(QThread):
    """Downloads a URL to a local file in a background thread.

    Signals
    -------
    progress(int)   0–100 percent complete
    finished(str)   absolute local path of the downloaded file
    error(str)      human-readable error message
    """

    progress = pyqtSignal(int)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, url: str, dest_path: str, parent=None):
        super().__init__(parent)
        self.url = url
        self.dest_path = dest_path
        self._cancelled = False

    def cancel(self):
        """Signal the worker to abort cleanly."""
        self._cancelled = True

    def _on_progress(self, downloaded: int, total: int) -> None:
        if total > 0:
            self.progress.emit(min(100, int(downloaded * 100 / total)))

    def run(self):
        try:
            logger.info(f"Downloading update: {self.url} → {self.dest_path}")
            download_to_file(
                self.url,
                self.dest_path,
                progress=self._on_progress,
                should_cancel=lambda: self._cancelled,
                headers={"User-Agent": "ChessAnalyzerPro"},
            )

            if self._cancelled:
                raise DownloadCancelled("Download cancelled by user")

            self.progress.emit(100)
            logger.info("Download complete")
            self.finished.emit(self.dest_path)

        except Exception as exc:
            if not self._cancelled:
                logger.error(f"Download failed: {exc}")
            # Clean up partial file
            try:
                if os.path.exists(self.dest_path):
                    os.remove(self.dest_path)
            except OSError:
                pass
            if not self._cancelled:
                self.error.emit(str(exc))


__all__ = ["DownloadWorker"]
