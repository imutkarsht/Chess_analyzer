"""
Game List Widget - Paginated list container for chess games.
"""
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem, QFrame, QLabel, QPushButton
from PyQt6.QtCore import pyqtSignal, Qt
from ..styles import Styles
from .game_list_item_widget import GameListItemWidget

class GameListWidget(QWidget):
    """Container widget for the game list with pagination (10 games per page)."""

    game_selected = pyqtSignal(object)
    _PAGE_SIZE = 10

    def __init__(self):
        super().__init__()
        self._all_games: list = []
        self._current_page: int = 0
        self.usernames: list = []

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Header ──────────────────────────────────────────────────────────
        self.title_label = QLabel("Games")
        self._apply_title_style()
        root.addWidget(self.title_label)

        # ── List ─────────────────────────────────────────────────────────────
        self.list_widget = QListWidget()
        self.list_widget.setFrameShape(QFrame.Shape.NoFrame)
        self.list_widget.setSpacing(0)
        self._apply_list_style()
        self.list_widget.itemClicked.connect(self._on_item_clicked)
        root.addWidget(self.list_widget, stretch=1)

        # ── Pagination bar ───────────────────────────────────────────────────
        self._pagination_bar = QWidget()
        self._pagination_bar.setFixedHeight(52)
        self._pagination_bar.setStyleSheet(
            f"background-color: {Styles.COLOR_SURFACE}; border-top: 1px solid {Styles.COLOR_BORDER};"
        )
        self._page_bar_layout = QHBoxLayout(self._pagination_bar)
        self._page_bar_layout.setContentsMargins(16, 0, 16, 0)
        self._page_bar_layout.setSpacing(6)
        root.addWidget(self._pagination_bar)

        # Alias kept for history_view.py refresh_styles() call
        self.layout = root

        self._render_page()

    # ── Public API ────────────────────────────────────────────────────────────

    def set_games(self, games, usernames=None):
        """Replace the game list and jump back to page 1."""
        self._all_games = list(games)
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

    # ── Rendering ─────────────────────────────────────────────────────────────

    def _total_pages(self) -> int:
        if not self._all_games:
            return 1
        import math
        return math.ceil(len(self._all_games) / self._PAGE_SIZE)

    def _render_page(self):
        """Populate the list widget with the current page's games."""
        self.list_widget.clear()

        start = self._current_page * self._PAGE_SIZE
        end = start + self._PAGE_SIZE
        page_games = self._all_games[start:end]

        for game in page_games:
            item = QListWidgetItem(self.list_widget)
            widget = GameListItemWidget(game, self.usernames)
            widget.delete_requested.connect(self._on_delete_requested)
            item.setSizeHint(widget.sizeHint())
            self.list_widget.addItem(item)
            self.list_widget.setItemWidget(item, widget)

        self._rebuild_pagination()

    def _rebuild_pagination(self):
        """Rebuild the pagination button bar to reflect the current state."""
        # Clear existing widgets
        while self._page_bar_layout.count():
            child = self._page_bar_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        total = self._total_pages()
        current = self._current_page

        # ── Page counter label (left) ────────────────────────────────────────
        start = current * self._PAGE_SIZE + 1
        end = min(start + self._PAGE_SIZE - 1, len(self._all_games))
        total_games = len(self._all_games)

        if total_games == 0:
            counter_text = "No games"
        else:
            counter_text = f"{start}–{end} of {total_games}"

        counter = QLabel(counter_text)
        counter.setStyleSheet(
            f"color: {Styles.COLOR_TEXT_SECONDARY}; font-size: 12px;"
            " background: transparent; border: none;"
        )
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
        from PyQt6.QtWidgets import QMessageBox
        from ...backend.game_history import GameHistoryManager

        reply = QMessageBox.question(
            self,
            "Delete Game",
            "Remove this game from history? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
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
        start = self._current_page * self._PAGE_SIZE
        absolute_index = start + index
        if 0 <= absolute_index < len(self._all_games):
            self.game_selected.emit(self._all_games[absolute_index])

    # ── Button factories ──────────────────────────────────────────────────────

    def _make_page_btn(self, text: str, enabled: bool) -> QPushButton:
        btn = QPushButton(text)
        btn.setFixedHeight(30)
        btn.setEnabled(enabled)
        btn.setCursor(Qt.CursorShape.PointingHandCursor if enabled else Qt.CursorShape.ArrowCursor)
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Styles.COLOR_SURFACE_LIGHT if enabled else 'transparent'};
                color: {Styles.COLOR_TEXT_PRIMARY if enabled else Styles.COLOR_TEXT_MUTED};
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 6px;
                padding: 0 12px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {Styles.COLOR_ACCENT};
                color: {Styles.COLOR_TEXT_PRIMARY};
                border-color: {Styles.COLOR_ACCENT};
            }}
            QPushButton:disabled {{
                opacity: 0.4;
            }}
        """)
        return btn

    def _make_page_num_btn(self, page: int) -> QPushButton:
        is_current = (page == self._current_page)
        btn = QPushButton(str(page + 1))
        btn.setFixedSize(30, 30)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Styles.COLOR_ACCENT if is_current else Styles.COLOR_SURFACE_LIGHT};
                color: {Styles.COLOR_TEXT_PRIMARY};
                border: 1px solid {Styles.COLOR_ACCENT if is_current else Styles.COLOR_BORDER};
                border-radius: 6px;
                font-size: 12px;
                font-weight: {'700' if is_current else '400'};
            }}
            QPushButton:hover {{
                background-color: {Styles.COLOR_ACCENT};
                border-color: {Styles.COLOR_ACCENT};
            }}
        """)
        btn.clicked.connect(lambda _, p=page: self._go_to_page(p))
        return btn

    def _make_ellipsis(self) -> QLabel:
        lbl = QLabel("…")
        lbl.setFixedSize(20, 30)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet(
            f"color: {Styles.COLOR_TEXT_MUTED}; font-size: 13px;"
            " background: transparent; border: none;"
        )
        return lbl

    # ── Style refresh ─────────────────────────────────────────────────────────

    def _apply_title_style(self):
        self.title_label.setStyleSheet(f"""
            padding: 16px 20px;
            font-weight: 600;
            font-size: 16px;
            color: {Styles.COLOR_TEXT_PRIMARY};
            background-color: {Styles.COLOR_SURFACE};
            border-bottom: 2px solid {Styles.COLOR_ACCENT};
        """)

    def _apply_list_style(self):
        self.list_widget.setStyleSheet(f"""
            QListWidget {{
                background-color: {Styles.COLOR_BACKGROUND};
                border: none;
                outline: none;
            }}
            QListWidget::item {{
                background-color: {Styles.COLOR_BACKGROUND};
                border: none;
                border-bottom: 1px solid {Styles.COLOR_SURFACE_LIGHT};
                padding: 0px;
                margin: 0px;
            }}
            QListWidget::item:hover {{
                background-color: {Styles.COLOR_SURFACE};
            }}
        """)
