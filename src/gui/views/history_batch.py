# SPDX-License-Identifier: GPL-3.0-only
"""History widgets for the batch-analysis workflow."""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QFrame, QHBoxLayout

from src.gui.components import (
    Button,
    ButtonSize,
    ButtonVariant,
    Label,
    TextRole,
)
from src.gui.styles import Styles


class BatchSelectionBar(QFrame):
    """Selection count and page/clear actions shown in History bulk mode."""

    select_page_requested = pyqtSignal()
    clear_requested = pyqtSignal()
    exit_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("BatchSelectionBar")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 8, 14, 8)
        layout.setSpacing(10)

        self.count_label = Label("0 selected", role=TextRole.BODY_STRONG, weight=600)
        layout.addWidget(self.count_label)
        layout.addStretch()

        self.btn_select_page = Button(
            "Select page",
            ButtonVariant.HOLLOW,
            ButtonSize.SM,
            on_click=lambda: self.select_page_requested.emit(),
        )
        self.btn_select_page.setAccessibleName("Select games on this page")
        layout.addWidget(self.btn_select_page)

        self.btn_clear = Button(
            "Clear selection",
            ButtonVariant.LINK,
            ButtonSize.SM,
            on_click=lambda: self.clear_requested.emit(),
        )
        self.btn_clear.setAccessibleName("Clear batch selection")
        layout.addWidget(self.btn_clear)

        self.btn_exit = Button(
            "Exit selection",
            ButtonVariant.LINK,
            ButtonSize.SM,
            on_click=lambda: self.exit_requested.emit(),
        )
        self.btn_exit.setAccessibleName("Exit batch selection mode")
        layout.addWidget(self.btn_exit)

        self.set_count(0)
        self.refresh_styles()

    def set_count(self, count: int) -> None:
        count = max(0, int(count))
        self.count_label.setText(f"{count:,} selected")
        self.btn_clear.setEnabled(count > 0)

    def set_page_available(self, available: bool) -> None:
        self.btn_select_page.setEnabled(bool(available))

    def refresh_styles(self) -> None:
        self.setStyleSheet(Styles.get_batch_selection_bar_style())
        self.btn_select_page.refresh_styles()
        self.btn_clear.refresh_styles()
        self.btn_exit.refresh_styles()
