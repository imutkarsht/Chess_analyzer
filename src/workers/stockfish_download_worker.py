# SPDX-License-Identifier: GPL-3.0-only
"""Background Stockfish download for the setup wizard."""

import os
import subprocess
import sys

from PyQt6.QtCore import QThread, pyqtSignal

from src.backend.engine.downloader import (
    download_and_extract,
    get_download_candidates,
    try_package_manager_install,
)
from src.utils.logger import logger


class StockfishDownloadWorker(QThread):
    """Download or install Stockfish without blocking the setup wizard."""

    progress = pyqtSignal(int)
    stage = pyqtSignal(str)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, dest_dir, parent=None):
        super().__init__(parent)
        self.dest_dir = dest_dir
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        import shutil

        # 1. On macOS, try installing Stockfish via Homebrew first
        if sys.platform == "darwin":
            brew_path = shutil.which("brew")
            if not brew_path:
                for path in ["/opt/homebrew/bin/brew", "/usr/local/bin/brew"]:
                    if os.path.isfile(path) and os.access(path, os.X_OK):
                        brew_path = path
                        break

            if brew_path:
                self.stage.emit("Checking Homebrew installation...")
                self.progress.emit(15)
                logger.info(
                    "StockfishDownloadWorker: attempting Homebrew installation via %s",
                    brew_path,
                )
                try:
                    result = subprocess.run(
                        [brew_path, "install", "stockfish"],
                        capture_output=True,
                        text=True,
                        timeout=120,
                    )
                    if self._is_cancelled:
                        return

                    if result.returncode == 0:
                        for candidate in (
                            "/opt/homebrew/bin/stockfish",
                            "/usr/local/bin/stockfish",
                        ):
                            if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                                self.progress.emit(100)
                                self.finished.emit(candidate)
                                return
                        which_sf = shutil.which("stockfish")
                        if (
                            which_sf
                            and os.path.isfile(which_sf)
                            and os.access(which_sf, os.X_OK)
                        ):
                            self.progress.emit(100)
                            self.finished.emit(which_sf)
                            return
                    logger.warning(
                        "StockfishDownloadWorker: Homebrew installation failed: %s",
                        result.stderr,
                    )
                except Exception as exc:
                    logger.warning(
                        "StockfishDownloadWorker: Homebrew installation crashed: %s",
                        exc,
                    )

        if self._is_cancelled:
            return

        # 2. GitHub Releases download fallback
        download_error = None
        try:
            self.stage.emit("Resolving latest release candidate...")
            candidates = get_download_candidates()
            if not candidates:
                raise RuntimeError(
                    "No compatible Stockfish download was found for this platform"
                )

            if self._is_cancelled:
                return

            self.stage.emit("Downloading Stockfish binary...")

            def progress_callback(downloaded, total):
                if self._is_cancelled:
                    raise RuntimeError("Download cancelled by user")
                pct = int(downloaded / total * 100) if total else 0
                self.progress.emit(pct)

            binary_path = download_and_extract(
                candidates[0],
                self.dest_dir,
                progress_callback=progress_callback,
                fallback_urls=candidates[1:],
                should_cancel=lambda: self._is_cancelled,
            )
            if self._is_cancelled:
                return

            self.stage.emit("Verifying engine binary...")
            logger.info(
                "StockfishDownloadWorker: successfully downloaded Stockfish to %s",
                binary_path,
            )
            self.finished.emit(binary_path)
            return
        except Exception as exc:
            if self._is_cancelled:
                logger.info("StockfishDownloadWorker: cancelled")
                return
            download_error = exc
            logger.warning("StockfishDownloadWorker: GitHub download failed: %s", exc)

        # 3. Distro package manager fallback (Linux and friends)
        if not self._is_cancelled:
            self.stage.emit("Attempting system package manager fallback...")
            pm_path = try_package_manager_install()
            if pm_path:
                logger.info(
                    "StockfishDownloadWorker: package manager installed Stockfish to %s",
                    pm_path,
                )
                self.finished.emit(pm_path)
                return

        logger.error(
            "StockfishDownloadWorker: all download strategies failed: %s",
            download_error,
        )
        self.error.emit(str(download_error))


__all__ = ["StockfishDownloadWorker"]
