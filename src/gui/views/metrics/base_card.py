from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout

from src.gui.styles import Styles


class MetricCard(QFrame):
    def __init__(self, title, parent=None, max_height=None, min_height=None, action_widget=None):
        super().__init__(parent)
        self.setObjectName("MetricCard")
        self.setProperty("metric_card", "true")
        self._apply_theme()

        if max_height is not None:
            self.setMaximumHeight(max_height)
        if min_height is not None:
            self.setMinimumHeight(min_height)

        self.card_layout = QVBoxLayout(self)
        self.card_layout.setContentsMargins(24, 20, 24, 20)
        self.card_layout.setSpacing(16)

        if title:
            header_layout = QHBoxLayout()
            self.lbl_title = QLabel(title)
            self.lbl_title.setStyleSheet(Styles.get_card_title_style())
            header_layout.addWidget(self.lbl_title)
            header_layout.addStretch()
            if action_widget:
                header_layout.addWidget(action_widget, alignment=Qt.AlignmentFlag.AlignVCenter)
            self.card_layout.addLayout(header_layout)

    def _apply_theme(self):
        self.setStyleSheet(f"""
            QFrame#MetricCard, QFrame[metric_card="true"] {{
                background-color: {Styles.COLOR_SURFACE};
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 12px;
            }}
            QFrame#MetricCard:hover, QFrame[metric_card="true"]:hover {{
                border: 1px solid {Styles.COLOR_ACCENT};
            }}
            QFrame#MetricCard QWidget, QFrame[metric_card="true"] QWidget {{
                background-color: transparent;
            }}
        """)

    def refresh_styles(self):
        self._apply_theme()
        if hasattr(self, "lbl_title"):
            self.lbl_title.setStyleSheet(Styles.get_card_title_style())

    def set_content(self, widget):
        widget.setStyleSheet("background: transparent;")
        self.card_layout.addWidget(widget, stretch=1)
