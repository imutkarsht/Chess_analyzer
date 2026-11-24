# SPDX-License-Identifier: GPL-3.0-only
"""Shared themed dialogs and dialog launchers."""

from __future__ import annotations

import traceback

from PyQt6.QtCore import QObject, Qt
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QVBoxLayout,
)

from src.constants import PAGE_SETTINGS
from src.gui.components.controls.button import Button, ButtonVariant
from src.gui.components.display.label import Label
from src.gui.theme.typography import TextRole, TextTone
from src.utils.logger import logger


def confirm_dialog(
    parent,
    title: str,
    message: str,
    confirm_label: str = "Confirm",
    cancel_label: str = "Cancel",
    danger: bool = True,
) -> bool:
    """Show a lightweight, themed Yes/No confirmation dialog."""
    dialog = QDialog(parent)
    dialog.setWindowTitle(title)
    dialog.setModal(True)
    dialog.setMinimumWidth(360)
    dialog.setObjectName("ConfirmDialog")

    root = QVBoxLayout(dialog)
    root.setContentsMargins(24, 20, 24, 20)
    root.setSpacing(16)

    title_label = Label(title, role=TextRole.SUBHEADING, weight=700)
    root.addWidget(title_label)

    message_label = Label(
        message,
        role=TextRole.BODY,
        tone=TextTone.SECONDARY,
        wrap=True,
    )
    root.addWidget(message_label)

    button_row = QHBoxLayout()
    button_row.addStretch()
    button_row.addWidget(
        Button(cancel_label, ButtonVariant.FILLED, on_click=dialog.reject)
    )
    button_row.addWidget(
        Button(
            confirm_label,
            ButtonVariant.PRIMARY,
            danger=danger,
            on_click=dialog.accept,
        )
    )
    root.addLayout(button_row)

    return dialog.exec() == QDialog.DialogCode.Accepted


def show_error_dialog(
    parent,
    title: str,
    message: str,
    details: str = "",
    *,
    action_label: str | None = None,
    on_action=None,
    close_label: str = "OK",
) -> None:
    """Show a modal error dialog with selectable/copyable details.

    ``action_label`` adds one optional action button (for example
    "Report Issue"). ``on_action`` runs after the dialog closes when that
    button was clicked.
    """
    try:
        if parent is not None and not isinstance(parent, QObject):
            parent = None
    except Exception:
        pass

    try:
        box = QMessageBox(parent)
    except Exception:
        box = QMessageBox()

    clicked_action = False
    try:
        box.setIcon(QMessageBox.Icon.Critical)
        box.setWindowTitle(title)
        box.setTextFormat(Qt.TextFormat.PlainText)
        box.setText(message)
        if details:
            box.setDetailedText(details)

        try:
            for label in box.findChildren(QLabel):
                label.setTextInteractionFlags(
                    Qt.TextInteractionFlag.TextSelectableByMouse
                    | Qt.TextInteractionFlag.TextSelectableByKeyboard
                )
        except Exception:
            pass

        if action_label:
            close_button = box.addButton(QMessageBox.StandardButton.Ok)
            close_button.setText(close_label)
            action_button = box.addButton(
                action_label, QMessageBox.ButtonRole.ActionRole
            )
            box.setDefaultButton(close_button)
            box.exec()
            clicked_action = box.clickedButton() is action_button
        else:
            box.setStandardButtons(QMessageBox.StandardButton.Ok)
            box.exec()
    except Exception:
        logger.error("show_error_dialog failed: %s", traceback.format_exc())
        return

    if clicked_action and on_action is not None:
        on_action()


def open_llm_settings(parent) -> None:
    """Offer the LLM setup dialog, then open Settings when accepted."""
    from src.gui.dialogs.llm_error_dialog import LlmNotConfiguredDialog

    dialog = LlmNotConfiguredDialog(parent)
    if dialog.exec() != QDialog.DialogCode.Accepted or not dialog.wants_configure():
        return
    window = parent.window()
    if hasattr(window, "sidebar") and hasattr(window, "switch_page"):
        window.sidebar.set_active(PAGE_SETTINGS)
        window.switch_page(PAGE_SETTINGS)


def open_feedback_dialog(parent, *, initial_tab: str = "bug") -> None:
    """Open the unified feedback dialog on the requested tab."""
    from src.gui.dialogs.feedback_dialog import FeedbackDialog

    FeedbackDialog(parent, initial_tab=initial_tab).exec()
