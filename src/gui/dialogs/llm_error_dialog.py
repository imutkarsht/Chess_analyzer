"""
Error dialog for when the LLM is not configured,
offering Configure Now and Skip actions.
"""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QHBoxLayout, QVBoxLayout

from ..components import Button, ButtonVariant, Label, TextRole, TextTone
from ..styles import Styles


class LlmNotConfiguredDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("LLM Not Configured")
        self.setFixedSize(440, 220)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {Styles.COLOR_BACKGROUND};
                color: {Styles.COLOR_TEXT_PRIMARY};
            }}
        """)

        self._configured = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 28, 28, 20)
        layout.setSpacing(14)

        title = Label("AI Features Require Configuration", role=TextRole.SECTION_TITLE)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        desc = Label(
            "AI-powered analysis (summaries, coach insights, and move explanations) "
            "need an LLM provider API key. You can configure one in Settings.",
            role=TextRole.BODY,
            tone=TextTone.SECONDARY,
            wrap=True,
        )
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(desc)

        layout.addStretch()

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self._skip_btn = Button("Skip", ButtonVariant.FILLED, on_click=self.reject)
        btn_layout.addWidget(self._skip_btn)

        btn_layout.addSpacing(12)

        self._configure_btn = Button(
            "Configure Now",
            ButtonVariant.PRIMARY,
            on_click=self._on_configure,
        )
        btn_layout.addWidget(self._configure_btn)

        layout.addLayout(btn_layout)

    def _on_configure(self):
        self._configured = True
        self.accept()

    def wants_configure(self) -> bool:
        return self._configured
