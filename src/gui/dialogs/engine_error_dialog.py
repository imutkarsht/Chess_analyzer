"""
Error dialog for when the chess engine is not found,
offering Auto-detect, Download, and Browse actions.
"""
import os

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QVBoxLayout,
)

from src.backend.analysis.engine import invalidate_engine_cache, resolve_engine_path
from src.gui.components import (
    Button,
    ButtonVariant,
    Label,
    ProgressBar,
    TextRole,
    TextTone,
)
from src.gui.dialogs.engine_download_worker import EngineDownloadWorker
from src.gui.styles import Styles
from src.utils.path_utils import get_engine_data_dir


class EngineNotFoundDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Engine Not Found")
        self.setFixedSize(520, 420)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {Styles.COLOR_BACKGROUND};
                color: {Styles.COLOR_TEXT_PRIMARY};
            }}
        """)

        self._result_action = None
        self._engine_path = None
        self._download_worker: EngineDownloadWorker | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 28, 28, 20)
        layout.setSpacing(16)

        icon_lbl = Label("\u26CF", role=TextRole.STAT, size=36)
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

        self._progress = ProgressBar()
        self._progress.setVisible(False)
        layout.addWidget(self._progress)

        self._status = Label("", role=TextRole.CAPTION, tone=TextTone.SECONDARY)
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status.setVisible(False)
        layout.addWidget(self._status)

        btn_layout = QVBoxLayout()
        btn_layout.setSpacing(10)
        btn_layout.setContentsMargins(0, 4, 0, 0)

        self._auto_btn = Button(
            "Auto-detect Stockfish",
            ButtonVariant.FILLED,
            full_width=True,
            align="left",
            on_click=self._auto_detect,
        )
        btn_layout.addWidget(self._auto_btn)

        self._download_btn = Button(
            "Download Stockfish",
            ButtonVariant.FILLED,
            full_width=True,
            align="left",
            on_click=self._start_download,
        )
        btn_layout.addWidget(self._download_btn)

        self._browse_btn = Button(
            "Browse for Stockfish...",
            ButtonVariant.FILLED,
            full_width=True,
            align="left",
            on_click=self._browse,
        )
        btn_layout.addWidget(self._browse_btn)

        layout.addLayout(btn_layout)

        layout.addStretch()

        footer = QHBoxLayout()
        footer.addStretch()
        self._cancel_btn = Button("Cancel", ButtonVariant.FILLED, on_click=self.reject)
        footer.addWidget(self._cancel_btn)
        layout.addLayout(footer)

    def _set_buttons_enabled(self, enabled: bool):
        for btn in (self._auto_btn, self._download_btn, self._browse_btn, self._cancel_btn):
            btn.setEnabled(enabled)

    def _auto_detect(self):
        self._set_buttons_enabled(False)
        self._status.setText("Scanning for Stockfish...")
        self._status.setVisible(True)
        QApplication.processEvents()

        path = resolve_engine_path(self.config_manager()) if hasattr(self, 'config_manager') else None
        if not path:
            path = self._search_common_paths()

        if path and os.path.isfile(path):
            self._status.setText(f"Found: {path}")
            self._status.set_tone(TextTone.BEST)
            self._engine_path = path
            QTimer.singleShot(800, self.accept)
        else:
            self._status.setText("No Stockfish found on your system.")
            self._status.set_tone(TextTone.BLUNDER)
            self._set_buttons_enabled(True)

    def _search_common_paths(self):
        import shutil
        candidates = [
            "stockfish",
            shutil.which("stockfish"),
            "/usr/local/bin/stockfish",
            "/opt/homebrew/bin/stockfish",
        ]
        for c in candidates:
            if c and (os.path.isfile(c) or shutil.which(c)):
                return shutil.which(c) or c
        return None

    def _start_download(self):
        if self._download_worker is not None and self._download_worker.isRunning():
            return

        for btn in (self._auto_btn, self._download_btn, self._browse_btn):
            btn.setEnabled(False)
        self._cancel_btn.setEnabled(True)
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
        self._set_buttons_enabled(True)
        QTimer.singleShot(600, self.accept)

    def _on_download_error(self, message: str) -> None:
        self._status.setText(f"Download failed: {message}")
        self._status.set_tone(TextTone.BLUNDER)
        self._progress.setVisible(False)
        self._release_worker()
        self._set_buttons_enabled(True)

    def _release_worker(self) -> None:
        worker = self._download_worker
        self._download_worker = None
        if worker is not None:
            worker.deleteLater()

    def _cancel_download(self) -> None:
        worker = self._download_worker
        if worker is not None and worker.isRunning():
            worker.cancel()
            worker.wait()
        self._release_worker()

    def reject(self) -> None:
        self._cancel_download()
        super().reject()

    def closeEvent(self, event) -> None:
        self._cancel_download()
        super().closeEvent(event)

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Stockfish Executable", "",
            "All Files (*);;Executables (*)"
        )
        if path:
            self._engine_path = path
            self.accept()

    def engine_path(self) -> str:
        return self._engine_path

    def result_action(self):
        return self._result_action
