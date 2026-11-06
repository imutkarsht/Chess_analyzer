from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QHBoxLayout, QWidget

from src.gui.components import Button, ButtonVariant, Label, StatusBadge, TextRole
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
        self.steps_layout = QHBoxLayout(self.steps_widget)
        self.steps_layout.setContentsMargins(0, 0, 0, 0)
        self.steps_layout.setSpacing(6)

        self.step_pills: list[StatusBadge] = []
        for i in range(len(self.STEP_TITLES)):
            pill = StatusBadge(
                f"{i + 1}",
                "neutral",
                variant="soft",
                font_size=11,
                weight=700,
                padding="0px",
                radius=11,
            )
            pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
            pill.setFixedSize(22, 22)
            self.step_pills.append(pill)
            self.steps_layout.addWidget(pill)

        self.step_name_label = Label("", role=TextRole.BODY, weight=600)
        self.steps_layout.addSpacing(6)
        self.steps_layout.addWidget(self.step_name_label)

        layout.addWidget(self.steps_widget)
        layout.addStretch()

        self.skip_btn = Button("Skip AI Setup", ButtonVariant.GHOST)
        layout.addWidget(self.skip_btn)

        self.back_btn = Button("Back", ButtonVariant.FILLED)
        self.back_btn.setFixedHeight(36)
        layout.addWidget(self.back_btn)

        self.next_btn = Button("Next", ButtonVariant.PRIMARY)
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
        self.skip_btn.refresh_styles()
        self.refresh_accent()

    def refresh_accent(self):
        self.next_btn.refresh_styles()
        self.back_btn.refresh_styles()

    def update(self, index: int, total: int = 7):
        # Map wizard page index to step indicator (0: Gatekeeper, 1: Welcome, 2: Profile, 3: Appearance, 4: Engine, 5: LLM, 6: Done)
        # We display steps starting from index 1 (Welcome) up to 6 (Done)
        step_idx = max(0, min(len(self.STEP_TITLES) - 1, index - 1)) if index > 0 else 0

        for i, pill in enumerate(self.step_pills):
            if i == step_idx and index > 0:
                pill.set_tone("accent")
                pill.set_variant("solid")
            elif i < step_idx:
                pill.set_tone("best")
                pill.set_variant("soft")
            else:
                pill.set_tone("neutral")
                pill.set_variant("soft")

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
