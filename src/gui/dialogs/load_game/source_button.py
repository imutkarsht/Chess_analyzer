"""
Source button component for the Load Game dialog.
"""
import os
from PyQt6.QtWidgets import QPushButton, QHBoxLayout, QLabel, QSizePolicy
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from ...styles import Styles

class SourceBtn(QPushButton):
    def __init__(self, emoji: str | None, label: str,
                 icon_path: str | None = None, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(54)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 0, 14, 0)
        layout.setSpacing(10)

        # Icon: prefer brand image, fall back to emoji
        if icon_path and os.path.exists(icon_path):
            lbl_icon = QLabel()
            pix = QPixmap(icon_path).scaled(
                22, 22,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            lbl_icon.setPixmap(pix)
            lbl_icon.setFixedSize(22, 22)
        else:
            lbl_icon = QLabel(emoji or "")
            lbl_icon.setStyleSheet("font-size: 18px; background: transparent; border: none;")

        lbl_icon.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout.addWidget(lbl_icon)

        lbl_text = QLabel(label)
        lbl_text.setStyleSheet(
            f"font-size: 14px; font-weight: 600; color: {Styles.COLOR_TEXT_PRIMARY};"
            " background: transparent; border: none;"
        )
        lbl_text.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout.addWidget(lbl_text)
        layout.addStretch()

        self._apply_style(False)

    def _apply_style(self, checked: bool):
        if checked:
            self.setStyleSheet(f"""
                QPushButton {{
                    background-color: {Styles.COLOR_ACCENT_SUBTLE};
                    border: none;
                    border-left: 3px solid {Styles.COLOR_ACCENT};
                    border-radius: 8px;
                    text-align: left;
                }}
            """)
        else:
            self.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent;
                    border: none;
                    border-left: 3px solid transparent;
                    border-radius: 8px;
                    text-align: left;
                }}
                QPushButton:hover {{
                    background-color: {Styles.COLOR_SURFACE_LIGHT};
                }}
            """)

    def setChecked(self, checked: bool):
        super().setChecked(checked)
        self._apply_style(checked)

    def refresh_styles(self):
        self._apply_style(self.isChecked())
