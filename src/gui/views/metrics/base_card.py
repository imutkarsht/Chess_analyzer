from PyQt6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel
from src.gui.styles import Styles

class MetricCard(QFrame):
    def __init__(self, title, parent=None, max_height=None, min_height=None, action_widget=None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {Styles.COLOR_SURFACE};
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 12px;
            }}
            QFrame:hover {{
                border: 1px solid {Styles.COLOR_ACCENT};
            }}
        """)
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
            self.lbl_title.setStyleSheet(f"""
                color: {Styles.COLOR_TEXT_SECONDARY}; 
                font-size: 12px; 
                font-weight: 600; 
                letter-spacing: 0.5px;
                text-transform: uppercase;
                border: none; 
                background: transparent;
            """)
            header_layout.addWidget(self.lbl_title)
            header_layout.addStretch()
            if action_widget:
                header_layout.addWidget(action_widget)
            self.card_layout.addLayout(header_layout)

    def set_content(self, widget):
        self.card_layout.addWidget(widget)
