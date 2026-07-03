"""
Error dialog for when the chess engine is not found,
offering Auto-detect, Download, and Browse actions.
"""
import os
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QProgressBar, QApplication
)
from PyQt6.QtCore import Qt, QTimer
from ...backend.analysis.engine import resolve_engine_path, invalidate_engine_cache
from ...backend.engine.downloader import (
    get_official_releases, get_expected_asset_name, get_download_url,
    download_and_extract
)
from ...utils.path_utils import get_engine_data_dir
from ...utils.logger import logger
from ..styles import Styles

BUTTON_STYLE = f"""
    QPushButton {{
        background-color: {Styles.COLOR_SURFACE_LIGHT};
        color: {Styles.COLOR_TEXT_PRIMARY};
        border: 1px solid {Styles.COLOR_BORDER};
        padding: 10px 18px;
        border-radius: 6px;
        font-size: 13px;
        font-weight: 500;
        text-align: left;
    }}
    QPushButton:hover {{
        background-color: {Styles.COLOR_SURFACE};
        border-color: {Styles.COLOR_ACCENT};
    }}
    QPushButton:disabled {{
        color: {Styles.COLOR_TEXT_MUTED};
    }}
"""

PRIMARY_BUTTON_STYLE = f"""
    QPushButton {{
        background-color: {Styles.COLOR_ACCENT};
        color: white;
        border: none;
        padding: 8px 16px;
        border-radius: 6px;
        font-size: 13px;
        font-weight: 600;
    }}
    QPushButton:hover {{
        background-color: {Styles.COLOR_ACCENT_HOVER};
    }}
"""


class EngineNotFoundDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Engine Not Found")
        self.setFixedSize(520, 340)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {Styles.COLOR_BACKGROUND};
                color: {Styles.COLOR_TEXT_PRIMARY};
            }}
        """)

        self._result_action = None
        self._engine_path = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 28, 28, 20)
        layout.setSpacing(16)

        icon_lbl = QLabel("\u26CF")
        icon_lbl.setStyleSheet("font-size: 36px; background: transparent;")
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon_lbl)

        title = QLabel("Stockfish Engine Not Found")
        title.setStyleSheet(
            f"font-size: 18px; font-weight: bold; color: {Styles.COLOR_TEXT_PRIMARY}; "
            f"background: transparent;"
        )
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        desc = QLabel(
            "No working Stockfish engine was found. Analysis requires a Stockfish "
            "chess engine binary on your system."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet(
            f"font-size: 13px; color: {Styles.COLOR_TEXT_SECONDARY}; "
            f"background: transparent;"
        )
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(desc)

        self._progress = QProgressBar()
        self._progress.setVisible(False)
        self._progress.setStyleSheet(Styles.get_progress_bar_style())
        layout.addWidget(self._progress)

        self._status = QLabel("")
        self._status.setStyleSheet(
            f"font-size: 12px; color: {Styles.COLOR_TEXT_SECONDARY}; "
            f"background: transparent;"
        )
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status.setVisible(False)
        layout.addWidget(self._status)

        btn_layout = QVBoxLayout()
        btn_layout.setSpacing(10)

        self._auto_btn = QPushButton("  Auto-detect Stockfish")
        self._auto_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._auto_btn.setStyleSheet(BUTTON_STYLE)
        self._auto_btn.clicked.connect(self._auto_detect)
        btn_layout.addWidget(self._auto_btn)

        self._download_btn = QPushButton("  Download Stockfish")
        self._download_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._download_btn.setStyleSheet(BUTTON_STYLE)
        self._download_btn.clicked.connect(self._start_download)
        btn_layout.addWidget(self._download_btn)

        self._browse_btn = QPushButton("  Browse for Stockfish...")
        self._browse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._browse_btn.setStyleSheet(BUTTON_STYLE)
        self._browse_btn.clicked.connect(self._browse)
        btn_layout.addWidget(self._browse_btn)

        layout.addLayout(btn_layout)

        footer = QHBoxLayout()
        footer.addStretch()
        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._cancel_btn.setStyleSheet(BUTTON_STYLE.replace("text-align: left;", ""))
        self._cancel_btn.clicked.connect(self.reject)
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
            self._status.setStyleSheet(
                f"font-size: 12px; color: {Styles.COLOR_BEST}; "
                f"background: transparent;"
            )
            self._engine_path = path
            QTimer.singleShot(800, self.accept)
        else:
            self._status.setText("No Stockfish found on your system.")
            self._status.setStyleSheet(
                f"font-size: 12px; color: {Styles.COLOR_BLUNDER}; "
                f"background: transparent;"
            )
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
        self._set_buttons_enabled(False)
        self._progress.setVisible(True)
        self._progress.setValue(0)
        self._status.setText("Checking for Stockfish releases...")
        self._status.setVisible(True)
        self._status.setStyleSheet(
            f"font-size: 12px; color: {Styles.COLOR_TEXT_SECONDARY}; "
            f"background: transparent;"
        )
        QApplication.processEvents()

        try:
            releases = get_official_releases()
            target = get_expected_asset_name()
            url = get_download_url(releases, target)
            if not url:
                raise RuntimeError(f"No download found for {target}")

            dest_dir = get_engine_data_dir()
            self._status.setText("Downloading Stockfish...")
            QApplication.processEvents()

            def progress(downloaded, total):
                pct = int(downloaded / total * 100) if total else 0
                self._progress.setValue(pct)

            binary_path = download_and_extract(url, dest_dir, progress_callback=progress)
            self._progress.setValue(100)

            invalidate_engine_cache()
            self._engine_path = binary_path
            self._status.setText(f"Downloaded: {os.path.basename(binary_path)}")
            self._status.setStyleSheet(
                f"font-size: 12px; color: {Styles.COLOR_BEST}; "
                f"background: transparent;"
            )
            QTimer.singleShot(600, self.accept)
        except Exception as e:
            logger.exception("EngineNotFoundDialog: download failed")
            self._status.setText(f"Download failed: {e}")
            self._status.setStyleSheet(
                f"font-size: 12px; color: {Styles.COLOR_BLUNDER}; "
                f"background: transparent;"
            )
            self._progress.setVisible(False)
            self._set_buttons_enabled(True)

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
