"""Central pagination model and bar for every paginated surface.

``PaginationState`` owns the page window (size, totals, clamping, slicing).
``PaginationBar`` renders it in one of two looks and is the only place that
knows how to draw pagination controls or page-number buttons.
"""

from __future__ import annotations

from enum import StrEnum
from math import ceil
from typing import TypeVar

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QWidget

from src.gui.components.controls.button import Button, ButtonSize, ButtonVariant
from src.gui.styles import Styles
from src.gui.theme import ThemeManager

T = TypeVar("T")


class PaginationStyle(StrEnum):
    """Visual layout of the bar."""

    SIMPLE = "simple"
    NUMBERED = "numbered"


class PaginationSize(StrEnum):
    """Spacing scale for the surface the bar sits on."""

    CARD = "card"
    PAGE = "page"


class PaginationState:
    """A clamped page window over a flat item list.

    Every mutator keeps ``page`` inside ``0..total_pages-1`` and never emits
    signals; the bar is the only thing that reacts to user interaction.
    """

    def __init__(self, page_size: int = 10, total_items: int = 0) -> None:
        self._page_size = max(1, int(page_size))
        self._total_items = max(0, int(total_items))
        self._page = 0

    @property
    def page(self) -> int:
        return self._page

    @property
    def page_size(self) -> int:
        return self._page_size

    @property
    def total_items(self) -> int:
        return self._total_items

    @property
    def total_pages(self) -> int:
        return max(1, ceil(self._total_items / self._page_size))

    @property
    def has_prev(self) -> bool:
        return self._page > 0

    @property
    def has_next(self) -> bool:
        return self._page < self.total_pages - 1

    @property
    def start_index(self) -> int:
        return self._page * self._page_size

    @property
    def end_index(self) -> int:
        return min(self.start_index + self._page_size, self._total_items)

    def set_total_items(self, total_items: int) -> None:
        self._total_items = max(0, int(total_items))
        self._page = min(self._page, self.total_pages - 1)

    def set_page_size(self, page_size: int) -> None:
        self._page_size = max(1, int(page_size))
        self._page = min(self._page, self.total_pages - 1)

    def set_page(self, page: int) -> bool:
        """Jump to ``page`` (clamped). Returns True when the page changed."""
        target = max(0, min(int(page), self.total_pages - 1))
        changed = target != self._page
        self._page = target
        return changed

    def previous(self) -> bool:
        return self.set_page(self._page - 1)

    def next(self) -> bool:
        return self.set_page(self._page + 1)

    def slice(self, items: list[T]) -> list[T]:
        return items[self.start_index : self.end_index]

    def range_text(self, empty_text: str = "No items") -> str:
        if self._total_items <= 0:
            return empty_text
        return f"{self.start_index + 1}–{self.end_index} of {self._total_items}"

    def page_text(self, *, include_total: bool = False) -> str:
        text = f"Page {self._page + 1} of {self.total_pages}"
        if include_total:
            text += f" ({self._total_items} total)"
        return text


class PaginationBar(QWidget):
    """``Prev | page label | Next`` bar, optionally with numbered pages.

    The bar owns a :class:`PaginationState`. User interaction mutates it and
    emits ``page_changed``; programmatic ``set_*`` calls only re-render.
    """

    page_changed = pyqtSignal(int)
    prev_clicked = pyqtSignal()
    next_clicked = pyqtSignal()

    def __init__(
        self,
        state: PaginationState | None = None,
        *,
        style: PaginationStyle = PaginationStyle.SIMPLE,
        size: PaginationSize = PaginationSize.CARD,
        page: int = 0,
        total_pages: int = 1,
        prev_text: str = "‹ Prev",
        next_text: str = "Next ›",
        margins: tuple[int, int, int, int] | None = None,
        button_height: int | None = None,
        label_font_size: int | None = None,
        framed: bool = False,
        hide_when_single_page: bool = False,
        show_range: bool | None = None,
        show_total: bool = False,
        empty_text: str = "No items",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("PaginationBar")

        if state is None:
            state = PaginationState(page_size=1, total_items=max(1, total_pages))
            state.set_page(page)
        self.state = state

        self._style = style
        self._size = size
        self._framed = framed
        self._hide_when_single_page = hide_when_single_page
        self._show_range = style is PaginationStyle.NUMBERED if show_range is None else show_range
        self._show_total = show_total
        self._empty_text = empty_text
        self._label_font_size = label_font_size or (12 if size is PaginationSize.PAGE else 11)
        self._button_height = button_height or (30 if size is PaginationSize.PAGE else 26)

        if margins is None:
            margins = (24, 10, 24, 10) if size is PaginationSize.PAGE else (4, 4, 4, 0)

        self.label = QLabel()
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.prev_btn = Button(prev_text, ButtonVariant.FILLED, ButtonSize.SM)
        self.prev_btn.setFixedHeight(self._button_height)
        self.prev_btn.setAccessibleName("Previous page")
        self.prev_btn.clicked.connect(self._on_prev_clicked)

        self.next_btn = Button(next_text, ButtonVariant.FILLED, ButtonSize.SM)
        self.next_btn.setFixedHeight(self._button_height)
        self.next_btn.setAccessibleName("Next page")
        self.next_btn.clicked.connect(self._on_next_clicked)

        self._numbers_widget = QWidget()
        self._numbers_layout = QHBoxLayout(self._numbers_widget)
        self._numbers_layout.setContentsMargins(0, 0, 0, 0)
        self._numbers_layout.setSpacing(4)
        self._numbers_widget.setVisible(style is PaginationStyle.NUMBERED)
        self._number_tokens: list[int | None] = []
        self._number_buttons: dict[int, Button] = {}

        layout = QHBoxLayout(self)
        layout.setContentsMargins(*margins)
        layout.setSpacing(10)

        if style is PaginationStyle.NUMBERED:
            # Range on the left, then the page controls.
            layout.addWidget(self.label)
            layout.addStretch(1)
            layout.addWidget(self.prev_btn)
            layout.addWidget(self._numbers_widget)
            layout.addWidget(self.next_btn)
        else:
            layout.addWidget(self.prev_btn)
            layout.addStretch(1)
            layout.addWidget(self.label)
            layout.addStretch(1)
            layout.addWidget(self.next_btn)

        # Compatibility aliases used by cards, views, and their tests.
        self.btn_prev = self.prev_btn
        self.btn_next = self.next_btn
        self.lbl_page = self.label
        self.btn_prev_page = self.prev_btn
        self.btn_next_page = self.next_btn
        self.lbl_page_info = self.label

        theme_manager = ThemeManager.instance()
        theme_manager.theme_changed.connect(self._on_theme_changed)
        theme_manager.accent_changed.connect(self._on_theme_changed)
        self.refresh_styles()
        self.sync()

    # ------------------------------------------------------------------
    # State touch points
    # ------------------------------------------------------------------
    @property
    def page(self) -> int:
        return self.state.page

    @property
    def total_pages(self) -> int:
        return self.state.total_pages

    def visible_items(self, items: list[T]) -> list[T]:
        return self.state.slice(items)

    def set_total_items(self, total_items: int) -> None:
        self.state.set_total_items(total_items)
        self.sync()

    def set_page_size(self, page_size: int) -> None:
        self.state.set_page_size(page_size)
        self.sync()

    def set_page(
        self,
        page: int,
        total_pages: int | None = None,
        total_items: int | None = None,
    ) -> None:
        """Programmatic page update (compatibility with the old API)."""
        if total_items is not None:
            self.state.set_total_items(total_items)
        elif total_pages is not None:
            self.state.set_total_items(max(1, total_pages) * self.state.page_size)
        self.state.set_page(page)
        self.sync()

    def sync(self) -> None:
        """Re-render the label, buttons, page numbers, and visibility."""
        if self._show_range:
            self.label.setText(self.state.range_text(self._empty_text))
        else:
            self.label.setText(self.state.page_text(include_total=self._show_total))

        self.prev_btn.setEnabled(self.state.has_prev)
        self.next_btn.setEnabled(self.state.has_next)

        if self._style is PaginationStyle.NUMBERED:
            self._rebuild_numbers()

        should_show = not self._hide_when_single_page or self.state.total_pages > 1
        if should_show and self.parentWidget() is None:
            # Showing a parentless widget promotes it to a top-level window.
            # That steals focus (and can drop a fullscreen app out of its
            # space), so let the adopting layout show the bar instead.
            return
        self.setVisible(should_show)

    # ------------------------------------------------------------------
    # Interaction
    # ------------------------------------------------------------------
    def _on_prev_clicked(self) -> None:
        self.prev_clicked.emit()
        if self.state.previous():
            self.sync()
            self.page_changed.emit(self.state.page)

    def _on_next_clicked(self) -> None:
        self.next_clicked.emit()
        if self.state.next():
            self.sync()
            self.page_changed.emit(self.state.page)

    def _go_to_page(self, page: int) -> None:
        if self.state.set_page(page):
            self.sync()
            self.page_changed.emit(self.state.page)

    # ------------------------------------------------------------------
    # Numbered mode
    # ------------------------------------------------------------------
    def _desired_numbers(self) -> list[int | None]:
        """Page numbers and ``None`` ellipsis markers for the current window."""
        total = self.state.total_pages
        current = self.state.page
        window = 2
        low = max(0, current - window)
        high = min(total - 1, current + window)

        tokens: list[int | None] = []
        if low > 0:
            tokens.append(0)
            if low > 1:
                tokens.append(None)
        tokens.extend(range(low, high + 1))
        if high < total - 1:
            if high < total - 2:
                tokens.append(None)
            tokens.append(total - 1)
        return tokens

    def _rebuild_numbers(self) -> None:
        tokens = self._desired_numbers()
        current = self.state.page

        if tokens == self._number_tokens:
            # Reuse the existing buttons. Destroying the clicked button inside
            # its own handler makes macOS drop keyboard focus and switch away
            # from a fullscreen window.
            for page, button in self._number_buttons.items():
                button.set_variant(
                    ButtonVariant.PRIMARY if page == current else ButtonVariant.FILLED
                )
            return

        had_focus = self._numbers_widget.focusWidget() is not None

        while self._numbers_layout.count():
            item = self._numbers_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                # Hide before detaching: a visible widget promoted to a
                # top-level window can steal focus on macOS.
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()

        self._number_buttons.clear()
        for token in tokens:
            if token is None:
                self._numbers_layout.addWidget(self._make_ellipsis())
            else:
                button = self._make_number_button(token)
                self._number_buttons[token] = button
                self._numbers_layout.addWidget(button)
        self._number_tokens = tokens

        if had_focus and current in self._number_buttons:
            self._number_buttons[current].setFocus()

    def _make_number_button(self, page: int) -> Button:
        button = Button(
            str(page + 1),
            ButtonVariant.PRIMARY if page == self.state.page else ButtonVariant.FILLED,
            ButtonSize.SM,
            on_click=lambda _checked=False, p=page: self._go_to_page(p),
        )
        button.setFixedSize(self._button_height, self._button_height)
        button.setAccessibleName(f"Page {page + 1}")
        return button

    @staticmethod
    def _make_ellipsis() -> QLabel:
        label = QLabel("…")
        label.setFixedSize(20, 30)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet(
            Styles.get_label_style(size=13, color=Styles.COLOR_TEXT_MUTED)
            + " "
            + Styles.get_transparent_label_style()
        )
        return label

    # ------------------------------------------------------------------
    # Styling
    # ------------------------------------------------------------------
    def _on_theme_changed(self, *_args) -> None:
        self.refresh_styles()

    def refresh_styles(self) -> None:
        self.setStyleSheet(
            Styles.get_pagination_bar_style() if self._framed else "background: transparent;"
        )
        self.label.setStyleSheet(
            Styles.get_label_style(
                size=self._label_font_size,
                color=Styles.COLOR_TEXT_SECONDARY,
                weight=500,
            )
            + " "
            + Styles.get_transparent_label_style()
        )
        self.prev_btn.refresh_styles()
        self.next_btn.refresh_styles()
