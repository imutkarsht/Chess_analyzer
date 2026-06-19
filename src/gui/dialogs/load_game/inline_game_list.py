"""
Inline game list component for the Load Game dialog.
"""
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea
from PyQt6.QtCore import pyqtSignal, Qt
from ...styles import Styles
from .game_card import GameCard

class InlineGameList(QWidget):
    """
    Scrollable list of GameCard rows with 10-games pagination.
    Emits game_chosen(index) when a card is clicked.
    Emits cleared() when the Clear button is clicked.
    Also supports pre-selecting the first item.
    """
    game_chosen = pyqtSignal(int)
    cleared = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(4)

        header_widget = QWidget()
        h_layout = QHBoxLayout(header_widget)
        h_layout.setContentsMargins(2, 0, 2, 0)

        self._header = QLabel("")
        self._header.setStyleSheet(
            f"font-size: 13px; font-weight: 600; color: {Styles.COLOR_TEXT_SECONDARY};"
            " padding: 4px 0px;"
        )
        h_layout.addWidget(self._header)
        h_layout.addStretch()

        self.btn_clear = QPushButton("✕ Clear")
        self.btn_clear.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_clear.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_clear.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 6px;
                color: {Styles.COLOR_TEXT_SECONDARY};
                font-size: 12px;
                padding: 4px 10px;
            }}
            QPushButton:hover {{
                border-color: {Styles.COLOR_ACCENT};
                color: {Styles.COLOR_ACCENT};
                background-color: {Styles.COLOR_ACCENT_SUBTLE};
            }}
        """)
        self.btn_clear.clicked.connect(self.cleared.emit)
        h_layout.addWidget(self.btn_clear)

        root.addWidget(header_widget)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet(f"""
            QScrollArea {{
                background: transparent;
                border: none;
            }}
            QScrollBar:vertical {{
                background: {Styles.COLOR_BACKGROUND};
                width: 6px;
                border-radius: 3px;
            }}
            QScrollBar::handle:vertical {{
                background: {Styles.COLOR_BORDER};
                border-radius: 3px;
                min-height: 20px;
            }}
        """)

        self._content = QWidget()
        self._content.setStyleSheet("background: transparent;")
        self._cards_layout = QVBoxLayout(self._content)
        self._cards_layout.setContentsMargins(2, 2, 8, 2)
        self._cards_layout.setSpacing(6)
        self._cards_layout.addStretch()

        self.scroll.setWidget(self._content)
        root.addWidget(self.scroll, stretch=1)

        # Pagination controls
        self._pagination_widget = QWidget()
        self._pagination_layout = QHBoxLayout(self._pagination_widget)
        self._pagination_layout.setContentsMargins(2, 4, 2, 4)
        self._pagination_layout.setSpacing(10)

        self.btn_prev = QPushButton("◀ Previous")
        self.btn_prev.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_prev.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_prev.setStyleSheet(self._button_style())
        self.btn_prev.clicked.connect(self._prev_page)
        self._pagination_layout.addWidget(self.btn_prev)

        self._pagination_layout.addStretch()

        self.lbl_page = QLabel("")
        self.lbl_page.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {Styles.COLOR_TEXT_SECONDARY};")
        self._pagination_layout.addWidget(self.lbl_page)

        self._pagination_layout.addStretch()

        self.btn_next = QPushButton("Next ▶")
        self.btn_next.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_next.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_next.setStyleSheet(self._button_style())
        self.btn_next.clicked.connect(self._next_page)
        self._pagination_layout.addWidget(self.btn_next)

        root.addWidget(self._pagination_widget)

        self._all_rows: list[tuple[str, str]] = []
        self._cards: list[GameCard] = []
        self._selected_index: int = -1
        self._current_page: int = 0
        self._games_per_page: int = 10
        self._header_template: str = ""

    def _button_style(self):
        return f"""
            QPushButton {{
                background-color: {Styles.COLOR_SURFACE};
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 6px;
                color: {Styles.COLOR_TEXT_PRIMARY};
                font-size: 12px;
                padding: 5px 12px;
            }}
            QPushButton:hover {{
                border-color: {Styles.COLOR_ACCENT};
                background-color: {Styles.COLOR_ACCENT_SUBTLE};
            }}
            QPushButton:disabled {{
                background-color: transparent;
                border-color: {Styles.COLOR_BORDER};
                color: {Styles.COLOR_TEXT_MUTED};
            }}
        """

    def populate(self, rows: list[tuple[str, str]], header: str = ""):
        self._all_rows = rows
        self._header_template = header
        self._current_page = 0
        self._selected_index = -1
        self._update_page()

    def _update_page(self):
        # Clear old cards
        for card in self._cards:
            self._cards_layout.removeWidget(card)
            card.deleteLater()
        self._cards.clear()

        total_games = len(self._all_rows)
        total_pages = (total_games + self._games_per_page - 1) // self._games_per_page

        start_idx = self._current_page * self._games_per_page
        end_idx = min(start_idx + self._games_per_page, total_games)

        # Update Header
        if total_pages > 1:
            header_text = f"{self._header_template} - Page {self._current_page + 1} of {total_pages}"
            self._pagination_widget.setVisible(True)
            self.btn_prev.setEnabled(self._current_page > 0)
            self.btn_next.setEnabled(self._current_page < total_pages - 1)
            self.lbl_page.setText(f"Page {self._current_page + 1} of {total_pages}")
        else:
            header_text = self._header_template
            self._pagination_widget.setVisible(False)

        self._header.setText(header_text)
        self._header.setVisible(bool(header_text))

        # Add cards for current page
        for i in range(start_idx, end_idx):
            line1, line2 = self._all_rows[i]
            card = GameCard(i, line1, line2)
            card.selected.connect(self._on_card_selected)
            self._cards_layout.insertWidget(self._cards_layout.count() - 1, card)
            self._cards.append(card)

        # Restore selection if it's on this page, or pre-select first card on page change
        if self._cards:
            on_page = False
            for card in self._cards:
                if card._index == self._selected_index:
                    card.set_selected(True)
                    on_page = True
            if not on_page:
                self._on_card_selected(start_idx)

    def _on_card_selected(self, absolute_index: int):
        # Deselect old card on page
        for card in self._cards:
            if card._index == self._selected_index:
                card.set_selected(False)
        
        self._selected_index = absolute_index
        
        # Select new card on page
        for card in self._cards:
            if card._index == absolute_index:
                card.set_selected(True)
                
        self.game_chosen.emit(absolute_index)

    def _prev_page(self):
        if self._current_page > 0:
            self._current_page -= 1
            self._update_page()

    def _next_page(self):
        total_pages = (len(self._all_rows) + self._games_per_page - 1) // self._games_per_page
        if self._current_page < total_pages - 1:
            self._current_page += 1
            self._update_page()

    def clear(self):
        self.populate([], "")
