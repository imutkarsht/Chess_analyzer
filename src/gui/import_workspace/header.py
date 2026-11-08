"""Header for the import workspace."""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QVBoxLayout, QWidget

from src.gui.components import (
    Button,
    ButtonSize,
    ButtonVariant,
    Label,
    StatusBadge,
    TextRole,
    TextTone,
)
from src.gui.styles import Styles


class ImportHeader(QFrame):
    """Back navigation, source summary, and batch counters."""

    back_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("ImportHeader")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(24, 14, 24, 14)
        layout.setSpacing(12)

        self.btn_back = Button(
            "Back to History",
            ButtonVariant.HOLLOW,
            ButtonSize.SM,
            icon="fa5s.arrow-left",
            on_click=self.back_requested.emit,
        )
        layout.addWidget(self.btn_back)

        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        self.lbl_title = Label(
            "Import games", role=TextRole.DIALOG_TITLE, weight=700
        )
        self.lbl_subtitle = Label(
            "", role=TextRole.CAPTION, tone=TextTone.SECONDARY
        )
        title_box.addWidget(self.lbl_title)
        title_box.addWidget(self.lbl_subtitle)
        layout.addLayout(title_box, 1)

        self.badge_count = StatusBadge(
            "0 games",
            TextTone.ACCENT,
            variant="quiet",
            font_size=11,
            weight=700,
            padding="4px 10px",
            radius=10,
        )
        self.badge_saved = StatusBadge(
            "0 in history",
            TextTone.SECONDARY,
            variant="quiet",
            font_size=11,
            weight=600,
            padding="4px 10px",
            radius=10,
        )
        layout.addWidget(self.badge_count)
        layout.addWidget(self.badge_saved)
        self.refresh_styles()

    def set_batch_info(self, label: str, count: int, saved: int) -> None:
        self.lbl_subtitle.setText(label)
        self.badge_count.setText(
            f"{count} game" if count == 1 else f"{count} games"
        )
        self.badge_saved.setText(
            "1 in history" if saved == 1 else f"{saved} in history"
        )

    def reset(self) -> None:
        self.lbl_subtitle.setText("")
        self.badge_count.setText("0 games")
        self.badge_saved.setText("0 in history")

    def refresh_styles(self) -> None:
        self.setStyleSheet(
            Styles.get_header_bar_ext_style(Styles.COLOR_BACKGROUND)
        )
        self.btn_back.refresh_styles()
