"""
Inline game list component for the Load Game dialog.
"""
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from ...components import (
    Button,
    ButtonSize,
    ButtonVariant,
    PaginationBar,
    PaginationSize,
    PaginationState,
)
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
        self.pagination_state = PaginationState(page_size=10)
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

        self.btn_clear = Button(
            "✕ Clear",
            ButtonVariant.HOLLOW,
            ButtonSize.SM,
            on_click=self.cleared.emit,
        )
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
        self._pagination_bar = PaginationBar(
            self.pagination_state,
            size=PaginationSize.CARD,
            hide_when_single_page=True,
            margins=(2, 4, 2, 4),
        )
        self._pagination_bar.page_changed.connect(lambda _page: self._update_page())
        self.btn_prev = self._pagination_bar.prev_btn
        self.lbl_page = self._pagination_bar.label
        self.btn_next = self._pagination_bar.next_btn

        root.addWidget(self._pagination_bar)

        self._all_rows: list[tuple[str, str]] = []
        self._cards: list[GameCard] = []
        self._selected_index: int = -1
        self._header_template: str = ""

    def populate(self, rows: list[tuple[str, str]], header: str = ""):
        self._all_rows = rows
        self._header_template = header
        self.pagination_state.set_page(0)
        self._selected_index = -1
        self._update_page()

    def _update_page(self):
        # Clear old cards
        for card in self._cards:
            self._cards_layout.removeWidget(card)
            card.deleteLater()
        self._cards.clear()
        self.scroll.verticalScrollBar().setValue(0)

        self.pagination_state.set_total_items(len(self._all_rows))
        start_idx = self.pagination_state.start_index
        end_idx = self.pagination_state.end_index

        self._header.setText(self._header_template)
        self._header.setVisible(bool(self._header_template))

        # Add cards for current page
        for i in range(start_idx, end_idx):
            line1, line2 = self._all_rows[i]
            card = GameCard(i, line1, line2)
            card.selected.connect(self._on_card_selected)
            self._cards_layout.insertWidget(self._cards_layout.count() - 1, card)
            self._cards.append(card)

        self._pagination_bar.sync()

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

    def clear(self):
        self.populate([], "")
