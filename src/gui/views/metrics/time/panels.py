"""Shared building blocks for the Time & Clock Analytics card."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from src.gui.styles import Styles


def make_icon_pixmap(icon_name: str, color: str, size: int) -> QPixmap | None:
    """Return a qtawesome pixmap, or ``None`` when the icon pack is absent."""
    try:
        import qtawesome as qta

        return qta.icon(icon_name, color=color).pixmap(size, size)
    except Exception:
        return None


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

        pixmap = make_icon_pixmap(icon_name, color, icon_size)
        if pixmap is not None:
            icon_lbl = QLabel()
            icon_lbl.setPixmap(pixmap)
            icon_lbl.setStyleSheet("border: none; background: transparent;")
            layout.addWidget(icon_lbl)


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
        title_color: str = Styles.COLOR_TEXT_PRIMARY,
        title_size: int = 12,
        title_weight: int = 700,
        value_color: str = Styles.COLOR_TEXT_PRIMARY,
        value_size: int = 24,
        description_color: str = Styles.COLOR_TEXT_SECONDARY,
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
                pixmap = make_icon_pixmap(icon_name, icon_color, 14)
                if pixmap is not None:
                    icon_lbl = QLabel()
                    icon_lbl.setPixmap(pixmap)
                    icon_lbl.setStyleSheet("border: none; background: transparent;")
                    top.addWidget(icon_lbl)
            title_lbl = self._title_label(title, title_color, title_size, title_weight)
            top.addWidget(title_lbl)
            top.addStretch()
            if threshold is not None:
                thresh_lbl = QLabel(threshold)
                thresh_lbl.setStyleSheet(
                    f"color: {Styles.COLOR_TEXT_MUTED}; font-size: 9px; "
                    "border: none; background: transparent;"
                )
                top.addWidget(thresh_lbl)
            layout.addLayout(top)
        else:
            layout.addWidget(self._title_label(title, title_color, title_size, title_weight))

        value_lbl = QLabel(value)
        value_lbl.setStyleSheet(
            f"color: {value_color}; font-size: {value_size}px; font-weight: 800; "
            "border: none; background: transparent; padding: 0;"
        )
        layout.addWidget(value_lbl)

        desc_lbl = QLabel(description)
        desc_lbl.setStyleSheet(
            f"color: {description_color}; font-size: 10px; "
            "border: none; background: transparent; padding: 0;"
        )
        layout.addWidget(desc_lbl)

    @staticmethod
    def _title_label(text: str, color: str, size: int, weight: int) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet(
            f"color: {color}; font-weight: {weight}; font-size: {size}px; "
            "border: none; background: transparent; padding: 0;"
        )
        return label


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

        title = QLabel("No Clock Timestamps Recorded")
        title.setStyleSheet(
            f"color: {Styles.COLOR_TEXT_PRIMARY}; font-size: 14px; font-weight: 700;"
        )
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        desc = QLabel(
            f"{note}\nGames imported from Chess.com or Lichess automatically include clock comments.\n"
            "View the 'Formats' tab for win rates and accuracy by time control."
        )
        desc.setStyleSheet(
            f"color: {Styles.COLOR_TEXT_SECONDARY}; font-size: 12px; line-height: 1.4;"
        )
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(desc)
