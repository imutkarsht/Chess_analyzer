# SPDX-License-Identifier: GPL-3.0-only
"""Update Notification panel, dialog wrapper, and overlay launcher.

States
------
IDLE        -> shows "Download Update" + "Remind Later"
DOWNLOADING -> shows progress bar + "Cancel" (buttons replaced by QStackedWidget)
DONE        -> platform-specific finish panel:
               Windows : "Installing...  App will restart automatically."
               macOS   : "Saved to ~/Downloads  ->  Open DMG" button
               Linux   : "Applying update...  App will relaunch automatically."
ERROR       -> shows error text + "Open in Browser" fallback
"""

from __future__ import annotations

import os
import re

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QStackedWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from src.backend.updater.updater import (
    PLATFORM,
    get_download_destination,
    install_and_quit,
)
from src.gui.components import (
    Button,
    ButtonVariant,
    IconLabel,
    Label,
    OverlayManager,
    ProgressBar,
    ProgressBarVariant,
    RichTextLabel,
    StatusBadge,
    TextRole,
    TextTone,
)
from src.gui.styles import Styles
from src.gui.theme import ThemeManager
from src.gui.utils.links import open_path, open_url
from src.utils.logger import logger
from src.workers import DownloadWorker

_PAGE_BUTTONS = 0
_PAGE_PROGRESS = 1
_PAGE_DONE = 2
_PAGE_ERROR = 3


class UpdateNotificationPanel(QWidget):
    """Version delta, formatted changelog, and self-contained download state machine."""

    accepted = pyqtSignal()
    rejected = pyqtSignal()
    download_active_changed = pyqtSignal(bool)

    def __init__(self, update_info, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.update_info = update_info
        self._worker: DownloadWorker | None = None
        self._dest_path = ""
        self._pending_install_path = ""
        self._changelog_browser: QTextBrowser | None = None
        self._install_timer = QTimer(self)
        self._install_timer.setSingleShot(True)
        self._install_timer.timeout.connect(self._on_install_timeout)
        ThemeManager.instance().theme_changed.connect(self._refresh_changelog_theme)
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(14)

        root.addLayout(self._build_version_row())
        if self.update_info.changelog:
            root.addWidget(self._build_changelog(), 1)
        root.addWidget(self._build_footer())

    def _build_version_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(
            Label(f"v{self.update_info.current}", role=TextRole.BODY, tone=TextTone.MUTED)
        )
        row.addWidget(Label("→", role=TextRole.BODY, tone=TextTone.MUTED))
        row.addWidget(
            Label(
                f"v{self.update_info.latest}",
                role=TextRole.BODY,
                weight=700,
                tone=TextTone.ACCENT,
            )
        )
        row.addStretch()

        short_fmt = {
            "win32": ".exe",
            "darwin": ".dmg",
            "linux": ".AppImage",
        }.get(PLATFORM, ".pkg")
        row.addWidget(
            StatusBadge(
                short_fmt,
                TextTone.ACCENT,
                variant="outline",
                font_size=11,
                weight=700,
                padding="2px 8px",
                radius=8,
            )
        )
        return row

    def _build_changelog(self) -> QWidget:
        w = QWidget(self)
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        top_row = QHBoxLayout()
        top_row.addWidget(Label("What's New", role=TextRole.BODY, weight=600))
        top_row.addStretch()
        if self.update_info.html_url:
            top_row.addWidget(
                Button(
                    "View on GitHub ↗",
                    ButtonVariant.LINK,
                    on_click=self._open_github_release,
                )
            )
        layout.addLayout(top_row)

        changelog_text = QTextBrowser()
        changelog_text.setObjectName("changelogText")
        changelog_text.setReadOnly(True)
        changelog_text.setOpenExternalLinks(True)
        changelog_text.setMinimumHeight(180)
        changelog_text.setHtml(self.format_changelog_html(self.update_info.changelog))
        changelog_text.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        changelog_text.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._changelog_browser = changelog_text
        layout.addWidget(changelog_text, 1)
        return w

    def _refresh_changelog_theme(self, *_args) -> None:
        if self._changelog_browser is not None and self.update_info.changelog:
            self._changelog_browser.setHtml(
                self.format_changelog_html(self.update_info.changelog)
            )

    def _build_footer(self) -> QWidget:
        outer = QWidget(self)
        outer_layout = QVBoxLayout(outer)
        outer_layout.setContentsMargins(0, 4, 0, 0)
        outer_layout.setSpacing(0)

        self._footer_stack = QStackedWidget(outer)
        self._footer_stack.addWidget(self._page_buttons())
        self._footer_stack.addWidget(self._page_progress())
        self._footer_stack.addWidget(self._page_done())
        self._footer_stack.addWidget(self._page_error())
        self._footer_stack.setCurrentIndex(_PAGE_BUTTONS)

        outer_layout.addWidget(self._footer_stack)
        return outer

    def _page_buttons(self) -> QWidget:
        w = QWidget(self._footer_stack)
        layout = QHBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        layout.addStretch()

        btn_later = Button(
            "Remind Later",
            ButtonVariant.HOLLOW,
            icon="clock",
            on_click=self.rejected.emit,
        )
        layout.addWidget(btn_later, 0, Qt.AlignmentFlag.AlignVCenter)

        dl_col = QVBoxLayout()
        dl_col.setSpacing(4)

        self._btn_download = Button(
            "Download Update",
            ButtonVariant.PRIMARY,
            icon="download",
            on_click=self._start_download,
        )
        dl_col.addWidget(self._btn_download)

        if self.update_info.install_hint:
            hint = RichTextLabel(
                f"<i>{self.update_info.install_hint}</i>",
                role=TextRole.MICRO,
                size=10,
                tone=TextTone.MUTED,
            )
            hint.setAlignment(Qt.AlignmentFlag.AlignRight)
            dl_col.addWidget(hint)

        layout.addLayout(dl_col)
        return w

    def _page_progress(self) -> QWidget:
        w = QWidget(self._footer_stack)
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        top_row = QHBoxLayout()
        self._lbl_status = Label("Downloading…", role=TextRole.BODY, weight=600)
        top_row.addWidget(self._lbl_status)
        top_row.addStretch()
        self._lbl_pct = Label("0 %", role=TextRole.CAPTION, tone=TextTone.MUTED)
        top_row.addWidget(self._lbl_pct)
        layout.addLayout(top_row)

        self._progress_bar = ProgressBar(variant=ProgressBarVariant.THIN)
        self._progress_bar.setValue(0)
        layout.addWidget(self._progress_bar)

        btn_cancel = Button("Cancel", ButtonVariant.HOLLOW, on_click=self.cancel_download)
        cancel_row = QHBoxLayout()
        cancel_row.addStretch()
        cancel_row.addWidget(btn_cancel)
        layout.addLayout(cancel_row)
        return w

    def _page_done(self) -> QWidget:
        w = QWidget(self._footer_stack)
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        row = QHBoxLayout()
        row.setSpacing(10)
        row.addWidget(IconLabel("check-circle", size=22, tone=TextTone.BEST))

        self._lbl_done_title = Label("", role=TextRole.BODY, weight=600)
        row.addWidget(self._lbl_done_title)
        row.addStretch()

        self._btn_open_finder = Button(
            "Open in Finder",
            ButtonVariant.PRIMARY,
            icon="folder-open",
            on_click=self._open_in_finder,
        )
        self._btn_open_finder.hide()
        row.addWidget(self._btn_open_finder)
        layout.addLayout(row)

        self._lbl_done_sub = Label("", role=TextRole.MICRO, tone=TextTone.MUTED, wrap=True)
        layout.addWidget(self._lbl_done_sub)
        return w

    def _page_error(self) -> QWidget:
        w = QWidget(self._footer_stack)
        layout = QHBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        err_col = QVBoxLayout()
        err_col.setSpacing(4)
        self._lbl_error = Label("Download failed.", role=TextRole.BODY, weight=600)
        err_col.addWidget(self._lbl_error)
        self._lbl_error_detail = Label(
            "", role=TextRole.MICRO, tone=TextTone.MUTED, wrap=True
        )
        err_col.addWidget(self._lbl_error_detail)

        layout.addLayout(err_col, 1)
        layout.addWidget(
            Button(
                "Open in Browser",
                ButtonVariant.PRIMARY,
                icon="external-link-alt",
                on_click=self._open_in_browser,
            )
        )
        return w

    # ---------------------------------------------------------------- Slots --

    def _start_download(self) -> None:
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
        self.download_active_changed.emit(True)

        self._worker = DownloadWorker(url, dest, parent=self)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_download_finished)
        self._worker.error.connect(self._on_download_error)
        self._worker.start()

    def cancel_download(self) -> None:
        self._install_timer.stop()
        self._pending_install_path = ""
        worker = self._worker
        self._worker = None
        if worker is not None:
            worker.cancel()
            worker.wait(2000)
        self.download_active_changed.emit(False)
        self._footer_stack.setCurrentIndex(_PAGE_BUTTONS)

    def _on_progress(self, pct: int) -> None:
        self._progress_bar.setValue(pct)
        self._lbl_pct.setText(f"{pct} %")

    def _on_download_finished(self, local_path: str) -> None:
        self._worker = None
        self.download_active_changed.emit(False)
        self._footer_stack.setCurrentIndex(_PAGE_DONE)
        self._configure_done_page(local_path)

        delay = 1500 if PLATFORM in ("win32", "darwin") else 1200
        self._pending_install_path = local_path
        self._install_timer.start(delay)

    def _on_install_timeout(self) -> None:
        path = self._pending_install_path
        if path:
            self._do_install(path)

    def _do_install(self, local_path: str) -> None:
        try:
            install_and_quit(local_path, QApplication.instance().quit)
        except Exception as exc:
            logger.error(f"install_and_quit raised: {exc}")
            self._show_error_page(
                "Install step failed.",
                f"{exc}\n\nYou can install manually from the browser.",
            )

    def _on_download_error(self, msg: str) -> None:
        self._worker = None
        self.download_active_changed.emit(False)
        if "cancelled" in msg.lower():
            self._footer_stack.setCurrentIndex(_PAGE_BUTTONS)
            return
        self._show_error_page("Download failed.", msg)

    def _show_error_page(self, title: str, detail: str) -> None:
        self._lbl_error.setText(title)
        self._lbl_error_detail.setText(detail)
        self._footer_stack.setCurrentIndex(_PAGE_ERROR)

    def _configure_done_page(self, local_path: str) -> None:
        if PLATFORM == "win32":
            self._lbl_done_title.setText("Installing update…")
            self._lbl_done_sub.setText(
                "The installer is running. Chess Analyzer Pro will restart automatically."
            )
            self._btn_open_finder.hide()
        elif PLATFORM == "darwin":
            filename = os.path.basename(local_path)
            self._lbl_done_title.setText("Saved to ~/Downloads")
            self._lbl_done_sub.setText(
                f"{filename} — open it, then drag Chess Analyzer Pro to Applications."
            )
            self._btn_open_finder.show()
            self._btn_open_finder.setText("Open DMG")
            self._dest_path = local_path
        else:
            self._lbl_done_title.setText("Applying update…")
            self._lbl_done_sub.setText(
                "The new AppImage will launch automatically after this window closes."
            )
            self._btn_open_finder.hide()

    def _open_in_finder(self) -> None:
        import subprocess

        try:
            subprocess.Popen(["open", "-R", self._dest_path])
        except Exception:
            open_path(os.path.dirname(self._dest_path))

    def _open_in_browser(self) -> None:
        url = self.update_info.html_url or self.update_info.download_url
        if url:
            open_url(url)
        self.accepted.emit()

    def _open_github_release(self) -> None:
        url = (
            self.update_info.html_url
            or "https://github.com/imutkarsht/chess-analyzer/releases"
        )
        open_url(url)

    # ------------------------------------------------------------- Helpers --

    @classmethod
    def format_changelog_html(cls, raw_md: str) -> str:
        """Format GitHub release notes markdown into clean, well-styled HTML."""
        if not raw_md or not raw_md.strip():
            return f"<p style='color: {Styles.COLOR_TEXT_MUTED}; font-style: italic;'>No release notes provided.</p>"

        lines = raw_md.strip().splitlines()
        html_parts: list[str] = []
        in_list = False

        for line in lines:
            stripped = line.strip()

            if not stripped:
                if in_list:
                    html_parts.append("</ul>")
                    in_list = False
                continue

            if stripped.startswith("### "):
                if in_list:
                    html_parts.append("</ul>")
                    in_list = False
                title = cls._inline_format(stripped[4:])
                html_parts.append(
                    f"<h4 style='color: {Styles.COLOR_ACCENT}; font-size: 13px; font-weight: 700; margin: 12px 0 4px 0;'>{title}</h4>"
                )
                continue
            elif stripped.startswith("## "):
                if in_list:
                    html_parts.append("</ul>")
                    in_list = False
                title = cls._inline_format(stripped[3:])
                html_parts.append(
                    f"<h3 style='color: {Styles.COLOR_TEXT_PRIMARY}; font-size: 14px; font-weight: 700; margin: 14px 0 6px 0;'>{title}</h3>"
                )
                continue
            elif stripped.startswith("# "):
                if in_list:
                    html_parts.append("</ul>")
                    in_list = False
                title = cls._inline_format(stripped[2:])
                html_parts.append(
                    f"<h2 style='color: {Styles.COLOR_TEXT_PRIMARY}; font-size: 15px; font-weight: 700; margin: 16px 0 8px 0;'>{title}</h2>"
                )
                continue

            if stripped.startswith(("- ", "* ", "• ")):
                if not in_list:
                    html_parts.append(
                        "<ul style='margin: 4px 0 8px 0; padding-left: 18px; list-style-type: disc;'>"
                    )
                    in_list = True
                content = cls._inline_format(stripped[2:].strip())
                html_parts.append(
                    f"<li style='color: {Styles.COLOR_TEXT_SECONDARY}; font-size: 12px; line-height: 1.55; margin-bottom: 6px;'>{content}</li>"
                )
                continue

            if in_list:
                html_parts.append("</ul>")
                in_list = False

            content = cls._inline_format(stripped)
            html_parts.append(
                f"<p style='color: {Styles.COLOR_TEXT_SECONDARY}; font-size: 12px; line-height: 1.55; margin: 4px 0 6px 0;'>{content}</p>"
            )

        if in_list:
            html_parts.append("</ul>")

        body_html = "\n".join(html_parts)
        return f"""
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: {Styles.COLOR_TEXT_SECONDARY};">
            {body_html}
        </div>
        """

    @classmethod
    def _inline_format(cls, text: str) -> str:
        text = re.sub(
            r"`([^`]+)`",
            rf"<code style='background-color: {Styles.COLOR_SURFACE}; color: {Styles.COLOR_TEXT_PRIMARY}; padding: 1px 4px; border-radius: 3px; font-family: monospace;'>\1</code>",
            text,
        )
        text = re.sub(
            r"\*\*([^*]+)\*\*",
            rf"<strong style='color: {Styles.COLOR_TEXT_PRIMARY}; font-weight: 600;'>\1</strong>",
            text,
        )
        text = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", text)
        text = re.sub(
            r"\[([^\]]+)\]\((https?://[^\)]+)\)",
            rf'<a href="\2" style="color: {Styles.COLOR_ACCENT}; text-decoration: underline;">\1</a>',
            text,
        )

        def _replace_url(match: re.Match) -> str:
            url = match.group(0)
            trailing = ""
            while url and url[-1] in ".,;:!?()":
                trailing = url[-1] + trailing
                url = url[:-1]
            return (
                f'<a href="{url}" style="color: {Styles.COLOR_ACCENT};'
                f' text-decoration: underline;">{url}</a>{trailing}'
            )

        return re.sub(
            r'(?<!href=["\'])(?<![">])(https?://[^\s<"]+)', _replace_url, text
        )


class UpdateNotificationDialog(QDialog):
    """Native QDialog wrapper around ``UpdateNotificationPanel``."""

    def __init__(self, update_info, parent=None):
        super().__init__(parent)
        self.update_info = update_info
        self.setWindowTitle("Update Available")
        self.setMinimumSize(540, 480)
        self.resize(560, 520)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(14)

        title_row = QHBoxLayout()
        title_row.setSpacing(10)
        title_row.addWidget(
            IconLabel("arrow-circle-up", size=24, tone=TextTone.ACCENT)
        )
        title_row.addWidget(
            Label("Update Available", role=TextRole.DIALOG_TITLE, weight=600)
        )
        title_row.addStretch()
        root.addLayout(title_row)

        self.panel = UpdateNotificationPanel(update_info, self)
        self.panel.accepted.connect(self.accept)
        self.panel.rejected.connect(self.reject)
        root.addWidget(self.panel, 1)

    def reject(self) -> None:
        self.panel.cancel_download()
        super().reject()

    def closeEvent(self, event) -> None:
        self.panel.cancel_download()
        super().closeEvent(event)

    @classmethod
    def _format_changelog_html(cls, raw_md: str) -> str:
        return UpdateNotificationPanel.format_changelog_html(raw_md)

    @classmethod
    def _inline_format(cls, text: str) -> str:
        return UpdateNotificationPanel._inline_format(text)


def open_update_overlay(update_info, parent) -> None:
    """Open the update notification panel as an in-window overlay."""
    if isinstance(parent, QWidget):
        try:
            manager = OverlayManager.for_window(parent)
            card = manager.create_card(
                title="Update Available",
                description=f"Version v{update_info.latest} is ready to download.",
                max_width=600,
                minimum_width=420,
                dismiss_on_escape=True,
                dismiss_on_backdrop=True,
            )
            panel = UpdateNotificationPanel(update_info, card)
            card.set_content(panel)

            def on_download_active(active: bool) -> None:
                card.dismiss_on_backdrop = not active
                card.dismiss_on_escape = not active
                card.close_button.setVisible(not active)

            panel.download_active_changed.connect(on_download_active)
            panel.accepted.connect(card.accept)
            panel.rejected.connect(card.reject)

            card.add_cleanup(panel.cancel_download)
            manager.open(card)
            return
        except Exception:
            logger.warning("open_update_overlay failed, falling back", exc_info=True)

    UpdateNotificationDialog(update_info, parent).exec()
