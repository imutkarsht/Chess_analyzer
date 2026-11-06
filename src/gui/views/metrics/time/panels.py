"""Shared building blocks for the Time & Clock Analytics card."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QVBoxLayout, QWidget

from src.gui.components import IconLabel, Label, TextRole, TextTone
from src.gui.styles import Styles


class IconTile(QFrame):
    """Small rounded tile holding a single monochrome icon."""

    def __init__(
        self,
        icon_name: str,
        *,
        size: int = 32,
        icon_size: int = 16,
        color: str = Styles.COLOR_TEXT_SECONDARY,
        radius: int = 6,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setFixedSize(size, size)
        self.setStyleSheet(
            f"background-color: {Styles.COLOR_SURFACE}; "
            f"border: 1px solid {Styles.COLOR_BORDER}; border-radius: {radius}px;"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        pixmap = IconLabel(icon_name, size=icon_size, color=color)
        layout.addWidget(pixmap)


class StatPanel(QFrame):
    """Panel with an optional icon/threshold, a hero value and a description."""

    def __init__(
        self,
        *,
        object_name: str,
        title: str,
        value: str,
        description: str,
        icon_name: str | None = None,
        icon_color: str = Styles.COLOR_TEXT_SECONDARY,
        threshold: str | None = None,
        title_tone: TextTone = TextTone.PRIMARY,
        title_size: int = 12,
        title_weight: int = 700,
        value_tone: TextTone = TextTone.PRIMARY,
        value_size: int = 24,
        description_tone: TextTone = TextTone.SECONDARY,
        background: str = Styles.COLOR_SURFACE_LIGHT,
        border_color: str = Styles.COLOR_BORDER,
        radius: int = 8,
        padding: str = "10px",
        content_margins: tuple[int, int, int, int] = (6, 4, 6, 4),
        spacing: int = 4,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName(object_name)
        self.setStyleSheet(
            f"""
            QFrame#{object_name} {{
                background-color: {background};
                border: 1px solid {border_color};
                border-radius: {radius}px;
                padding: {padding};
            }}
            """
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(*content_margins)
        layout.setSpacing(spacing)

        if icon_name is not None or threshold is not None:
            top = QHBoxLayout()
            top.setSpacing(6)
            if icon_name is not None:
                top.addWidget(
                    IconLabel(icon_name, size=14, color=icon_color)
                )
            title_lbl = self._title_label(title, title_tone, title_size, title_weight)
            top.addWidget(title_lbl)
            top.addStretch()
            if threshold is not None:
                thresh_lbl = Label(
                    threshold,
                    role=TextRole.MICRO,
                    size=9,
                    tone=TextTone.MUTED,
                )
                top.addWidget(thresh_lbl)
            layout.addLayout(top)
        else:
            layout.addWidget(
                self._title_label(title, title_tone, title_size, title_weight)
            )

        value_lbl = Label(
            value,
            role=TextRole.BODY,
            tone=value_tone,
            size=value_size,
            weight=800,
        )
        layout.addWidget(value_lbl)

        desc_lbl = Label(
            description,
            role=TextRole.MICRO,
            size=10,
            tone=description_tone,
        )
        layout.addWidget(desc_lbl)

    @staticmethod
    def _title_label(
        text: str,
        tone: TextTone,
        size: int,
        weight: int,
    ) -> Label:
        return Label(
            text,
            role=TextRole.BODY,
            tone=tone,
            size=size,
            weight=weight,
        )


class NoClockBanner(QFrame):
    """Explains why a clock-dependent view has no data."""

    def __init__(self, note: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setStyleSheet(
            f"""
            background-color: {Styles.COLOR_SURFACE_LIGHT};
            border: 1px dashed {Styles.COLOR_BORDER};
            border-radius: 8px;
            padding: 24px;
            """
        )
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(8)

        title = Label(
            "No Clock Timestamps Recorded",
            role=TextRole.BODY_LARGE,
            weight=700,
        )
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        desc = Label(
            f"{note}\nGames imported from Chess.com or Lichess automatically include clock comments.\n"
            "View the 'Formats' tab for win rates and accuracy by time control.",
            role=TextRole.CAPTION,
            tone=TextTone.SECONDARY,
            wrap=True,
        )
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(desc)
