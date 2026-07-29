"""
Game List Widget - Paginated list container for chess games.
"""
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem, QFrame, QLabel, QPushButton
from PyQt6.QtCore import pyqtSignal, Qt
from ..styles import Styles
from .game_list_item_widget import GameListItemWidget

try:
    import qtawesome as qta
    HAS_QTAWESOME = True
except ImportError:
    HAS_QTAWESOME = False

class GameListWidget(QWidget):
    """Container widget for the game list with pagination (10 games per page)."""

    game_selected = pyqtSignal(object)
    _PAGE_SIZE = 10

    def __init__(self):
        super().__init__()
        self._all_games: list = []
        self._current_page: int = 0
        self.usernames: list = []
        self.view_mode: str = "compact"  # "compact" or "detailed"

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
        self.title_lbl.setStyleSheet(Styles.get_label_style(size=15, color=Styles.COLOR_TEXT_PRIMARY, bold=True) + " " + Styles.get_transparent_label_style())
        header_bar_layout.addWidget(self.title_lbl)

        header_bar_layout.addStretch()

        # View mode toggle buttons
        self.btn_detailed = QPushButton()
        self.btn_detailed.setFixedSize(30, 26)
        self.btn_detailed.setToolTip("Detailed Cards View")
        self.btn_detailed.setCursor(Qt.CursorShape.PointingHandCursor)

        self.btn_compact = QPushButton()
        self.btn_compact.setFixedSize(30, 26)
        self.btn_compact.setToolTip("Compact Table View")
        self.btn_compact.setCursor(Qt.CursorShape.PointingHandCursor)

        if HAS_QTAWESOME:
            self.btn_detailed.setIcon(qta.icon("fa5s.th-large", color=Styles.COLOR_TEXT_PRIMARY))
            self.btn_compact.setIcon(qta.icon("fa5s.list", color=Styles.COLOR_TEXT_PRIMARY))
        else:
            self.btn_detailed.setText("田")
            self.btn_compact.setText("≡")

        self.btn_detailed.clicked.connect(lambda: self.set_view_mode("detailed"))
        self.btn_compact.clicked.connect(lambda: self.set_view_mode("compact"))

        header_bar_layout.addWidget(self.btn_detailed)
        header_bar_layout.addWidget(self.btn_compact)
        root.addWidget(self.header_bar_widget)

        # ── List ─────────────────────────────────────────────────────────────
        self.list_widget = QListWidget()
        self.list_widget.setFrameShape(QFrame.Shape.NoFrame)
        self.list_widget.setSpacing(0)
        self.list_widget.itemClicked.connect(self._on_item_clicked)
        root.addWidget(self.list_widget, stretch=1)

        # ── Pagination bar ───────────────────────────────────────────────────
        self._pagination_bar = QWidget()
        self._pagination_bar.setFixedHeight(52)
        self._pagination_bar.setStyleSheet(Styles.get_pagination_bar_style())
        self._page_bar_layout = QHBoxLayout(self._pagination_bar)
        self._page_bar_layout.setContentsMargins(16, 0, 16, 0)
        self._page_bar_layout.setSpacing(6)
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
        is_detailed = (self.view_mode == "detailed")
        if HAS_QTAWESOME:
            detailed_icon_color = "#FFFFFF" if is_detailed else Styles.COLOR_TEXT_PRIMARY
            compact_icon_color = "#FFFFFF" if not is_detailed else Styles.COLOR_TEXT_PRIMARY
            self.btn_detailed.setIcon(qta.icon("fa5s.th-large", color=detailed_icon_color))
            self.btn_compact.setIcon(qta.icon("fa5s.list", color=compact_icon_color))
        self.btn_detailed.setStyleSheet(Styles.get_toggle_button_style(active=is_detailed))
        self.btn_compact.setStyleSheet(Styles.get_toggle_button_style(active=not is_detailed))

    # ── Public API ────────────────────────────────────────────────────────────

    def set_games(self, games, usernames=None):
        """Replace the game list and jump back to page 1."""
        self._all_games = games or []
        if usernames is not None:
            self.usernames = usernames
        self._current_page = 0
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

    def _total_pages(self) -> int:
        if not self._all_games:
            return 1
        import math
        return math.ceil(len(self._all_games) / self.page_size)

    def _render_page(self):
        """Populate the list widget with the current page's games."""
        self.list_widget.clear()

        # Clamp current page when page size changes
        max_page = max(0, self._total_pages() - 1)
        if self._current_page > max_page:
            self._current_page = max_page

        ps = self.page_size
        start = self._current_page * ps
        end = start + ps
        page_games = self._all_games[start:end]

        for game in page_games:
            item = QListWidgetItem(self.list_widget)
            widget = GameListItemWidget(game, self.usernames, view_mode=self.view_mode)
            widget.delete_requested.connect(self._on_delete_requested)
            item.setSizeHint(widget.sizeHint())
            self.list_widget.addItem(item)
            self.list_widget.setItemWidget(item, widget)

        self._rebuild_pagination()

    def _rebuild_pagination(self):
        """Rebuild the pagination button bar to reflect the current state."""
        while self._page_bar_layout.count():
            child = self._page_bar_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        total = self._total_pages()
        current = self._current_page
        ps = self.page_size

        # ── Page counter label (left) ────────────────────────────────────────
        start = current * ps + 1
        end = min(start + ps - 1, len(self._all_games))
        total_games = len(self._all_games)

        if total_games == 0:
            counter_text = "No games"
        else:
            counter_text = f"{start}–{end} of {total_games}"

        counter = QLabel(counter_text)
        counter.setStyleSheet(Styles.get_label_style(size=12, color=Styles.COLOR_TEXT_SECONDARY) + " " + Styles.get_transparent_label_style())
        self._page_bar_layout.addWidget(counter)
        self._page_bar_layout.addStretch()

        # ── Prev button ──────────────────────────────────────────────────────
        btn_prev = self._make_page_btn("‹ Prev", enabled=(current > 0))
        btn_prev.clicked.connect(self._go_prev)
        self._page_bar_layout.addWidget(btn_prev)

        # ── Page number buttons (show up to 5 around current) ────────────────
        window = 2
        lo = max(0, current - window)
        hi = min(total - 1, current + window)

        if lo > 0:
            self._page_bar_layout.addWidget(self._make_page_num_btn(0))
            if lo > 1:
                self._page_bar_layout.addWidget(self._make_ellipsis())

        for p in range(lo, hi + 1):
            self._page_bar_layout.addWidget(self._make_page_num_btn(p))

        if hi < total - 1:
            if hi < total - 2:
                self._page_bar_layout.addWidget(self._make_ellipsis())
            self._page_bar_layout.addWidget(self._make_page_num_btn(total - 1))

        # ── Next button ──────────────────────────────────────────────────────
        btn_next = self._make_page_btn("Next ›", enabled=(current < total - 1))
        btn_next.clicked.connect(self._go_next)
        self._page_bar_layout.addWidget(btn_next)

    # ── Navigation ────────────────────────────────────────────────────────────

    def _on_delete_requested(self, game_id: str):
        """Delete a single game from history after confirmation."""
        from src.gui.utils.gui_utils import confirm_dialog
        from src.backend.storage.game_history import GameHistoryManager

        if not confirm_dialog(self,
                              "Delete Game",
                              "Remove this game from history? This cannot be undone.",
                              confirm_label="Delete"):
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
        max_page = max(0, self._total_pages() - 1)
        if self._current_page > max_page:
            self._current_page = max_page

        self._render_page()

    def _go_prev(self):
        if self._current_page > 0:
            self._current_page -= 1
            self._render_page()

    def _go_next(self):
        if self._current_page < self._total_pages() - 1:
            self._current_page += 1
            self._render_page()

    def _go_to_page(self, page: int):
        if 0 <= page < self._total_pages():
            self._current_page = page
            self._render_page()

    def _on_item_clicked(self, item):
        index = self.list_widget.row(item)
        start = self._current_page * self.page_size
        absolute_index = start + index
        if 0 <= absolute_index < len(self._all_games):
            self.game_selected.emit(self._all_games[absolute_index])

    # ── Button factories ──────────────────────────────────────────────────────

    def _make_page_btn(self, text: str, enabled: bool) -> QPushButton:
        btn = QPushButton(text)
        btn.setFixedHeight(30)
        btn.setEnabled(enabled)
        btn.setCursor(Qt.CursorShape.PointingHandCursor if enabled else Qt.CursorShape.ArrowCursor)
        btn.setStyleSheet(Styles.get_page_btn_style(enabled=enabled))
        return btn

    def _make_page_num_btn(self, page: int) -> QPushButton:
        is_current = (page == self._current_page)
        btn = QPushButton(str(page + 1))
        btn.setFixedSize(30, 30)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet(Styles.get_page_num_btn_style(active=is_current))
        btn.clicked.connect(lambda _, p=page: self._go_to_page(p))
        return btn

    def _make_ellipsis(self) -> QLabel:
        lbl = QLabel("…")
        lbl.setFixedSize(20, 30)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet(Styles.get_label_style(size=13, color=Styles.COLOR_TEXT_MUTED) + " " + Styles.get_transparent_label_style())
        return lbl

    # ── Style refresh ─────────────────────────────────────────────────────────

    def _apply_title_style(self):
        if hasattr(self, 'header_bar_widget') and self.header_bar_widget:
            self.header_bar_widget.setStyleSheet(Styles.get_header_bar_style())
        if hasattr(self, 'title_lbl') and self.title_lbl:
            self.title_lbl.setStyleSheet(Styles.get_label_style(size=15, color=Styles.COLOR_TEXT_PRIMARY, bold=True) + " " + Styles.get_transparent_label_style())

    def _apply_list_style(self):
        self.list_widget.setStyleSheet(Styles.get_list_widget_style())

    def refresh_styles(self):
        """Re-applies styles on theme change."""
        self._apply_title_style()
        self._apply_list_style()
        self._pagination_bar.setStyleSheet(Styles.get_pagination_bar_style())
        self._update_view_toggle_styles()
        self._render_page()
