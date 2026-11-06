"""
Shared StatCard component for dashboard widgets.
"""

import os

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout

from src.gui.styles import Styles
from src.gui.theme import ThemeManager
from src.gui.theme.typography import TextRole, TextTone
from src.gui.utils.gui_utils import resolve_asset  # Use shared utility

from .label import Label


class StatCard(QFrame):
    """
    A reusable stat card for dashboards, showing title, value, optional subtitle and icon.

    Args:
        title: Header text for the card
        value: Main display value
        subtitle: Optional secondary text below the value
        icon: Optional icon name (without extension) to display
        color: Optional color for the value text
        clickable: Optional boolean to enable pointing cursor and click interactions
    """

    clicked = pyqtSignal()

    def __init__(self, title, value, subtitle=None, icon=None, color=None, clickable=False):
        super().__init__()

        self.clickable = clickable
        if clickable:
            self.setCursor(Qt.CursorShape.PointingHandCursor)

        self.setObjectName("StatCard")
        # Modern card styling with subtle gradient
        self.setStyleSheet(f"""
            QFrame#StatCard {{
                background-color: {Styles.COLOR_SURFACE};
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 12px;
            }}
            QFrame#StatCard:hover {{
                border: 1px solid {Styles.COLOR_ACCENT};
                background-color: {Styles.COLOR_SURFACE_LIGHT};
            }}
            QFrame#StatCard QLabel {{
                border: none;
                background: transparent;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(8)

        # Header (Title + Icon)
        header_layout = QHBoxLayout()

        self.lbl_title = Label(title, role=TextRole.CARD_TITLE)
        header_layout.addWidget(self.lbl_title)

        if icon:
            self._add_icon(header_layout, icon)
        else:
            header_layout.addStretch()

        layout.addLayout(header_layout)
        layout.addSpacing(4)

        # Value - Large, bold, eye-catching
        value_tone = TextTone.PRIMARY
        if color == Styles.COLOR_ACCENT:
            value_tone = TextTone.ACCENT
        elif color == Styles.COLOR_BEST:
            value_tone = TextTone.BEST
        elif color == Styles.COLOR_BLUNDER:
            value_tone = TextTone.BLUNDER
        elif color == Styles.COLOR_MISTAKE:
            value_tone = TextTone.MISTAKE
        elif color == Styles.COLOR_TEXT_SECONDARY:
            value_tone = TextTone.SECONDARY
        elif color == Styles.COLOR_TEXT_MUTED:
            value_tone = TextTone.MUTED

        self.lbl_value = Label(
            str(value),
            role=TextRole.STAT_LARGE,
            tone=value_tone,
        )
        layout.addWidget(self.lbl_value)

        # Subtitle - Subtle, informative
        self.lbl_sub = None
        if subtitle:
            self.lbl_sub = Label(
                subtitle,
                role=TextRole.BODY,
                weight=500,
                tone=TextTone.SECONDARY,
                wrap=True,
            )
            layout.addWidget(self.lbl_sub)

        ThemeManager.apply_elevation(self, elevation=1)

    def refresh_styles(self):
        """Re-apply styles with the updated accent color."""
        self.setStyleSheet(f"""
            QFrame#StatCard {{
                background-color: {Styles.COLOR_SURFACE};
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 12px;
            }}
            QFrame#StatCard:hover {{
                border: 1px solid {Styles.COLOR_ACCENT};
                background-color: {Styles.COLOR_SURFACE_LIGHT};
            }}
            QFrame#StatCard QLabel {{
                border: none;
                background: transparent;
            }}
        """)

    def _add_icon(self, layout, icon):
        """Add icon to the header layout."""
        # Try to find icon file
        if not icon.endswith((".png", ".svg")):
            icon_path = resolve_asset(f"{icon}.svg")
            if not icon_path:
                icon_path = resolve_asset(f"{icon}.png")
        else:
            icon_path = resolve_asset(icon)

        layout.addStretch()

        if icon_path and os.path.exists(icon_path):
            lbl_icon = QLabel()
            pixmap = QPixmap(icon_path)
            if not pixmap.isNull():
                pixmap = pixmap.scaled(
                    48,
                    48,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                lbl_icon.setPixmap(pixmap)
                lbl_icon.setStyleSheet(Styles.get_transparent_style())
                layout.addWidget(lbl_icon)
                return

        # Fallback: show icon name as text
        lbl = QLabel(icon)
        lbl.setStyleSheet(
            f"color: {Styles.COLOR_ACCENT}; font-size: 16px; {Styles.get_transparent_style()}"
        )
        layout.addWidget(lbl)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class SimpleStatCard(QFrame):
    """
    A simpler stat card variant for compact displays (e.g., analysis report).

    Args:
        title: Header text
        value: Display value
        color: Optional value color
    """

    def __init__(self, title, value, color=None):
        super().__init__()

        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {Styles.COLOR_SURFACE};
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 8px;
                padding: 10px;
            }}
            QLabel {{ border: none; background: transparent; }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        self.lbl_title = Label(title, role=TextRole.CAPTION, tone=TextTone.SECONDARY)
        self.lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        value_tone = TextTone.PRIMARY
        if color == Styles.COLOR_ACCENT:
            value_tone = TextTone.ACCENT
        elif color == Styles.COLOR_BEST:
            value_tone = TextTone.BEST
        elif color == Styles.COLOR_BLUNDER:
            value_tone = TextTone.BLUNDER
        elif color == Styles.COLOR_MISTAKE:
            value_tone = TextTone.MISTAKE

        self.lbl_value = Label(
            str(value),
            role=TextRole.BODY,
            size=18,
            weight=700,
            tone=value_tone,
        )
        self.lbl_value.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(self.lbl_title)
        layout.addWidget(self.lbl_value)

        ThemeManager.apply_elevation(self, elevation=1)

    def refresh_styles(self):
        """Re-apply styles with the updated accent color."""
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {Styles.COLOR_SURFACE};
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 8px;
                padding: 10px;
            }}
            QLabel {{ border: none; background: transparent; }}
        """)
