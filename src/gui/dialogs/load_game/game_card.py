"""
Game card component for the Load Game dialog.
"""
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QFrame, QSizePolicy, QVBoxLayout

from ...components import Label, TextRole, TextTone
from ...styles import Styles


class GameCard(QFrame):
    """Single selectable game row inside the inline game list."""
    selected = pyqtSignal(int)   # emits its own index

    def __init__(self, index: int, line1: str, line2: str, parent=None):
        super().__init__(parent)
        self._index = index
        self._is_selected = False
        self.setObjectName("GameCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(62)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(3)

        self._lbl1 = Label(line1, role=TextRole.CAPTION, weight=600)
        layout.addWidget(self._lbl1)

        self._lbl2 = Label(line2, role=TextRole.CAPTION, tone=TextTone.SECONDARY)
        layout.addWidget(self._lbl2)

        self._apply_style(False)

    def _apply_style(self, selected: bool):
        if selected:
            self.setStyleSheet(f"""
                QFrame#GameCard {{
                    background-color: {Styles.COLOR_ACCENT_SUBTLE};
                    border: 1px solid {Styles.COLOR_ACCENT};
                    border-radius: 8px;
                }}
                QFrame#GameCard QLabel {{
                    background: transparent;
                    border: none;
                }}
            """)
        else:
            self.setStyleSheet(f"""
                QFrame#GameCard {{
                    background-color: {Styles.COLOR_SURFACE};
                    border: 1px solid {Styles.COLOR_BORDER};
                    border-radius: 8px;
                }}
                QFrame#GameCard QLabel {{
                    background: transparent;
                    border: none;
                }}
                QFrame#GameCard:hover {{
                    background-color: {Styles.COLOR_SURFACE_LIGHT};
                    border: 1px solid {Styles.COLOR_BORDER_LIGHT};
                }}
            """)

    def set_selected(self, selected: bool):
        self._is_selected = selected
        self._apply_style(selected)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.selected.emit(self._index)
