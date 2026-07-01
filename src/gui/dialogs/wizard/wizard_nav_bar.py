from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton
from src.gui.styles import Styles


class WizardNavBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(52)
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {Styles.COLOR_SURFACE};
                border-top: 1px solid {Styles.COLOR_BORDER};
            }}
        """)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 8)

        self.dots_widget = QWidget()
        self.dots_widget.setStyleSheet("background: transparent;")
        self.dots_layout = QHBoxLayout(self.dots_widget)
        self.dots_layout.setContentsMargins(0, 0, 0, 0)
        self.dots_layout.setSpacing(6)
        self.dot_labels = []
        for i in range(6):
            dot = QLabel("o")
            dot.setStyleSheet(
                f"color: {Styles.COLOR_TEXT_MUTED}; font-size: 10px; background: transparent;"
            )
            self.dot_labels.append(dot)
            self.dots_layout.addWidget(dot)
        layout.addWidget(self.dots_widget)

        layout.addStretch()

        self.skip_btn = QPushButton("Skip")
        self.skip_btn.setFlat(True)
        self.skip_btn.setStyleSheet(f"""
            QPushButton {{ color: {Styles.COLOR_TEXT_SECONDARY}; font-size: 13px; border: none; background: transparent; }}
            QPushButton:hover {{ color: {Styles.COLOR_TEXT_PRIMARY}; }}
        """)
        layout.addWidget(self.skip_btn)

        self.back_btn = QPushButton("Back")
        self.back_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Styles.COLOR_SURFACE_LIGHT};
                color: {Styles.COLOR_TEXT_PRIMARY};
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 6px;
                padding: 6px 18px;
                font-size: 13px;
            }}
            QPushButton:hover {{ border: 1px solid {Styles.COLOR_ACCENT}; }}
        """)
        layout.addWidget(self.back_btn)

        self.next_btn = QPushButton("Next")
        self.next_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Styles.COLOR_ACCENT};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 6px 24px;
                font-size: 13px;
                font-weight: bold;
            }}
            QPushButton:hover {{ background-color: {Styles.COLOR_ACCENT_HOVER}; }}
        """)
        layout.addWidget(self.next_btn)

    def update(self, index: int, total: int = 6):
        for i, dot in enumerate(self.dot_labels):
            if i == index:
                dot.setStyleSheet(
                    f"color: {Styles.COLOR_ACCENT}; font-size: 10px; background: transparent;"
                )
            elif i < index:
                dot.setStyleSheet(
                    f"color: {Styles.COLOR_TEXT_SECONDARY}; font-size: 10px; background: transparent;"
                )
            else:
                dot.setStyleSheet(
                    f"color: {Styles.COLOR_TEXT_MUTED}; font-size: 10px; background: transparent;"
                )

        is_last = index == total - 1
        is_first = index <= 1
        is_gatekeeper = index == 0

        self.back_btn.setVisible(not is_first and not is_gatekeeper)
        self.skip_btn.setVisible(index == 4)
        self.next_btn.setText("Finish" if is_last else "Next")
        self.next_btn.setVisible(not is_gatekeeper)
        self.back_btn.setVisible(not is_first and not is_gatekeeper)
        self.skip_btn.setVisible(index == 4)
