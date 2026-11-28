# SPDX-License-Identifier: GPL-3.0-only
"""Stockfish Engine Not Found panel, dialog wrapper, and overlay launcher."""

from __future__ import annotations

import os
import shutil

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
)

from src.backend.analysis.engine import invalidate_engine_cache, resolve_engine_path
from src.gui.components import (
    Button,
    ButtonVariant,
    IconLabel,
    Label,
    OverlayManager,
    OverlayResult,
    ProgressBar,
    TextRole,
    TextTone,
)
from src.utils.logger import logger
from src.utils.path_utils import get_engine_data_dir
from src.workers import EngineDownloadWorker


class EngineNotFoundPanel(QWidget):
    """Actions and download status for locating or installing Stockfish."""

    accepted = pyqtSignal()
    rejected = pyqtSignal()
    busy_changed = pyqtSignal(bool)

    def __init__(self, config_manager=None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._config_manager = config_manager
        self._engine_path: str | None = None
        self._download_worker: EngineDownloadWorker | None = None
        self._scan_timer = QTimer(self)
        self._scan_timer.setSingleShot(True)
        self._scan_timer.timeout.connect(self._run_auto_detect)
        self._accept_timer = QTimer(self)
        self._accept_timer.setSingleShot(True)
        self._accept_timer.timeout.connect(self.accepted.emit)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        self._progress = ProgressBar()
        self._progress.setVisible(False)
        layout.addWidget(self._progress)

        self._status = Label("", role=TextRole.CAPTION, tone=TextTone.SECONDARY, wrap=True)
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status.setVisible(False)
        layout.addWidget(self._status)

        btn_layout = QVBoxLayout()
        btn_layout.setSpacing(10)
        btn_layout.setContentsMargins(0, 0, 0, 0)

        self._auto_btn = Button(
            "Auto-detect Stockfish",
            ButtonVariant.FILLED,
            icon="search",
            full_width=True,
            align="left",
            on_click=self._auto_detect,
        )
        btn_layout.addWidget(self._auto_btn)

        self._download_btn = Button(
            "Download Stockfish",
            ButtonVariant.FILLED,
            icon="download",
            full_width=True,
            align="left",
            on_click=self._start_download,
        )
        btn_layout.addWidget(self._download_btn)

        self._browse_btn = Button(
            "Browse for Stockfish...",
            ButtonVariant.FILLED,
            icon="folder-open",
            full_width=True,
            align="left",
            on_click=self._browse,
        )
        btn_layout.addWidget(self._browse_btn)

        layout.addLayout(btn_layout)

    def _set_actions_enabled(self, enabled: bool) -> None:
        for btn in (self._auto_btn, self._download_btn, self._browse_btn):
            btn.setEnabled(enabled)
        self.busy_changed.emit(not enabled)

    def _auto_detect(self) -> None:
        self._set_actions_enabled(False)
        self._status.setText("Scanning for Stockfish...")
        self._status.set_tone(TextTone.SECONDARY)
        self._status.setVisible(True)
        self._scan_timer.start(0)

    def _run_auto_detect(self) -> None:
        cfg = self._config_manager() if callable(self._config_manager) else self._config_manager
        path = resolve_engine_path(cfg) if cfg is not None else None
        if not path:
            path = self._search_common_paths()

        if path and os.path.isfile(path):
            self._status.setText(f"Found: {path}")
            self._status.set_tone(TextTone.BEST)
            self._engine_path = path
            self._accept_timer.start(800)
        else:
            self._status.setText("No Stockfish found on your system.")
            self._status.set_tone(TextTone.BLUNDER)
            self._set_actions_enabled(True)

    @staticmethod
    def _search_common_paths() -> str | None:
        candidates = [
            "stockfish",
            shutil.which("stockfish"),
            "/usr/local/bin/stockfish",
            "/opt/homebrew/bin/stockfish",
        ]
        for candidate in candidates:
            if candidate and (os.path.isfile(candidate) or shutil.which(candidate)):
                return shutil.which(candidate) or candidate
        return None

    def _start_download(self) -> None:
        if self._download_worker is not None and self._download_worker.isRunning():
            return

        self._set_actions_enabled(False)
        self._progress.setVisible(True)
        self._progress.setValue(0)
        self._status.setVisible(True)
        self._status.set_tone(TextTone.SECONDARY)
        self._status.setText("Checking for Stockfish releases...")

        worker = EngineDownloadWorker(get_engine_data_dir(), self)
        worker.progress.connect(self._progress.setValue)
        worker.stage.connect(self._status.setText)
        worker.finished.connect(self._on_download_finished)
        worker.error.connect(self._on_download_error)
        self._download_worker = worker
        worker.start()

    def _on_download_finished(self, binary_path: str) -> None:
        self._progress.setValue(100)
        invalidate_engine_cache()
        self._engine_path = binary_path
        self._status.setText(f"Downloaded: {os.path.basename(binary_path)}")
        self._status.set_tone(TextTone.BEST)
        self._release_worker()
        self._set_actions_enabled(True)
        self._accept_timer.start(600)

    def _on_download_error(self, message: str) -> None:
        self._status.setText(f"Download failed: {message}")
        self._status.set_tone(TextTone.BLUNDER)
        self._progress.setVisible(False)
        self._release_worker()
        self._set_actions_enabled(True)

    def _release_worker(self) -> None:
        worker = self._download_worker
        self._download_worker = None
        if worker is not None:
            worker.deleteLater()

    def cancel_download(self) -> None:
        self._scan_timer.stop()
        self._accept_timer.stop()
        worker = self._download_worker
        if worker is not None and worker.isRunning():
            worker.cancel()
            worker.wait()
        self._release_worker()

    def _browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Stockfish Executable",
            "",
            "All Files (*);;Executables (*)",
        )
        if path:
            self._engine_path = path
            self.accepted.emit()

    def engine_path(self) -> str | None:
        return self._engine_path


class EngineNotFoundDialog(QDialog):
    """Native QDialog wrapper around ``EngineNotFoundPanel``."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Engine Not Found")
        self.setFixedSize(520, 420)
        self._result_action = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 28, 28, 20)
        layout.setSpacing(14)

        icon_lbl = IconLabel("exclamation-triangle", size=34, tone=TextTone.MISTAKE)
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon_lbl)

        title = Label("Stockfish Engine Not Found", role=TextRole.SECTION_TITLE)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        desc = Label(
            "No working Stockfish engine was found. Analysis requires a Stockfish "
            "chess engine binary on your system.",
            role=TextRole.BODY,
            tone=TextTone.SECONDARY,
            wrap=True,
        )
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(desc)

        self.panel = EngineNotFoundPanel(
            config_manager=lambda: getattr(self, "config_manager", lambda: None)(),
            parent=self,
        )
        self.panel.accepted.connect(self.accept)
        self.panel.rejected.connect(self.reject)
        layout.addWidget(self.panel)
        layout.addStretch()

        footer = QHBoxLayout()
        footer.addStretch()
        self._cancel_btn = Button("Cancel", ButtonVariant.HOLLOW, on_click=self.reject)
        footer.addWidget(self._cancel_btn)
        layout.addLayout(footer)

    def reject(self) -> None:
        self.panel.cancel_download()
        super().reject()

    def closeEvent(self, event) -> None:
        self.panel.cancel_download()
        super().closeEvent(event)

    def engine_path(self) -> str | None:
        return self.panel.engine_path()

    def result_action(self):
        return self._result_action


def open_engine_not_found(parent, *, config_manager=None) -> str | None:
    """Prompt the user to locate or download Stockfish via an in-window overlay.

    Returns the chosen engine path if accepted, or ``None`` if cancelled.
    """
    if isinstance(parent, QWidget):
        try:
            manager = OverlayManager.for_window(parent)
            card = manager.create_card(
                title="Stockfish Engine Not Found",
                description=(
                    "No working Stockfish engine was found. Analysis requires a "
                    "Stockfish chess engine binary on your system."
                ),
                max_width=500,
                minimum_width=380,
                dismiss_on_escape=True,
                dismiss_on_backdrop=True,
            )
            panel = EngineNotFoundPanel(config_manager=config_manager, parent=card)
            card.set_content(panel)

            cancel_btn = Button("Cancel", ButtonVariant.HOLLOW, on_click=card.reject)
            card.add_action(cancel_btn)
            card.set_initial_focus(panel._auto_btn)

            panel.accepted.connect(card.accept)
            panel.rejected.connect(card.reject)

            card.add_cleanup(panel.cancel_download)
            result = manager.open_blocking(card)
            if result is OverlayResult.ACCEPTED:
                return panel.engine_path()
            return None
        except Exception:
            logger.warning("open_engine_not_found overlay failed, falling back", exc_info=True)

    dialog = EngineNotFoundDialog(parent)
    if config_manager is not None:
        dialog.config_manager = lambda: config_manager
    if dialog.exec() == QDialog.DialogCode.Accepted:
        return dialog.engine_path()
    return None
