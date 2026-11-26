# SPDX-License-Identifier: GPL-3.0-only
"""Shared card chrome for every in-window overlay dialog.

One widget owns the header, scrollable body, action row, close affordance and
accessibility contract. Dialog content is a plain ``QWidget`` dropped into
``set_content``, so the same panel can be embedded in an overlay or in a thin
native ``QDialog`` wrapper during migration.

Static chrome lives in ``theme_template.qss``; this module only publishes
object names and dynamic properties.
"""

from __future__ import annotations

from enum import Enum

from PyQt6.QtCore import QEvent, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.gui.components.controls.button import Button, ButtonSize, ButtonVariant
from src.gui.components.display.label import Label
from src.gui.styles import Styles
from src.gui.theme.typography import TextRole, TextTone


class OverlayResult(Enum):
    """How an overlay was closed."""

    ACCEPTED = "accepted"
    REJECTED = "rejected"
    DISMISSED = "dismissed"


class OverlayCard(QFrame):
    """The one visual parent for every in-window dialog.

    Content panels only build their body; the card supplies the title,
    description, close button, spacing, scrolling and action row. That keeps
    every confirmation, form and error surface visually identical.
    """

    result_requested = pyqtSignal(object)
    close_requested = pyqtSignal()
    size_hint_changed = pyqtSignal()

    def __init__(
        self,
        *,
        title: str = "",
        description: str = "",
        max_width: int = 520,
        minimum_width: int = 320,
        dismiss_on_escape: bool = True,
        dismiss_on_backdrop: bool = True,
        show_close: bool = True,
        destructive: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("OverlayCard")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        self.max_width = max(int(max_width), minimum_width)
        self.minimum_width = minimum_width
        self.dismiss_on_escape = dismiss_on_escape
        self.dismiss_on_backdrop = dismiss_on_backdrop
        self.destructive = destructive
        self._initial_focus: QWidget | None = None
        self._content: QWidget | None = None
        self._secondary_actions = 0

        self._build_ui(title, description, show_close)
        self._apply_accessible_copy(title, description)

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def _build_ui(self, title: str, description: str, show_close: bool) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.header = QWidget(self)
        self.header.setObjectName("OverlayHeader")
        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(24, 22, 18, 12)
        header_layout.setSpacing(12)

        copy_column = QVBoxLayout()
        copy_column.setContentsMargins(0, 0, 0, 0)
        copy_column.setSpacing(5)

        self.title_label = Label(
            title,
            role=TextRole.DIALOG_TITLE,
            weight=700,
            wrap=True,
        )
        self.description_label = Label(
            description,
            role=TextRole.BODY_LARGE,
            tone=TextTone.SECONDARY,
            wrap=True,
        )
        copy_column.addWidget(self.title_label)
        copy_column.addWidget(self.description_label)
        header_layout.addLayout(copy_column, 1)

        self.close_button = Button(
            "✕",
            ButtonVariant.GHOST,
            ButtonSize.SM,
            tooltip="Close (Esc)",
            on_click=self.close_requested.emit,
        )
        self.close_button.setAccessibleName("Close dialog")
        self.close_button.setVisible(show_close)
        header_layout.addWidget(
            self.close_button,
            0,
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight,
        )

        self.title_label.setVisible(bool(title))
        self.description_label.setVisible(bool(description))
        self.header.setVisible(bool(title or description))
        root.addWidget(self.header)

        self.body_scroll = QScrollArea(self)
        self.body_scroll.setObjectName("OverlayBodyScroll")
        self.body_scroll.setWidgetResizable(True)
        self.body_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.body_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.body_scroll.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        Styles.apply_transparent(self.body_scroll)
        Styles.apply_transparent(self.body_scroll.viewport())

        self.body = QWidget(self.body_scroll)
        self.body.setObjectName("OverlayBody")
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(24, 4, 24, 20)
        self.body_layout.setSpacing(0)
        self.body_scroll.setWidget(self.body)
        root.addWidget(self.body_scroll, 1)

        self.footer = QWidget(self)
        self.footer.setObjectName("OverlayFooter")
        footer_layout = QHBoxLayout(self.footer)
        footer_layout.setContentsMargins(24, 0, 24, 20)
        footer_layout.setSpacing(8)
        footer_layout.addStretch(1)

        self.actions_layout = QHBoxLayout()
        self.actions_layout.setContentsMargins(0, 0, 0, 0)
        self.actions_layout.setSpacing(8)
        footer_layout.addLayout(self.actions_layout)
        self.footer.hide()
        root.addWidget(self.footer)

    def _apply_accessible_copy(self, title: str, description: str) -> None:
        name = title.strip() or "Dialog"
        self.setAccessibleName(name)
        self.setAccessibleDescription(description.strip())

    # ------------------------------------------------------------------
    # Content and actions
    # ------------------------------------------------------------------

    def set_content(self, widget: QWidget) -> None:
        """Install the panel body. The card owns layout and scrolling."""
        if self._content is widget:
            return
        if self._content is not None:
            self._content.removeEventFilter(self)
            self.body_layout.removeWidget(self._content)
            self._content.setParent(None)
            self._content.deleteLater()
        self._content = widget
        widget.setParent(self.body)
        self.body_layout.addWidget(widget, 1)
        widget.installEventFilter(self)
        self.notify_content_changed()

    @property
    def content(self) -> QWidget | None:
        return self._content

    def add_action(self, widget: QWidget, *, primary: bool = False) -> QWidget:
        """Add an action in shadcn order: secondaries first, primary last."""
        if primary:
            self.actions_layout.addWidget(widget)
        else:
            self.actions_layout.insertWidget(self._secondary_actions, widget)
            self._secondary_actions += 1
        self.footer.show()
        return widget

    def set_initial_focus(self, widget: QWidget | None) -> None:
        self._initial_focus = widget

    @property
    def initial_focus(self) -> QWidget:
        candidate = self._initial_focus
        if candidate is not None and candidate.isVisibleTo(self):
            return candidate
        return self

    def notify_content_changed(self) -> None:
        """Ask the host to recalculate the card height after a page change."""
        self.layout().activate()
        self.size_hint_changed.emit()

    # ------------------------------------------------------------------
    # Result helpers
    # ------------------------------------------------------------------

    def accept(self) -> None:
        self.result_requested.emit(OverlayResult.ACCEPTED)

    def reject(self) -> None:
        self.result_requested.emit(OverlayResult.REJECTED)

    def dismiss(self) -> None:
        self.result_requested.emit(OverlayResult.DISMISSED)

    def preferred_height(self) -> int:
        """Natural height before the host clamps it to the window."""
        self.layout().activate()
        header = self.header.sizeHint().height() if not self.header.isHidden() else 0
        footer = self.footer.sizeHint().height() if not self.footer.isHidden() else 0
        body = self.body.sizeHint().height()
        return header + body + footer

    # ------------------------------------------------------------------
    # Qt overrides
    # ------------------------------------------------------------------

    def eventFilter(self, obj, event):
        if obj is self._content and event.type() == QEvent.Type.LayoutRequest:
            self.size_hint_changed.emit()
        return super().eventFilter(obj, event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape and self.dismiss_on_escape:
            self.dismiss()
            return
        super().keyPressEvent(event)
