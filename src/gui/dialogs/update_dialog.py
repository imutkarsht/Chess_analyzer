"""
Update Notification Dialog — shows when a new version is available.

States
------
IDLE        → shows "Download Update" + "Remind Later"
DOWNLOADING → shows progress bar + "Cancel" (buttons replaced by QStackedWidget)
DONE        → platform-specific finish panel:
               Windows : "Installing…  App will restart automatically."
               macOS   : "Saved to ~/Downloads  →  Open in Finder" button
               Linux   : "Applying update…  App will relaunch automatically."
ERROR       → shows error text + "Open in Browser" fallback
"""

import sys
import os
import re

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTextEdit, QWidget, QProgressBar,
    QStackedWidget, QSizePolicy,
)
from PyQt6.QtCore import Qt, QUrl, QTimer
from PyQt6.QtGui import QDesktopServices

from ..styles import Styles
from ...utils.logger import logger  # src/gui/dialogs/ → src/utils/
from ...backend.updater import (    # src/gui/dialogs/ → src/backend/
    DownloadWorker,
    get_download_destination,
    install_and_quit,
    PLATFORM,
)

try:
    import qtawesome as qta
    HAS_QTAWESOME = True
except ImportError:
    HAS_QTAWESOME = False


# ---------------------------------------------------------------------------
# Footer page indices inside QStackedWidget
# ---------------------------------------------------------------------------
_PAGE_BUTTONS    = 0   # default: Remind Later + Download
_PAGE_PROGRESS   = 1   # downloading: progress bar + Cancel
_PAGE_DONE       = 2   # done / installing
_PAGE_ERROR      = 3   # download failed


class UpdateNotificationDialog(QDialog):
    """Dialog to notify user of an available update and manage the download."""

    def __init__(self, update_info, parent=None):
        super().__init__(parent)
        self.update_info  = update_info
        self._worker: DownloadWorker | None = None

        self.setWindowTitle("Update Available")
        self.setFixedSize(480, 420)
        self.setStyleSheet(f"QDialog {{ background-color: {Styles.COLOR_BACKGROUND}; }}")

        self._setup_ui()

    # ------------------------------------------------------------------ UI --

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_header())
        root.addWidget(self._build_changelog(), stretch=1)
        root.addWidget(self._build_footer())

    # ── Header ──────────────────────────────────────────────────────────────

    def _build_header(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet(f"""
            QWidget {{
                background-color: {Styles.COLOR_SURFACE};
                border-bottom: 1px solid {Styles.COLOR_BORDER};
            }}
        """)
        layout = QVBoxLayout(w)
        layout.setContentsMargins(24, 18, 24, 14)
        layout.setSpacing(0)

        # ── Single header row ──────────────────────────────────────────────
        # Left:  [↑ icon]  Update Available
        # Right: v2.0.1 → v9.9.9   [.exe pill]
        title_row = QHBoxLayout()
        title_row.setSpacing(10)

        if HAS_QTAWESOME:
            ic = QLabel()
            ic.setPixmap(qta.icon('fa5s.arrow-circle-up', color=Styles.COLOR_ACCENT).pixmap(24, 24))
            title_row.addWidget(ic)

        title = QLabel("Update Available")
        title.setStyleSheet(
            f"font-size: 17px; font-weight: bold; color: {Styles.COLOR_TEXT_PRIMARY};"
        )
        title_row.addWidget(title)
        title_row.addStretch()

        # Version string: grey current → accent latest
        ver_widget = QWidget()
        ver_widget.setStyleSheet("background: transparent;")
        ver_lay = QHBoxLayout(ver_widget)
        ver_lay.setContentsMargins(0, 0, 0, 0)
        ver_lay.setSpacing(4)

        lbl_cur = QLabel(f"v{self.update_info.current}")
        lbl_cur.setStyleSheet(f"color: {Styles.COLOR_TEXT_MUTED}; font-size: 13px; font-weight: 500;")
        ver_lay.addWidget(lbl_cur)

        arr = QLabel("→")
        arr.setStyleSheet(f"color: {Styles.COLOR_TEXT_MUTED}; font-size: 13px;")
        ver_lay.addWidget(arr)

        lbl_new = QLabel(f"v{self.update_info.latest}")
        lbl_new.setStyleSheet(
            f"color: {Styles.COLOR_ACCENT}; font-size: 13px; font-weight: 700;"
        )
        ver_lay.addWidget(lbl_new)
        title_row.addWidget(ver_widget)

        # Short format badge: ".exe" / ".dmg" / ".AppImage"
        _short = {
            "win32":  ".exe",
            "darwin": ".dmg",
            "linux":  ".AppImage",
        }.get(PLATFORM, ".pkg")

        _ac = Styles.COLOR_ACCENT.lstrip("#")
        _r, _g, _b = int(_ac[0:2], 16), int(_ac[2:4], 16), int(_ac[4:6], 16)

        fmt_badge = QLabel(_short)
        fmt_badge.setStyleSheet(f"""
            QLabel {{
                color: {Styles.COLOR_ACCENT};
                background-color: rgba({_r}, {_g}, {_b}, 35);
                border: 1px solid {Styles.COLOR_ACCENT};
                border-radius: 8px;
                padding: 2px 8px;
                font-size: 11px;
                font-weight: 700;
            }}
        """)
        title_row.addWidget(fmt_badge)

        layout.addLayout(title_row)

        return w


    # ── Changelog ───────────────────────────────────────────────────────────

    def _build_changelog(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(24, 14, 24, 14)
        layout.setSpacing(8)

        if self.update_info.changelog:
            lbl = QLabel("What's New")
            lbl.setStyleSheet(f"color: {Styles.COLOR_TEXT_PRIMARY}; font-size: 13px; font-weight: 600;")
            layout.addWidget(lbl)

            cleaned = self._clean_markdown(self.update_info.changelog)
            changelog_text = QTextEdit()
            changelog_text.setPlainText(cleaned[:600] + ("…" if len(cleaned) > 600 else ""))
            changelog_text.setReadOnly(True)
            changelog_text.setStyleSheet(f"""
                QTextEdit {{
                    background-color: {Styles.COLOR_SURFACE_LIGHT};
                    color: {Styles.COLOR_TEXT_SECONDARY};
                    border: 1px solid {Styles.COLOR_BORDER};
                    border-radius: 6px;
                    padding: 10px;
                    font-size: 12px;
                }}
                QScrollBar:vertical {{
                    background: {Styles.COLOR_SURFACE};
                    width: 6px;
                    border-radius: 3px;
                    margin: 0;
                }}
                QScrollBar::handle:vertical {{
                    background: {Styles.COLOR_BORDER};
                    border-radius: 3px;
                    min-height: 24px;
                }}
                QScrollBar::handle:vertical:hover {{
                    background: {Styles.COLOR_ACCENT};
                }}
                QScrollBar::add-line:vertical,
                QScrollBar::sub-line:vertical {{
                    height: 0;
                }}
            """)
            layout.addWidget(changelog_text)

        return w

    # ── Footer (stacked) ────────────────────────────────────────────────────

    def _build_footer(self) -> QWidget:
        outer = QWidget()
        outer.setStyleSheet(f"""
            QWidget {{
                background-color: {Styles.COLOR_SURFACE};
                border-top: 1px solid {Styles.COLOR_BORDER};
            }}
        """)
        outer_layout = QVBoxLayout(outer)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        self._footer_stack = QStackedWidget()
        self._footer_stack.addWidget(self._page_buttons())   # 0
        self._footer_stack.addWidget(self._page_progress())  # 1
        self._footer_stack.addWidget(self._page_done())      # 2
        self._footer_stack.addWidget(self._page_error())     # 3
        self._footer_stack.setCurrentIndex(_PAGE_BUTTONS)

        outer_layout.addWidget(self._footer_stack)
        return outer

    # -- Page 0: buttons
    def _page_buttons(self) -> QWidget:
        w = QWidget()
        layout = QHBoxLayout(w)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(12)
        layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        btn_later = QPushButton("  Remind Later")
        if HAS_QTAWESOME:
            btn_later.setIcon(qta.icon('fa5s.clock', color=Styles.COLOR_TEXT_SECONDARY))
        btn_later.setStyleSheet(self._btn_style_secondary())
        btn_later.setFixedHeight(40)
        btn_later.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_later.clicked.connect(self.reject)
        layout.addWidget(btn_later, 0, Qt.AlignmentFlag.AlignVCenter)

        layout.addStretch()

        # Download button + hint (stacked vertically)
        dl_col = QVBoxLayout()
        dl_col.setSpacing(4)

        self._btn_download = QPushButton("  Download Update")
        if HAS_QTAWESOME:
            self._btn_download.setIcon(qta.icon('fa5s.download', color="#ffffff"))
        self._btn_download.setStyleSheet(self._btn_style_primary())
        self._btn_download.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_download.clicked.connect(self._start_download)
        dl_col.addWidget(self._btn_download)

        if self.update_info.install_hint:
            hint = QLabel(self.update_info.install_hint)
            hint.setAlignment(Qt.AlignmentFlag.AlignRight)
            hint.setStyleSheet(f"color: {Styles.COLOR_TEXT_MUTED}; font-size: 10px; font-style: italic;")
            dl_col.addWidget(hint)

        layout.addLayout(dl_col)
        return w

    # -- Page 1: progress
    def _page_progress(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(24, 14, 24, 14)
        layout.setSpacing(8)

        # Status label + percentage
        top_row = QHBoxLayout()
        self._lbl_status = QLabel("Downloading…")
        self._lbl_status.setStyleSheet(f"color: {Styles.COLOR_TEXT_PRIMARY}; font-size: 13px; font-weight: 600;")
        top_row.addWidget(self._lbl_status)
        top_row.addStretch()
        self._lbl_pct = QLabel("0 %")
        self._lbl_pct.setStyleSheet(f"color: {Styles.COLOR_TEXT_MUTED}; font-size: 12px;")
        top_row.addWidget(self._lbl_pct)
        layout.addLayout(top_row)

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setFixedHeight(6)
        self._progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: {Styles.COLOR_SURFACE_LIGHT};
                border: none;
                border-radius: 3px;
            }}
            QProgressBar::chunk {{
                background-color: {Styles.COLOR_ACCENT};
                border-radius: 3px;
            }}
        """)
        layout.addWidget(self._progress_bar)

        btn_cancel = QPushButton("Cancel")
        btn_cancel.setStyleSheet(self._btn_style_secondary())
        btn_cancel.setFixedWidth(90)
        btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_cancel.clicked.connect(self._cancel_download)
        cancel_row = QHBoxLayout()
        cancel_row.addStretch()
        cancel_row.addWidget(btn_cancel)
        layout.addLayout(cancel_row)

        return w

    # -- Page 2: done
    def _page_done(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(6)

        row = QHBoxLayout()
        row.setSpacing(10)

        if HAS_QTAWESOME:
            ic = QLabel()
            ic.setPixmap(qta.icon('fa5s.check-circle', color="#4caf50").pixmap(22, 22))
            row.addWidget(ic)

        self._lbl_done_title = QLabel()
        self._lbl_done_title.setStyleSheet(
            f"color: {Styles.COLOR_TEXT_PRIMARY}; font-size: 13px; font-weight: 600;"
        )
        row.addWidget(self._lbl_done_title)
        row.addStretch()

        # macOS only: "Open in Finder" button (hidden on other platforms)
        self._btn_open_finder = QPushButton("  Open in Finder")
        if HAS_QTAWESOME:
            self._btn_open_finder.setIcon(qta.icon('fa5s.folder-open', color="#ffffff"))
        self._btn_open_finder.setStyleSheet(self._btn_style_primary())
        self._btn_open_finder.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_open_finder.clicked.connect(self._open_in_finder)
        self._btn_open_finder.hide()
        row.addWidget(self._btn_open_finder)

        layout.addLayout(row)

        self._lbl_done_sub = QLabel()
        self._lbl_done_sub.setStyleSheet(
            f"color: {Styles.COLOR_TEXT_MUTED}; font-size: 11px;"
        )
        self._lbl_done_sub.setWordWrap(True)
        layout.addWidget(self._lbl_done_sub)

        return w

    # -- Page 3: error
    def _page_error(self) -> QWidget:
        w = QWidget()
        layout = QHBoxLayout(w)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(12)

        err_col = QVBoxLayout()
        err_col.setSpacing(4)

        if HAS_QTAWESOME:
            ic = QLabel()
            ic.setPixmap(qta.icon('fa5s.exclamation-circle', color="#f44336").pixmap(18, 18))

        self._lbl_error = QLabel("Download failed.")
        self._lbl_error.setStyleSheet(
            f"color: {Styles.COLOR_TEXT_PRIMARY}; font-size: 13px; font-weight: 600;"
        )
        err_col.addWidget(self._lbl_error)

        self._lbl_error_detail = QLabel()
        self._lbl_error_detail.setStyleSheet(
            f"color: {Styles.COLOR_TEXT_MUTED}; font-size: 11px;"
        )
        self._lbl_error_detail.setWordWrap(True)
        err_col.addWidget(self._lbl_error_detail)

        layout.addLayout(err_col)
        layout.addStretch()

        btn_browser = QPushButton("  Open in Browser")
        if HAS_QTAWESOME:
            btn_browser.setIcon(qta.icon('fa5s.external-link-alt', color="#ffffff"))
        btn_browser.setStyleSheet(self._btn_style_primary())
        btn_browser.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_browser.clicked.connect(self._open_in_browser)
        layout.addWidget(btn_browser)

        return w

    # ---------------------------------------------------------------- Slots --

    def _start_download(self):
        url = self.update_info.download_url
        if not url:
            self._open_in_browser()
            return

        dest = get_download_destination(url)
        self._dest_path = dest

        self._footer_stack.setCurrentIndex(_PAGE_PROGRESS)
        self._progress_bar.setValue(0)
        self._lbl_status.setText("Downloading…")
        self._lbl_pct.setText("0 %")

        self._worker = DownloadWorker(url, dest, parent=self)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_download_finished)
        self._worker.error.connect(self._on_download_error)
        self._worker.start()

    def _cancel_download(self):
        if self._worker:
            self._worker.cancel()
            self._worker.wait(2000)
            self._worker = None
        self._footer_stack.setCurrentIndex(_PAGE_BUTTONS)

    def _on_progress(self, pct: int):
        self._progress_bar.setValue(pct)
        self._lbl_pct.setText(f"{pct} %")

    def _on_download_finished(self, local_path: str):
        self._worker = None
        self._footer_stack.setCurrentIndex(_PAGE_DONE)
        self._configure_done_page(local_path)

        if PLATFORM == "win32":
            # Delay slightly so the user sees "Installing…" before the app quits
            QTimer.singleShot(1500, lambda: self._do_install(local_path))
        elif PLATFORM == "darwin":
            # macOS: open the DMG; user drags manually — we quit after opening
            QTimer.singleShot(800, lambda: self._do_install(local_path))
        else:
            # Linux: swap script runs after we quit
            QTimer.singleShot(1200, lambda: self._do_install(local_path))

    def _do_install(self, local_path: str):
        from PyQt6.QtWidgets import QApplication
        try:
            install_and_quit(local_path, QApplication.instance().quit)
        except Exception as exc:
            logger.error(f"install_and_quit raised: {exc}")
            self._show_error_page(
                "Install step failed.",
                f"{exc}\n\nYou can install manually from the browser.",
            )

    def _on_download_error(self, msg: str):
        self._worker = None
        if "cancelled" in msg.lower():
            self._footer_stack.setCurrentIndex(_PAGE_BUTTONS)
            return
        self._show_error_page("Download failed.", msg)

    def _show_error_page(self, title: str, detail: str):
        self._lbl_error.setText(title)
        self._lbl_error_detail.setText(detail)
        self._footer_stack.setCurrentIndex(_PAGE_ERROR)

    def _configure_done_page(self, local_path: str):
        """Set the done-page labels and buttons depending on platform."""
        if PLATFORM == "win32":
            self._lbl_done_title.setText("Installing update…")
            self._lbl_done_sub.setText(
                "The installer is running. Chess Analyzer Pro will restart automatically."
            )
            self._btn_open_finder.hide()

        elif PLATFORM == "darwin":
            filename = os.path.basename(local_path)
            self._lbl_done_title.setText(f"Saved to ~/Downloads")
            self._lbl_done_sub.setText(
                f"{filename} — open it, then drag Chess Analyzer Pro to Applications."
            )
            self._btn_open_finder.show()
            self._btn_open_finder.setText("  Open DMG")
            self._dest_path = local_path   # used by _open_in_finder

        else:  # Linux
            self._lbl_done_title.setText("Applying update…")
            self._lbl_done_sub.setText(
                "The new AppImage will launch automatically after this window closes."
            )
            self._btn_open_finder.hide()

    def _open_in_finder(self):
        """macOS: reveal the DMG in Finder (used by the 'Open DMG' button)."""
        import subprocess
        try:
            subprocess.Popen(["open", "-R", self._dest_path])
        except Exception:
            QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.dirname(self._dest_path)))

    def _open_in_browser(self):
        url = self.update_info.html_url or self.update_info.download_url
        if url:
            QDesktopServices.openUrl(QUrl(url))
        self.accept()

    # ------------------------------------------------------------- Helpers --

    def _version_badge(self, version_str: str, label_str: str, color: str) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        lbl = QLabel(label_str)
        lbl.setStyleSheet(f"color: {Styles.COLOR_TEXT_MUTED}; font-size: 10px;")
        layout.addWidget(lbl)
        ver = QLabel(version_str)
        ver.setStyleSheet(f"color: {color}; font-size: 16px; font-weight: bold;")
        layout.addWidget(ver)
        return w

    def _btn_style_primary(self) -> str:
        return f"""
            QPushButton {{
                background-color: {Styles.COLOR_ACCENT};
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 6px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {Styles.COLOR_ACCENT_HOVER};
            }}
            QPushButton:disabled {{
                background-color: {Styles.COLOR_BORDER};
                color: {Styles.COLOR_TEXT_MUTED};
            }}
        """

    def _btn_style_secondary(self) -> str:
        return f"""
            QPushButton {{
                background-color: transparent;
                color: {Styles.COLOR_TEXT_SECONDARY};
                border: 1px solid {Styles.COLOR_BORDER};
                padding: 10px 18px;
                border-radius: 6px;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: {Styles.COLOR_SURFACE_LIGHT};
                color: {Styles.COLOR_TEXT_PRIMARY};
            }}
        """

    @staticmethod
    def _clean_markdown(text: str) -> str:
        text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
        text = re.sub(r'\*(.+?)\*',     r'\1', text)
        text = re.sub(r'^###\s+(.+)$',  r'\n\1:', text, flags=re.MULTILINE)
        text = re.sub(r'^##\s+(.+)$',   r'\n\1:', text, flags=re.MULTILINE)
        text = re.sub(r'^#\s+(.+)$',    r'\n\1:', text, flags=re.MULTILINE)
        text = re.sub(r'^\*\s+',        '• ',     text, flags=re.MULTILINE)
        text = re.sub(r'^-\s+',         '• ',     text, flags=re.MULTILINE)
        text = re.sub(r'\n{3,}',        '\n\n',   text)
        return text.strip()
