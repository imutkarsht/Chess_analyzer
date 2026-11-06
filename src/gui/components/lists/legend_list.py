"""Shared chart legend list for dashboard cards."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from src.gui.components.display.color_label import ColorLabel
from src.gui.components.display.icon_label import IconLabel
from src.gui.components.display.label import Label
from src.gui.components.display.rich_text import RichTextLabel
from src.gui.theme.typography import TextRole, TextTone


class LegendList(QWidget):
    """Vertical legend with an optional icon, label and colored value.

    Cards rebuild the legend when ``MetricCard.refresh_styles`` re-renders
    their content, so palette colours are captured per construction.
    """

    def __init__(self, spacing: int = 6, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")
        self._layout = QVBoxLayout(self)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self._layout.setSpacing(spacing)

    def add_row(
        self,
        label: str,
        value: str,
        color: str,
        pixmap: QPixmap | None = None,
    ) -> None:
        row = QHBoxLayout()
        row.setSpacing(8)

        if pixmap is not None and not pixmap.isNull():
            row.addWidget(IconLabel(pixmap, size=16))
        else:
            row.addWidget(
                ColorLabel(
                    "●",
                    color,
                    role=TextRole.BODY,
                    size=14,
                )
            )

        name_lbl = Label(
            label,
            role=TextRole.CAPTION,
            weight=500,
            tone=TextTone.SECONDARY,
        )
        row.addWidget(name_lbl)

        row.addStretch()

        row.addWidget(
            ColorLabel(
                value,
                color,
                role=TextRole.BODY,
                size=12,
                weight=700,
            )
        )

        self._layout.addLayout(row)

    def add_empty(self, text: str, italic: bool = False) -> None:
        if italic:
            label = RichTextLabel(
                f"<i>{text}</i>",
                role=TextRole.CAPTION,
                tone=TextTone.SECONDARY,
                wrap=True,
            )
        else:
            label = Label(
                text,
                role=TextRole.CAPTION,
                tone=TextTone.SECONDARY,
                wrap=True,
            )
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._layout.addWidget(label)
