"""Shared prev/next pagination bar for cards and list views."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QWidget

from src.gui.components.button import Button, ButtonSize, ButtonVariant
from src.gui.styles import Styles
from src.gui.theme import ThemeManager


class PaginationBar(QWidget):
    """``Prev | Page N of M | Next`` bar with test-friendly aliases."""

    prev_clicked = pyqtSignal()
    next_clicked = pyqtSignal()

    def __init__(
        self,
        page: int = 0,
        total_pages: int = 2,
        prev_text: str = "◀ Prev",
        next_text: str = "Next ▶",
        *,
        margins: tuple[int, int, int, int] = (4, 4, 4, 0),
        button_height: int | None = 26,
        label_font_size: int = 11,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._page = page
        self._total_pages = total_pages
        self._label_font_size = label_font_size

        layout = QHBoxLayout(self)
        layout.setContentsMargins(*margins)
        layout.setSpacing(10)

        self.prev_btn = Button(prev_text, ButtonVariant.FILLED, ButtonSize.SM)
        if button_height is not None:
            self.prev_btn.setFixedHeight(button_height)
        self.prev_btn.clicked.connect(lambda *_args: self.prev_clicked.emit())

        self.label = QLabel()
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.next_btn = Button(next_text, ButtonVariant.FILLED, ButtonSize.SM)
        if button_height is not None:
            self.next_btn.setFixedHeight(button_height)
        self.next_btn.clicked.connect(lambda *_args: self.next_clicked.emit())

        layout.addWidget(self.prev_btn)
        layout.addStretch()
        layout.addWidget(self.label)
        layout.addStretch()
        layout.addWidget(self.next_btn)

        # Compatibility aliases used by the cards and their tests.
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
        self.set_page(page, total_pages)

    @property
    def page(self) -> int:
        return self._page

    @property
    def total_pages(self) -> int:
        return self._total_pages

    def set_page(
        self,
        page: int,
        total_pages: int,
        total_items: int | None = None,
    ) -> None:
        self._total_pages = max(1, total_pages)
        self._page = max(0, min(page, self._total_pages - 1))

        text = f"Page {self._page + 1} of {self._total_pages}"
        if total_items is not None:
            text += f" ({total_items} total)"
        self.label.setText(text)

        self.prev_btn.setEnabled(self._page > 0)
        self.next_btn.setEnabled(self._page < self._total_pages - 1)

    def _on_theme_changed(self, *_args) -> None:
        self.refresh_styles()

    def refresh_styles(self) -> None:
        self.label.setStyleSheet(
            f"""
            color: {Styles.COLOR_TEXT_SECONDARY};
            font-size: {self._label_font_size}px;
            font-weight: 500;
            background: transparent;
            """
        )
        self.prev_btn.refresh_styles()
        self.next_btn.refresh_styles()
