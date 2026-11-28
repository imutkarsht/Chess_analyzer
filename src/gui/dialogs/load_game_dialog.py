# SPDX-License-Identifier: GPL-3.0-only
"""Unified Load Game panel, dialog wrapper, and overlay launcher."""

from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from src.constants import SRC_CHESSCOM, SRC_LICHESS, SRC_PGN_FILE, SRC_PGN_TEXT
from src.gui.components import (
    Button,
    ButtonSize,
    ButtonVariant,
    Label,
    OverlayManager,
    OverlayResult,
    SegmentedControl,
    Tabs,
    TabVariant,
    TextRole,
    TextTone,
)
from src.gui.dialogs.load_game import OnlineFetchPanel, PgnFilePanel, PgnTextPanel
from src.gui.styles import Styles
from src.utils.logger import logger

__all__ = [
    "LoadGameDialog",
    "LoadGamePanel",
    "open_load_game_overlay",
    "SRC_CHESSCOM",
    "SRC_LICHESS",
    "SRC_PGN_FILE",
    "SRC_PGN_TEXT",
]


class LoadGamePanel(QWidget):
    """Content body for importing a game from Chess.com, Lichess, or PGN."""

    batch_ready = pyqtSignal(object)
    navigate_to_settings = pyqtSignal()

    _TAB_KEYS = ("online", "pgn")

    def __init__(
        self,
        parent: QWidget | None = None,
        initial_source: int = SRC_PGN_FILE,
    ) -> None:
        super().__init__(parent)
        self._build_ui()
        self.switch_source(initial_source)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        root.addWidget(self._build_tabs())

        self.pages = QStackedWidget()
        Styles.apply_transparent(self.pages, borderless=False)

        self._online_fetch_panel = OnlineFetchPanel(self)
        self._online_fetch_panel.batch_ready.connect(self.batch_ready.emit)
        self._online_fetch_panel.navigate_to_settings.connect(
            self.navigate_to_settings.emit
        )
        self.pages.addWidget(self._online_fetch_panel)
        self.pages.addWidget(self._build_pgn_page())

        root.addWidget(self.pages, 1)

    def _build_tabs(self) -> QWidget:
        bar = QWidget(self)
        bar.setObjectName("LoadGameTabsBar")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        self.tabs = Tabs(
            TabVariant.UNDERLINE,
            active_style="accent",
            spacing=16,
            padding=(0, 12, 0, 12),
            font_size=13,
            icon_size=16,
        )
        self.tabs.add_tab("Online", icon="globe")
        self.tabs.add_tab(
            "PGN",
            icon="assets/icons/file.png",
        )
        self.tabs.set_tab_tooltip(0, "Import games from Chess.com or Lichess")
        self.tabs.set_tab_tooltip(1, "Open a PGN file or paste PGN text")
        self.tabs.current_changed.connect(self._on_tab_index_changed)
        self.tabs.setFixedHeight(44)
        layout.addWidget(self.tabs, 1)
        return bar

    def _build_pgn_page(self) -> QWidget:
        page = QWidget(self.pages)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(12)

        self.pgn_mode = SegmentedControl(
            [("File", "file"), ("Text", "text")], value="file"
        )
        self.pgn_mode.button("file").setToolTip("Load a .pgn file")
        self.pgn_mode.button("text").setToolTip("Paste PGN text")
        self.pgn_mode.valueChanged.connect(self._on_pgn_mode_changed)
        mode_row = QHBoxLayout()
        mode_row.setContentsMargins(0, 0, 0, 0)
        mode_row.addWidget(self.pgn_mode)
        mode_row.addStretch(1)
        layout.addLayout(mode_row)

        self.pgn_stack = QStackedWidget()
        self._pgn_file_panel = PgnFilePanel(self)
        self._pgn_file_panel.batch_ready.connect(self.batch_ready.emit)
        self._pgn_text_panel = PgnTextPanel(self)
        self._pgn_text_panel.batch_ready.connect(self.batch_ready.emit)
        self.pgn_stack.addWidget(self._pgn_file_panel)
        self.pgn_stack.addWidget(self._pgn_text_panel)
        layout.addWidget(self.pgn_stack, 1)
        return page

    def _on_tab_index_changed(self, index: int) -> None:
        if 0 <= index < len(self._TAB_KEYS):
            self._on_tab_changed(self._TAB_KEYS[index])

    def _on_tab_changed(self, tab_key: str) -> None:
        if tab_key == "online":
            self.pages.setCurrentIndex(0)
        else:
            self._online_fetch_panel.deactivate()
            self.pages.setCurrentIndex(1)

    def _on_pgn_mode_changed(self, mode: str) -> None:
        self.pgn_stack.setCurrentIndex(0 if mode == "file" else 1)

    def switch_source(self, src_id: int) -> None:
        if src_id in (SRC_CHESSCOM, SRC_LICHESS):
            self.tabs.set_current_index(0)
            platform = "chesscom" if src_id == SRC_CHESSCOM else "lichess"
            self._online_fetch_panel.platform_selector.setValue(platform)
            self._online_fetch_panel._on_platform_changed(platform)
        else:
            self.tabs.set_current_index(1)
            mode = "text" if src_id == SRC_PGN_TEXT else "file"
            self.pgn_mode.set_value(mode)
            self._on_pgn_mode_changed(mode)

    def load_initial_text(self, initial_text: str) -> None:
        if self._pgn_text_panel.load_initial_text(initial_text):
            self._pgn_text_panel._parse()

    def shutdown(self) -> None:
        self._online_fetch_panel.deactivate()
        self._pgn_file_panel.shutdown()
        self._pgn_text_panel.shutdown()


class LoadGameDialog(QDialog):
    """Native QDialog wrapper around ``LoadGamePanel``."""

    def __init__(self, parent=None, initial_source: int = SRC_PGN_FILE):
        super().__init__(parent)
        self.setWindowTitle("Load Game")
        self.setModal(True)
        self.resize(640, 560)
        self.setMinimumSize(640, 560)

        self._already_accepted = False
        self._navigate_to_settings = False
        self._pending_batch = None
        self._setup_ui(initial_source)

    def _setup_ui(self, initial_source: int) -> None:
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_header())

        body_host = QWidget()
        body_layout = QVBoxLayout(body_host)
        body_layout.setContentsMargins(24, 0, 24, 16)
        body_layout.setSpacing(0)

        self.panel = LoadGamePanel(body_host, initial_source=initial_source)
        self.panel.batch_ready.connect(self._on_batch_ready)
        self.panel.navigate_to_settings.connect(self._on_navigate_to_settings)
        body_layout.addWidget(self.panel, 1)
        root.addWidget(body_host, 1)
        root.addWidget(self._build_footer())

        # Expose inner panel attributes for compatibility with tests and callers.
        self.tabs = self.panel.tabs
        self.pages = self.panel.pages
        self.pgn_mode = self.panel.pgn_mode
        self.pgn_stack = self.panel.pgn_stack
        self._online_fetch_panel = self.panel._online_fetch_panel
        self._pgn_file_panel = self.panel._pgn_file_panel
        self._pgn_text_panel = self.panel._pgn_text_panel

    def _build_header(self) -> QWidget:
        header = QWidget()
        layout = QVBoxLayout(header)
        layout.setContentsMargins(24, 20, 24, 12)
        layout.setSpacing(4)

        layout.addWidget(Label("Import game", role=TextRole.DIALOG_TITLE))
        layout.addWidget(
            Label(
                "Fetch a game from Chess.com or Lichess, or load a PGN file.",
                role=TextRole.CAPTION,
                tone=TextTone.SECONDARY,
            )
        )
        return header

    def _build_footer(self) -> QWidget:
        footer = QWidget()
        footer.setObjectName("LoadGameFooter")
        footer.setFixedHeight(64)
        layout = QHBoxLayout(footer)
        layout.setContentsMargins(24, 0, 24, 0)
        layout.setSpacing(8)
        layout.addStretch(1)

        cancel = Button(
            "Cancel",
            ButtonVariant.HOLLOW,
            ButtonSize.MD,
            tooltip="Close without loading a game",
            on_click=self.reject,
        )
        cancel.setMinimumWidth(92)
        layout.addWidget(cancel)
        return footer

    def _on_pgn_mode_changed(self, mode: str) -> None:
        self.panel._on_pgn_mode_changed(mode)

    def _on_batch_ready(self, batch) -> None:
        if self._already_accepted:
            return
        self._pending_batch = batch
        self.accept()

    def keyPressEvent(self, event) -> None:  # noqa: N802 - Qt override
        if event.key() == Qt.Key.Key_Escape:
            self.reject()
        else:
            super().keyPressEvent(event)

    def _on_navigate_to_settings(self) -> None:
        self._navigate_to_settings = True
        self.accept()

    def accept(self) -> None:
        self._already_accepted = True
        self._cleanup_workers()
        super().accept()

    def reject(self) -> None:
        self._cleanup_workers()
        super().reject()

    def _cleanup_workers(self) -> None:
        if hasattr(self, "panel"):
            self.panel.shutdown()


def open_load_game_overlay(
    parent,
    *,
    initial_source: int = SRC_PGN_FILE,
    initial_text: str | None = None,
    on_batch: Callable[[object], None] | None = None,
    on_settings: Callable[[], None] | None = None,
) -> None:
    """Open Load Game as an in-window overlay, invoking callbacks asynchronously."""
    if isinstance(parent, QWidget):
        try:
            manager = OverlayManager.for_window(parent)
            card = manager.create_card(
                title="Import game",
                description="Fetch a game from Chess.com or Lichess, or load a PGN file.",
                max_width=680,
                minimum_width=460,
                dismiss_on_escape=True,
                dismiss_on_backdrop=True,
            )
            panel = LoadGamePanel(card, initial_source=initial_source)
            panel.setMinimumHeight(410)
            card.set_content(panel)

            if initial_text and initial_source == SRC_PGN_TEXT:
                panel.load_initial_text(initial_text)

            cancel_btn = Button(
                "Cancel",
                ButtonVariant.HOLLOW,
                ButtonSize.MD,
                tooltip="Close without loading a game",
                on_click=card.reject,
            )
            cancel_btn.setMinimumWidth(92)
            card.add_action(cancel_btn)

            state: dict[str, object] = {"batch": None, "settings": False, "done": False}

            def on_panel_batch(batch) -> None:
                if state["done"]:
                    return
                state["done"] = True
                state["batch"] = batch
                card.accept()

            def on_panel_settings() -> None:
                if state["done"]:
                    return
                state["done"] = True
                state["settings"] = True
                card.accept()

            panel.batch_ready.connect(on_panel_batch)
            panel.navigate_to_settings.connect(on_panel_settings)

            card.add_cleanup(panel.shutdown)

            def on_result(result: OverlayResult) -> None:
                if result is not OverlayResult.ACCEPTED:
                    return
                if state["settings"] and on_settings is not None:
                    on_settings()
                elif state["batch"] is not None and on_batch is not None:
                    on_batch(state["batch"])

            manager.open(card, on_result=on_result)
            return
        except Exception:
            logger.warning("open_load_game_overlay failed, falling back", exc_info=True)

    dialog = LoadGameDialog(parent, initial_source=initial_source)
    try:
        if initial_text and initial_source == SRC_PGN_TEXT:
            dialog.panel.load_initial_text(initial_text)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            if dialog._navigate_to_settings and on_settings is not None:
                on_settings()
            elif dialog._pending_batch is not None and on_batch is not None:
                on_batch(dialog._pending_batch)
    finally:
        dialog.deleteLater()
