# SPDX-License-Identifier: GPL-3.0-only
"""Background Stockfish download for the engine-missing dialog."""

from __future__ import annotations

import threading

from PyQt6.QtCore import QThread, pyqtSignal

from src.backend.engine.downloader import (
    download_and_extract,
    get_download_candidates,
    try_package_manager_install,
)
from src.utils.logger import logger


class EngineDownloadWorker(QThread):
    """Download and verify Stockfish without blocking the Qt event loop."""

    progress = pyqtSignal(int)
    stage = pyqtSignal(str)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, dest_dir: str, parent=None):
        super().__init__(parent)
        self._dest_dir = dest_dir
        self._cancel = threading.Event()

    def cancel(self) -> None:
        self._cancel.set()

    def run(self) -> None:
        try:
            self.stage.emit("Checking for Stockfish releases...")
            candidates = get_download_candidates()
            if self._cancel.is_set():
                return

            if not candidates:
                logger.warning(
                    "EngineDownloadWorker: no matching Stockfish asset; "
                    "trying the system package manager"
                )
                self.stage.emit("Trying the system package manager...")
                package_path = try_package_manager_install()
                if self._cancel.is_set():
                    return
                if package_path:
                    self.finished.emit(package_path)
                    return
                raise RuntimeError(
                    "No compatible Stockfish download was found for this platform"
                )

            self.stage.emit("Downloading Stockfish...")

            def progress(downloaded: int, total: int) -> None:
                if self._cancel.is_set():
                    raise RuntimeError("Download cancelled by user")
                pct = int(downloaded / total * 100) if total else 0
                self.progress.emit(pct)

            binary_path = download_and_extract(
                candidates[0],
                self._dest_dir,
                progress_callback=progress,
                fallback_urls=candidates[1:],
                should_cancel=self._cancel.is_set,
            )
            if self._cancel.is_set():
                return
            self.finished.emit(binary_path)
        except Exception as exc:
            if self._cancel.is_set():
                logger.info("EngineDownloadWorker: download cancelled")
                return
            logger.exception("EngineDownloadWorker: download failed")
            self.error.emit(str(exc))


__all__ = ["EngineDownloadWorker"]
