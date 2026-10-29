"""
Game List Widget - Paginated list container for chess games.
"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..styles import Styles
from .button import Button, ButtonSize, ButtonVariant
from .game_list_item_widget import GameListItemWidget
from .pagination_bar import PaginationBar, PaginationSize, PaginationState, PaginationStyle
from .smooth_scroll import SmoothScroll


class GameListWidget(QWidget):
    """Container widget for the game list with pagination (10 games per page)."""

    game_selected = pyqtSignal(object)
    game_action_requested = pyqtSignal(object, str)
    game_deleted = pyqtSignal(str)
    _PAGE_SIZE = 10

    def __init__(self):
        super().__init__()
        self._all_games: list = []
        self.pagination_state = PaginationState(page_size=self._PAGE_SIZE)
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

        self.title_lbl = QLabel("Games")
        self.title_lbl.setStyleSheet(
            Styles.get_label_style(size=15, color=Styles.COLOR_TEXT_PRIMARY, bold=True)
            + " "
            + Styles.get_transparent_label_style()
        )
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
        # Paginated rows all share one height, so let the view skip per-item
        # size lookups while scrolling.
        self.list_widget.setUniformItemSizes(True)
        SmoothScroll(self.list_widget)
        self.list_widget.itemClicked.connect(self._on_item_clicked)
        root.addWidget(self.list_widget, stretch=1)

        # ── Pagination bar ───────────────────────────────────────────────────
        self._pagination_bar = PaginationBar(
            self.pagination_state,
            style=PaginationStyle.NUMBERED,
            size=PaginationSize.PAGE,
            framed=True,
            show_range=True,
            empty_text="No games",
            margins=(16, 0, 16, 0),
        )
        self._pagination_bar.setFixedHeight(52)
        self._pagination_bar.page_changed.connect(lambda _page: self._render_page())
        root.addWidget(self._pagination_bar)

        self._update_view_toggle_styles()
        self._render_page()

    def set_view_mode(self, mode: str):
        """Switch between 'detailed' card view and 'compact' list view."""
        if mode in ("detailed", "compact") and mode != self.view_mode:
            self.view_mode = mode
            self._update_view_toggle_styles()
            self._render_page()

    def _update_view_toggle_styles(self):
        is_detailed = self.view_mode == "detailed"
        self.btn_detailed.setChecked(is_detailed)
        self.btn_compact.setChecked(not is_detailed)
        self.btn_detailed.refresh_styles()
        self.btn_compact.refresh_styles()

    # ── Public API ────────────────────────────────────────────────────────────

    def set_analyzing_game_id(self, game_id: str | None):
        """Update currently analyzing game ID so the active card reflects Analyzing state."""
        if self.analyzing_game_id != game_id:
            self.analyzing_game_id = game_id
            if self._all_games:
                self._render_page()

    def set_games(self, games, usernames=None):
        """Replace the game list and jump back to page 1."""
        self._all_games = games or []
        if usernames is not None:
            self.usernames = usernames
        self.pagination_state.set_page(0)
        self._render_page()

    @property
    def games(self):
        """Compatibility shim — callers that read .games get the full list."""
        return self._all_games

    @games.setter
    def games(self, value):
        self._all_games = list(value)

    @property
    def page_size(self) -> int:
        """Fit items on screen without vertical scrolling (10 for compact, 5 for detailed card view)."""
        return 10 if self.view_mode == "compact" else 5

    # ── Rendering ─────────────────────────────────────────────────────────────

    def _render_page(self):
        """Populate the list widget with the current page's games."""
        self.list_widget.clear()

        self.pagination_state.set_page_size(self.page_size)
        self.pagination_state.set_total_items(len(self._all_games))

        for game in self.pagination_state.slice(self._all_games):
            item = QListWidgetItem(self.list_widget)
            is_analyzing = bool(
                self.analyzing_game_id and getattr(game, "game_id", None) == self.analyzing_game_id
            )
            widget = GameListItemWidget(
                game, self.usernames, view_mode=self.view_mode, is_analyzing=is_analyzing
            )
            widget.delete_requested.connect(self._on_delete_requested)
            widget.action_requested.connect(self.game_action_requested.emit)
            item.setSizeHint(widget.sizeHint())
            self.list_widget.addItem(item)
            self.list_widget.setItemWidget(item, widget)

        self._pagination_bar.sync()

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
            from ...utils.logger import logger

            logger.error(f"Failed to delete game {game_id}: {e}")
            return

        # Remove from the local list and re-render without reloading from DB
        self._all_games = [g for g in self._all_games if g.game_id != game_id]

        # Stay on the current page unless it no longer exists
        self.pagination_state.set_total_items(len(self._all_games))

        self._render_page()
        self.game_deleted.emit(game_id)

    def _on_item_clicked(self, item):
        index = self.list_widget.row(item)
        absolute_index = self.pagination_state.start_index + index
        if 0 <= absolute_index < len(self._all_games):
            self.game_selected.emit(self._all_games[absolute_index])

    # ── Style refresh ─────────────────────────────────────────────────────────

    def _apply_title_style(self):
        if hasattr(self, "header_bar_widget") and self.header_bar_widget:
            self.header_bar_widget.setStyleSheet(Styles.get_header_bar_style())
        if hasattr(self, "title_lbl") and self.title_lbl:
            self.title_lbl.setStyleSheet(
                Styles.get_label_style(size=15, color=Styles.COLOR_TEXT_PRIMARY, bold=True)
                + " "
                + Styles.get_transparent_label_style()
            )

    def _apply_list_style(self):
        self.list_widget.setStyleSheet(Styles.get_list_widget_style())

    def refresh_styles(self):
        """Re-applies styles on theme change."""
        self._apply_title_style()
        self._apply_list_style()
        self._pagination_bar.refresh_styles()
        self._update_view_toggle_styles()
        self._render_page()
