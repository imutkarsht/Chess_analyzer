# SPDX-License-Identifier: GPL-3.0-only
"""Keyboard Shortcuts Help panel, dialog wrapper, and overlay launcher."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from src.gui.components import (
    Button,
    ButtonVariant,
    IconLabel,
    Label,
    OverlayManager,
    StatusBadge,
    TextRole,
    TextTone,
    open_feedback_dialog,
)
from src.gui.styles import Styles
from src.utils.logger import logger


class ShortcutHelpPanel(QWidget):
    """Two-column categorized keyboard shortcut grid.

    Embedded directly inside ``OverlayCard`` (which provides scrolling, header,
    and actions) or inside ``ShortcutHelpDialog`` for native fallback.
    """

    _CAT_ICONS = {
        "File": "fa5s.folder-open",
        "Analysis": "fa5s.bolt",
        "Navigation": "fa5s.arrows-alt",
        "Board": "fa5s.chess-board",
        "Variations": "fa5s.code-branch",
        "Pages": "fa5s.columns",
        "Help": "fa5s.question-circle",
        "General": "fa5s.cog",
    }

    def __init__(self, bindings: list[dict] | None = None, parent: QWidget | None = None):
        super().__init__(parent)
        self._bindings = bindings or []
        self._build_ui()

    def _build_ui(self) -> None:
        content_layout = QHBoxLayout(self)
        content_layout.setSpacing(20)
        content_layout.setContentsMargins(0, 0, 0, 0)

        left_column = QVBoxLayout()
        left_column.setSpacing(12)
        left_column.setContentsMargins(0, 0, 0, 0)

        right_column = QVBoxLayout()
        right_column.setSpacing(12)
        right_column.setContentsMargins(0, 0, 0, 0)

        content_layout.addLayout(left_column, 1)
        content_layout.addLayout(right_column, 1)

        shortcuts = self.group_bindings(self._bindings)
        left_categories = {"Navigation", "Board", "Variations"}

        for category, items in shortcuts.items():
            target_col = left_column if category in left_categories else right_column

            cat_widget = QWidget(self)
            cat_layout = QVBoxLayout(cat_widget)
            cat_layout.setContentsMargins(0, 0, 0, 0)
            cat_layout.setSpacing(6)

            hdr_layout = QHBoxLayout()
            hdr_layout.setSpacing(8)
            hdr_layout.addWidget(
                IconLabel(
                    self._CAT_ICONS.get(category, "fa5s.circle"),
                    size=13,
                    tone=TextTone.ACCENT,
                )
            )
            hdr_layout.addWidget(
                Label(
                    category.upper(),
                    role=TextRole.CARD_TITLE,
                    tone=TextTone.ACCENT,
                )
            )
            hdr_layout.addStretch()
            cat_layout.addLayout(hdr_layout)

            for key, description in items:
                cat_layout.addWidget(self._create_shortcut_row(key, description))

            target_col.addWidget(cat_widget)

        left_column.addStretch()
        right_column.addStretch()

    @staticmethod
    def lookup_bindings(parent) -> list[dict]:
        window = parent.window() if parent is not None else None
        manager = getattr(window, "shortcut_manager", None)
        return manager.get_bindings() if manager is not None else []

    @staticmethod
    def group_bindings(bindings: list[dict]) -> dict[str, list[tuple[str, str]]]:
        """Group ``ShortcutManager.get_bindings()`` output by category, in order."""
        grouped: dict[str, list[tuple[str, str]]] = {}
        for binding in bindings:
            if binding["keys"]:
                keys = "  /  ".join(binding["keys"])
                grouped.setdefault(binding["category"], []).append(
                    (keys, binding["description"])
                )
        # F1/? and dialog Esc are handled outside ShortcutManager (keyPressEvent / OverlayManager).
        grouped.setdefault("General", []).extend(
            [
                ("F1  /  ?", "Show this help"),
                ("Esc", "Close dialogs"),
            ]
        )
        return grouped

    def _create_shortcut_row(self, key: str, description: str) -> QFrame:
        """Create a compact row with key badge and description."""
        row = QFrame(self)
        row.setObjectName("ShortcutRow")

        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(10, 6, 10, 6)
        row_layout.setSpacing(10)

        key_label = StatusBadge(
            key,
            "neutral",
            variant="outline",
            mono=True,
            font_size=11,
            weight=600,
            padding="3px 8px",
            radius=4,
        )
        key_label.setMinimumWidth(68)
        key_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        row_layout.addWidget(key_label)

        desc_label = Label(description, role=TextRole.CAPTION, weight=500)
        row_layout.addWidget(desc_label, 1)
        return row


class ShortcutHelpDialog(QDialog):
    """Native QDialog wrapper around ``ShortcutHelpPanel``."""

    def __init__(self, parent=None, bindings: list[dict] | None = None):
        super().__init__(parent)
        self._bindings = (
            bindings if bindings is not None else ShortcutHelpPanel.lookup_bindings(parent)
        )
        self.setWindowTitle("Keyboard Shortcuts")
        self.resize(760, 580)
        self.setMinimumSize(680, 480)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setup_ui()

    def setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        header_layout = QHBoxLayout()
        header_layout.setSpacing(12)
        header_layout.addWidget(
            IconLabel("fa5s.keyboard", size=26, tone=TextTone.ACCENT, fallback="⌨")
        )
        header_layout.addWidget(
            Label("Keyboard Shortcuts", role=TextRole.DIALOG_TITLE, weight=600)
        )
        header_layout.addStretch()
        layout.addLayout(header_layout)

        layout.addWidget(
            Label(
                "Master these shortcuts to navigate and analyze games faster",
                role=TextRole.CAPTION,
                tone=TextTone.SECONDARY,
            )
        )

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        Styles.apply_background(scroll)
        self.panel = ShortcutHelpPanel(self._bindings, scroll)
        scroll.setWidget(self.panel)
        layout.addWidget(scroll, 1)

        btn_feedback = Button(
            "Report Bug / Feedback",
            ButtonVariant.FILLED,
            icon="fa5s.comment-dots",
            on_click=lambda: open_feedback_dialog(self, initial_tab="bug"),
        )
        btn_close = Button("Got it", ButtonVariant.PRIMARY, on_click=self.accept)

        btn_layout = QHBoxLayout()
        btn_layout.addWidget(btn_feedback)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_close)
        layout.addLayout(btn_layout)

    @staticmethod
    def _lookup_bindings(parent) -> list[dict]:
        return ShortcutHelpPanel.lookup_bindings(parent)

    @staticmethod
    def _group_bindings(bindings: list[dict]) -> dict[str, list[tuple[str, str]]]:
        return ShortcutHelpPanel.group_bindings(bindings)


def open_shortcut_help_overlay(parent, bindings: list[dict] | None = None) -> None:
    """Open the shortcut help panel as an in-window overlay."""
    if isinstance(parent, QWidget):
        try:
            resolved = (
                bindings if bindings is not None else ShortcutHelpPanel.lookup_bindings(parent)
            )
            manager = OverlayManager.for_window(parent)
            card = manager.create_card(
                title="Keyboard Shortcuts",
                description="Master these shortcuts to navigate and analyze games faster.",
                max_width=760,
                minimum_width=460,
                dismiss_on_escape=True,
                dismiss_on_backdrop=True,
            )
            panel = ShortcutHelpPanel(resolved, card)
            card.set_content(panel)

            feedback_btn = Button(
                "Report Bug / Feedback",
                ButtonVariant.LINK,
                icon="fa5s.comment-dots",
                on_click=lambda: open_feedback_dialog(parent, initial_tab="bug"),
            )
            done_btn = Button("Got it", ButtonVariant.PRIMARY, on_click=card.accept)
            card.add_action(feedback_btn)
            card.add_action(done_btn, primary=True)
            card.set_initial_focus(done_btn)

            manager.open(card)
            return
        except Exception:
            logger.warning("open_shortcut_help_overlay failed, falling back", exc_info=True)

    ShortcutHelpDialog(parent, bindings=bindings).exec()
