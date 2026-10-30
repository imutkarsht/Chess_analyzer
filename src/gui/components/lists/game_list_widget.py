"""
Game List Widget - a paged, append-only list of analysed games.

The widget owns rendering only: the history view decides which page to load and
the database is the source of truth for totals, so filtering, sorting and
counting never run in Python over the whole table.
"""

from PyQt6.QtCore import QPoint, Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.gui.components.controls.button import Button, ButtonSize, ButtonVariant
from src.gui.components.lists.game_list_item_widget import GameListItemWidget
from src.gui.styles import Styles
from src.gui.utils.smooth_scroll import SmoothScroll


class GameListWidget(QWidget):
    """Container widget for the game list with append-only pages."""

    game_selected = pyqtSignal(object)
    game_action_requested = pyqtSignal(object, str)
    game_deleted = pyqtSignal(str)
    load_more_requested = pyqtSignal()

    # Ask for the next page while the reader is still this far from the end.
    _APPEND_THRESHOLD_PX = 600

    def __init__(self):
        super().__init__()
        self._all_games: list = []
        self._total = 0
        self._rendered = 0
        self._request_pending = False
        self.usernames: list = []
        self.view_mode: str = "compact"  # "compact" or "detailed"
        self.analyzing_game_id: str | None = None

        from src.gui.theme import ThemeManager

        ThemeManager.instance().theme_changed.connect(lambda mode: self.refresh_styles())
        ThemeManager.instance().accent_changed.connect(lambda acc: self.refresh_styles())

        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Header Bar ───────────────────────────────────────────────────────
        self.header_bar_widget = QWidget()
        self.header_bar_widget.setFixedHeight(44)

        header_bar_layout = QHBoxLayout(self.header_bar_widget)
        header_bar_layout.setContentsMargins(16, 0, 16, 0)

        # The result count replaces a section title that only repeated the page title.
        self.title_lbl = QLabel("0 games")
        self.title_lbl.setStyleSheet(self._count_style())
        header_bar_layout.addWidget(self.title_lbl)

        header_bar_layout.addStretch()

        # View mode toggle buttons
        self.btn_detailed = Button(
            variant=ButtonVariant.FILLED,
            size=ButtonSize.SM,
            icon="fa5s.th-large",
            icon_position="only",
            checkable=True,
            tooltip="Detailed Cards View",
            on_click=lambda: self.set_view_mode("detailed"),
        )
        self.btn_detailed.setFixedSize(30, 26)

        self.btn_compact = Button(
            variant=ButtonVariant.FILLED,
            size=ButtonSize.SM,
            icon="fa5s.list",
            icon_position="only",
            checkable=True,
            tooltip="Compact Table View",
            on_click=lambda: self.set_view_mode("compact"),
        )
        self.btn_compact.setFixedSize(30, 26)

        header_bar_layout.addWidget(self.btn_detailed)
        header_bar_layout.addWidget(self.btn_compact)
        root.addWidget(self.header_bar_widget)

        # ── List ─────────────────────────────────────────────────────────────
        self.list_widget = QListWidget()
        self.list_widget.setFrameShape(QFrame.Shape.NoFrame)
        self.list_widget.setSpacing(0)
        self.list_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        # Rows share one height, so the view can skip per-item size lookups.
        self.list_widget.setUniformItemSizes(True)
        SmoothScroll(self.list_widget)
        self.list_widget.itemClicked.connect(self._on_item_clicked)
        self.list_widget.verticalScrollBar().valueChanged.connect(self._maybe_request_page)
        root.addWidget(self.list_widget, stretch=1)

        self._update_view_toggle_styles()

    # ── Data API ──────────────────────────────────────────────────────────────

    def reset(self, total: int | None = None, usernames=None):
        """Clear rendered rows and start a new result set."""
        self._all_games = []
        self._rendered = 0
        self._request_pending = False
        self.list_widget.clear()
        if total is not None:
            self._total = max(0, int(total))
        if usernames is not None:
            self.usernames = usernames
        self._update_count()

    def append_rows(self, games):
        """Append one fetched page of ``GameAnalysis`` rows."""
        games = list(games or [])
        if not games:
            self._request_pending = False
            return
        self._all_games.extend(games)
        self._render_from(self._rendered)
        self._request_pending = False
        self._update_count()
        # If the page does not fill the viewport there is no scrollbar event to
        # ask for more, so check once the layout has settled.
        QTimer.singleShot(0, self._fill_if_needed)

    def set_games(self, games, usernames=None):
        """Replace every row at once (non-paged callers and tests)."""
        games = list(games or [])
        self.reset(total=len(games), usernames=usernames)
        self.append_rows(games)

    def set_total(self, total: int):
        """Update the result count without touching rendered rows."""
        self._total = max(0, int(total))
        self._request_pending = False
        self._update_count()

    def update_row(self, game_id: str, game):
        """Replace a single rendered row in place (keeps scroll position)."""
        for row, existing in enumerate(self._all_games):
            if getattr(existing, "game_id", None) != game_id:
                continue
            item = self.list_widget.item(row)
            if item is None:
                return
            widget = self._build_item_widget(game)
            item.setSizeHint(widget.sizeHint())
            self.list_widget.setItemWidget(item, widget)
            self._all_games[row] = game
            return

    def remove_row(self, game_id: str) -> bool:
        """Remove one row after a delete and decrement the total."""
        for row, existing in enumerate(self._all_games):
            if getattr(existing, "game_id", None) != game_id:
                continue
            self.list_widget.takeItem(row)
            self._all_games.pop(row)
            self._rendered = max(0, self._rendered - 1)
            self._total = max(0, self._total - 1)
            self._update_count()
            return True
        return False

    @property
    def games(self):
        """Compatibility shim — the currently rendered rows."""
        return self._all_games

    @games.setter
    def games(self, value):
        self._all_games = list(value)

    @property
    def total_count(self) -> int:
        """Total rows matching the active query, from the database."""
        return self._total

    def top_game_id(self) -> str | None:
        """The id of the first visible row, used to restore scroll position."""
        index = self.list_widget.indexAt(QPoint(0, 1))
        if not index.isValid():
            index = self.list_widget.indexAt(QPoint(0, 0))
        row = index.row()
        if 0 <= row < len(self._all_games):
            return getattr(self._all_games[row], "game_id", None)
        return None

    def scroll_to_game(self, game_id: str) -> bool:
        """Scroll so ``game_id`` sits at the top of the viewport."""
        for row, game in enumerate(self._all_games):
            if getattr(game, "game_id", None) != game_id:
                continue
            item = self.list_widget.item(row)
            if item is not None:
                self.list_widget.scrollToItem(
                    item, QAbstractItemView.ScrollHint.PositionAtTop
                )
            return True
        return False

    def set_view_mode(self, mode: str):
        """Switch between 'detailed' card view and 'compact' list view."""
        if mode in ("detailed", "compact") and mode != self.view_mode:
            self.view_mode = mode
            self._update_view_toggle_styles()
            # Row height changes with the mode, so re-lay out the loaded rows.
            self._rebuild()

    def set_analyzing_game_id(self, game_id: str | None):
        """Update currently analyzing game ID so the active card reflects Analyzing state."""
        if self.analyzing_game_id != game_id:
            self.analyzing_game_id = game_id
            if self._all_games:
                self._rebuild(preserve_scroll=True)

    def _update_view_toggle_styles(self):
        is_detailed = self.view_mode == "detailed"
        self.btn_detailed.setChecked(is_detailed)
        self.btn_compact.setChecked(not is_detailed)
        self.btn_detailed.refresh_styles()
        self.btn_compact.refresh_styles()

    # ── Rendering ─────────────────────────────────────────────────────────────

    def _render_from(self, start: int):
        """Render stored rows from ``start`` to the end of the list."""
        for index in range(start, len(self._all_games)):
            game = self._all_games[index]
            widget = self._build_item_widget(game)
            hint = widget.sizeHint()
            item = QListWidgetItem()
            item.setSizeHint(hint)
            self.list_widget.addItem(item)
            self.list_widget.setItemWidget(item, widget)
        self._rendered = len(self._all_games)

    def _build_item_widget(self, game) -> GameListItemWidget:
        is_analyzing = bool(
            self.analyzing_game_id and getattr(game, "game_id", None) == self.analyzing_game_id
        )
        widget = GameListItemWidget(
            game, self.usernames, view_mode=self.view_mode, is_analyzing=is_analyzing
        )
        widget.delete_requested.connect(self._on_delete_requested)
        widget.action_requested.connect(self.game_action_requested.emit)
        return widget

    def _rebuild(self, preserve_scroll: bool = False):
        """Re-render every loaded row (view-mode switch, style refresh)."""
        top_id = self.top_game_id() if preserve_scroll else None
        rows = list(self._all_games)
        self.list_widget.clear()
        self._rendered = 0
        self._all_games = []
        self.append_rows(rows)
        if top_id:
            self.scroll_to_game(top_id)

    def _maybe_request_page(self, value: int):
        """Ask the view for the next page as the reader nears the end."""
        if self._request_pending or self._rendered >= self._total:
            return
        bar = self.list_widget.verticalScrollBar()
        # A zero range means the list is not laid out yet: asking there would
        # fire one request per appended page.
        if bar.maximum() <= 0:
            return
        if bar.maximum() - value > self._APPEND_THRESHOLD_PX:
            return
        self._request_page()

    def _request_page(self):
        if self._request_pending or self._rendered >= self._total:
            return
        self._request_pending = True
        self.load_more_requested.emit()

    def _fill_if_needed(self):
        """Request another page when a page does not fill the viewport."""
        if self._rendered >= self._total:
            return
        if not self.list_widget.isVisible() or self.list_widget.viewport().height() <= 0:
            return
        if self.list_widget.verticalScrollBar().maximum() <= 0:
            self._request_page()

    def showEvent(self, event):  # noqa: N802 - Qt override
        super().showEvent(event)
        # The first page loads while the page is hidden, so top up on reveal.
        QTimer.singleShot(0, self._fill_if_needed)

    def _update_count(self):
        self.title_lbl.setText(f"{self._total:,} game{'' if self._total == 1 else 's'}")

    # ── Navigation ────────────────────────────────────────────────────────────

    def _on_delete_requested(self, game_id: str):
        """Delete a single game from history after confirmation."""
        from src.backend.storage.game_history import GameHistoryManager
        from src.gui.utils.gui_utils import confirm_dialog

        if not confirm_dialog(
            self,
            "Delete Game",
            "Remove this game from history? This cannot be undone.",
            confirm_label="Delete",
        ):
            return

        try:
            GameHistoryManager().delete_game(game_id)
        except Exception as e:
            from src.utils.logger import logger

            logger.error(f"Failed to delete game {game_id}: {e}")
            return

        self.remove_row(game_id)
        self.game_deleted.emit(game_id)

    def _on_item_clicked(self, item):
        row = self.list_widget.row(item)
        if 0 <= row < len(self._all_games):
            self.game_selected.emit(self._all_games[row])

    # ── Style refresh ─────────────────────────────────────────────────────────

    @staticmethod
    def _count_style() -> str:
        return (
            Styles.get_label_style(size=13, color=Styles.COLOR_TEXT_SECONDARY, weight=600)
            + " "
            + Styles.get_transparent_label_style()
        )

    def _apply_title_style(self):
        if hasattr(self, "header_bar_widget") and self.header_bar_widget:
            self.header_bar_widget.setStyleSheet(Styles.get_header_bar_style())
        if hasattr(self, "title_lbl") and self.title_lbl:
            self.title_lbl.setStyleSheet(self._count_style())

    def _apply_list_style(self):
        self.list_widget.setStyleSheet(Styles.get_list_widget_style())

    def refresh_styles(self):
        """Re-applies styles on theme change."""
        self._apply_title_style()
        self._apply_list_style()
        self._update_view_toggle_styles()
        self._rebuild(preserve_scroll=True)
