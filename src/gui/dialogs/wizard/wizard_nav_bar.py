from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

from src.gui.styles import Styles
from src.gui.theme import ThemeManager


class WizardNavBar(QWidget):
    """
    Bottom navigation bar for SetupWizard with step badges and next/back/skip buttons.
    """
    STEP_TITLES = [
        "Welcome",
        "Accounts",
        "Theme",
        "Engine",
        "AI Coach",
        "Finish"
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("WizardNavBar")
        self.setFixedHeight(56)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 8, 20, 8)
        layout.setSpacing(12)

        # Step indicator container
        self.steps_widget = QWidget()
        self.steps_widget.setStyleSheet(Styles.get_transparent_label_style())
        self.steps_layout = QHBoxLayout(self.steps_widget)
        self.steps_layout.setContentsMargins(0, 0, 0, 0)
        self.steps_layout.setSpacing(6)

        self.step_pills: list[QLabel] = []
        for i in range(len(self.STEP_TITLES)):
            pill = QLabel(f"{i + 1}")
            pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
            pill.setFixedSize(22, 22)
            self.step_pills.append(pill)
            self.steps_layout.addWidget(pill)

        self.step_name_label = QLabel("")
        self.steps_layout.addWidget(self.step_name_label)

        layout.addWidget(self.steps_widget)
        layout.addStretch()

        self.skip_btn = QPushButton("Skip AI Setup")
        self.skip_btn.setFlat(True)
        self.skip_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        layout.addWidget(self.skip_btn)

        self.back_btn = QPushButton("Back")
        self.back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.back_btn.setFixedHeight(36)
        layout.addWidget(self.back_btn)

        self.next_btn = QPushButton("Next")
        self.next_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.next_btn.setFixedHeight(36)
        layout.addWidget(self.next_btn)

        self.refresh_theme()

    def refresh_theme(self):
        p = ThemeManager.palette()
        self.setStyleSheet(f"""
            QWidget#WizardNavBar {{
                background-color: {p.surface};
                border-top: 1px solid {p.border};
            }}
        """)
        self.step_name_label.setStyleSheet(
            f"color: {p.text_primary}; font-size: 13px; font-weight: 600; margin-left: 6px; {Styles.get_transparent_label_style()}"
        )
        self.skip_btn.setStyleSheet(f"""
            QPushButton {{
                color: {p.text_secondary};
                font-size: 13px;
                border: none;
                background: transparent;
                padding: 6px 12px;
            }}
            QPushButton:hover {{
                color: {p.text_primary};
            }}
        """)
        self.refresh_accent()

    def refresh_accent(self):
        p = ThemeManager.palette()
        self.next_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {p.accent};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 0 24px;
                font-size: 13px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {p.accent_hover};
            }}
        """)
        self.back_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {p.surface_light};
                color: {p.text_primary};
                border: 1px solid {p.border};
                border-radius: 6px;
                padding: 0 18px;
                font-size: 13px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                border: 1px solid {p.accent};
                background-color: {p.surface};
            }}
        """)

    def update(self, index: int, total: int = 7):
        # Map wizard page index to step indicator (0: Gatekeeper, 1: Welcome, 2: Profile, 3: Appearance, 4: Engine, 5: LLM, 6: Done)
        # We display steps starting from index 1 (Welcome) up to 6 (Done)
        step_idx = max(0, min(len(self.STEP_TITLES) - 1, index - 1)) if index > 0 else 0
        p = ThemeManager.palette()

        for i, pill in enumerate(self.step_pills):
            if i == step_idx and index > 0:
                pill.setStyleSheet(f"""
                    QLabel {{
                        background-color: {p.accent};
                        color: white;
                        font-size: 11px;
                        font-weight: bold;
                        border-radius: 11px;
                    }}
                """)
            elif i < step_idx:
                pill.setStyleSheet(f"""
                    QLabel {{
                        background-color: {p.surface_light};
                        color: {Styles.COLOR_BEST};
                        font-size: 11px;
                        font-weight: bold;
                        border: 1px solid {Styles.COLOR_BEST};
                        border-radius: 11px;
                    }}
                """)
            else:
                pill.setStyleSheet(f"""
                    QLabel {{
                        background-color: {p.surface_light};
                        color: {p.text_muted};
                        font-size: 11px;
                        font-weight: 500;
                        border: 1px solid {p.border};
                        border-radius: 11px;
                    }}
                """)

        if index > 0 and step_idx < len(self.STEP_TITLES):
            self.step_name_label.setText(self.STEP_TITLES[step_idx])
            self.steps_widget.setVisible(True)
        else:
            self.steps_widget.setVisible(False)

        is_last = index == total - 1
        is_first = index <= 1
        is_gatekeeper = index == 0

        self.back_btn.setVisible(not is_first and not is_gatekeeper)
        self.skip_btn.setVisible(index == 5)
        self.next_btn.setText("Finish" if is_last else "Next")
        self.next_btn.setVisible(not is_gatekeeper and index != 1 and not is_last)

        if index > 0 and step_idx < len(self.STEP_TITLES):
            self.step_name_label.setText(self.STEP_TITLES[step_idx])
            self.steps_widget.setVisible(True)
        else:
            self.steps_widget.setVisible(False)

        is_last = index == total - 1
        is_first = index <= 1
        is_gatekeeper = index == 0

        self.back_btn.setVisible(not is_first and not is_gatekeeper)
        self.skip_btn.setVisible(index == 5)
        self.next_btn.setText("Finish" if is_last else "Next")
        self.next_btn.setVisible(not is_gatekeeper and index != 1 and not is_last)
