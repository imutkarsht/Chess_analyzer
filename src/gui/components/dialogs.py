# SPDX-License-Identifier: GPL-3.0-only
"""Shared themed dialogs and dialog launchers."""

from __future__ import annotations

import traceback

from PyQt6.QtCore import QObject, Qt
from PyQt6.QtWidgets import (
    QLabel,
    QMessageBox,
    QWidget,
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
    """Show a themed in-window confirmation overlay.

    Falls back to the legacy QDialog path when no windowed parent is available.
    """
    # Resolve a widget so we can reach OverlayManager.
    widget: QWidget | None = None
    if isinstance(parent, QWidget):
        widget = parent

    if widget is not None:
        try:
            from src.gui.components.feedback.overlay_card import OverlayResult
            from src.gui.components.feedback.overlay_manager import OverlayManager

            manager = OverlayManager.for_window(widget)
            card = manager.create_card(
                title=title,
                description=message,
                max_width=460,
                dismiss_on_escape=not danger,
                dismiss_on_backdrop=not danger,
                show_close=not danger,
                destructive=danger,
            )

            cancel_btn = Button(cancel_label, ButtonVariant.HOLLOW, on_click=card.reject)
            confirm_btn = Button(
                confirm_label,
                ButtonVariant.PRIMARY,
                danger=danger,
                on_click=card.accept,
            )
            card.add_action(cancel_btn)
            card.add_action(confirm_btn, primary=True)
            card.set_initial_focus(cancel_btn if danger else confirm_btn)

            result = manager.open_blocking(card)
            return result is OverlayResult.ACCEPTED
        except Exception:
            logger.warning("confirm_dialog overlay failed, falling back", exc_info=True)

    # Fallback: plain QDialog for windows that have no overlay host yet.
    from PyQt6.QtWidgets import QDialog, QHBoxLayout, QVBoxLayout

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
    """Offer the LLM setup dialog as an in-window overlay, then open Settings."""
    from src.gui.dialogs.llm_error_dialog import open_llm_not_configured

    wants_configure = open_llm_not_configured(parent)
    if not wants_configure:
        return
    window = parent.window() if isinstance(parent, QWidget) else None
    if window is not None and hasattr(window, "sidebar") and hasattr(window, "switch_page"):
        window.sidebar.set_active(PAGE_SETTINGS)
        window.switch_page(PAGE_SETTINGS)


def open_feedback_dialog(
    parent,
    *,
    initial_tab: str = "bug",
    initial_title: str = "",
    initial_message: str = "",
    initial_logs: str = "",
) -> None:
    """Open the unified feedback dialog as an in-window overlay."""
    from src.gui.dialogs.feedback_dialog import open_feedback_overlay

    open_feedback_overlay(
        parent,
        initial_tab=initial_tab,
        initial_title=initial_title,
        initial_message=initial_message,
        initial_logs=initial_logs,
    )
