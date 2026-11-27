# SPDX-License-Identifier: GPL-3.0-only
"""Error dialog for when the LLM is not configured.

Offers Configure Now and Skip actions. ``open_llm_not_configured`` is the
preferred entry-point: it opens an in-window overlay and returns ``True`` when
the user wants to configure the LLM. The legacy QDialog class is kept for
compatibility with native fallbacks.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QHBoxLayout, QVBoxLayout, QWidget

from src.gui.components import (
    Button,
    ButtonVariant,
    Label,
    OverlayManager,
    OverlayResult,
    TextRole,
    TextTone,
)
from src.utils.logger import logger


def open_llm_not_configured(parent) -> bool:
    """Show the LLM-not-configured notice as an in-window overlay.

    Returns ``True`` when the user chose *Configure Now*, ``False`` otherwise.
    Falls back to a plain QDialog when no overlay host is available.
    """
    if isinstance(parent, QWidget):
        try:
            manager = OverlayManager.for_window(parent)
            card = manager.create_card(
                title="AI Features Require Configuration",
                description=(
                    "AI-powered analysis — summaries, coach insights, and move "
                    "explanations — needs an LLM provider API key. "
                    "You can configure one in Settings."
                ),
                max_width=480,
                dismiss_on_escape=True,
                dismiss_on_backdrop=True,
            )

            skip_btn = Button("Skip", ButtonVariant.HOLLOW, on_click=card.reject)
            configure_btn = Button(
                "Configure Now",
                ButtonVariant.PRIMARY,
                icon="fa5s.cog",
                on_click=card.accept,
            )
            card.add_action(skip_btn)
            card.add_action(configure_btn, primary=True)
            card.set_initial_focus(configure_btn)

            result = manager.open_blocking(card)
            return result is OverlayResult.ACCEPTED
        except Exception:
            logger.warning("open_llm_not_configured overlay failed, falling back", exc_info=True)

    dialog = LlmNotConfiguredDialog(parent)
    return (
        dialog.exec() == QDialog.DialogCode.Accepted
        and dialog.wants_configure()
    )


class LlmNotConfiguredDialog(QDialog):
    """Legacy native-dialog fallback for the LLM-not-configured notice."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("LLM Not Configured")
        self.setFixedSize(440, 220)

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
