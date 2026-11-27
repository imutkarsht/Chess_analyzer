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

from PyQt6.QtCore import QEvent, QSize, Qt, pyqtSignal
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


class _BodyScrollArea(QScrollArea):
    """Scroll area that hugs short content instead of forcing QScrollArea's
    ~256x192 default size hints onto compact confirmation cards."""

    def sizeHint(self) -> QSize:
        widget = self.widget()
        if widget is None:
            return super().sizeHint()
        return widget.sizeHint()

    def minimumSizeHint(self) -> QSize:
        return QSize(0, 0)


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
        if parent is not None:
            # Stay hidden until the host's card layer adopts and layouts us.
            self.hide()
        self.setObjectName("OverlayCard")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        # Expose the destructive flag as a Qt dynamic property so QSS can key
        # off it for a red-tinted header stripe without any inline styles.
        self.setProperty("overlayDestructive", destructive)

        self.max_width = max(int(max_width), minimum_width)
        self.minimum_width = minimum_width
        self.dismiss_on_escape = dismiss_on_escape
        self.dismiss_on_backdrop = dismiss_on_backdrop
        self.destructive = destructive
        self._initial_focus: QWidget | None = None
        self._content: QWidget | None = None
        self._secondary_actions = 0
        self._cleanups: list = []

        self._build_ui(title, description, show_close)
        self._apply_accessible_copy(title, description)

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def _build_ui(self, title: str, description: str, show_close: bool) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Header ────────────────────────────────────────────────────
        self.header = QWidget(self)
        self.header.setObjectName("OverlayHeader")
        header_layout = QHBoxLayout(self.header)
        # 24 px left gutter; 22 px top; 20 px right so the 28 px icon button
        # aligns cleanly; 14 px bottom gap before body or footer.
        header_layout.setContentsMargins(24, 22, 20, 14)
        header_layout.setSpacing(12)

        copy_column = QVBoxLayout()
        copy_column.setContentsMargins(0, 0, 0, 0)
        copy_column.setSpacing(6)

        self.title_label = Label(
            title,
            role=TextRole.DIALOG_TITLE,
            weight=600,
            wrap=True,
        )
        self.description_label = Label(
            description,
            role=TextRole.BODY,
            tone=TextTone.SECONDARY,
            wrap=True,
        )
        copy_column.addWidget(self.title_label)
        copy_column.addWidget(self.description_label)
        header_layout.addLayout(copy_column, 1)

        # Close button: compact icon-only ghost, quiet until hovered.
        # Pass parent=self.header and attach before setVisible so a temporary
        # parentless setVisible(True) never flashes a top-level NSWindow on macOS
        # (which pulls full-screen windows back to Desktop 1).
        self.close_button = Button(
            "",
            ButtonVariant.GHOST,
            ButtonSize.SM,
            icon="fa5s.times",
            icon_position="only",
            tooltip="Close (Esc)",
            on_click=self.close_requested.emit,
            parent=self.header,
        )
        self.close_button.setObjectName("OverlayCloseBtn")
        self.close_button.setAccessibleName("Close dialog")
        header_layout.addWidget(
            self.close_button,
            0,
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight,
        )
        self.close_button.setVisible(show_close)

        self.title_label.setVisible(bool(title))
        self.description_label.setVisible(bool(description))
        self.header.setVisible(bool(title or description))
        root.addWidget(self.header)

        # ── Body ──────────────────────────────────────────────────────
        self.body_scroll = _BodyScrollArea(self)
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
        self.body_layout.setContentsMargins(24, 6, 24, 16)
        self.body_layout.setSpacing(0)
        self.body_scroll.setWidget(self.body)
        # Hidden until non-empty content is installed so header-only dialogs
        # (like confirmations) stay compact without an empty middle gap.
        self.body_scroll.hide()
        root.addWidget(self.body_scroll, 1)

        # ── Footer ────────────────────────────────────────────────────
        self.footer = QWidget(self)
        self.footer.setObjectName("OverlayFooter")
        footer_layout = QHBoxLayout(self.footer)
        footer_layout.setContentsMargins(24, 10, 24, 22)
        footer_layout.setSpacing(10)
        footer_layout.addStretch(1)

        self.actions_layout = QHBoxLayout()
        self.actions_layout.setContentsMargins(0, 0, 0, 0)
        self.actions_layout.setSpacing(10)
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
        has_body = widget.layout() is None or widget.layout().count() > 0 or bool(widget.children())
        self.body_scroll.setVisible(has_body)
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

    def add_cleanup(self, fn) -> None:
        """Register a callback run whenever this card closes or shuts down."""
        self._cleanups.append(fn)

    def run_cleanup(self) -> None:
        """Run and clear registered cleanup callbacks."""
        callbacks, self._cleanups = self._cleanups, []
        for fn in callbacks:
            fn()

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
        border = 2  # 1px QFrame border top/bottom and left/right
        inner_width = max(120, (self.width() or self.max_width) - border)
        header = 0
        if not self.header.isHidden():
            header_lay = self.header.layout()
            header_lay.activate()
            header = (
                header_lay.totalHeightForWidth(inner_width)
                if header_lay.hasHeightForWidth()
                else self.header.sizeHint().height()
            )
        footer = self.footer.sizeHint().height() if not self.footer.isHidden() else 0
        body = 0
        if not self.body_scroll.isHidden():
            body_lay = self.body.layout()
            body_lay.activate()
            body = (
                body_lay.totalHeightForWidth(inner_width)
                if body_lay.hasHeightForWidth()
                else self.body.sizeHint().height()
            )
        return border + header + body + footer

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

    def mousePressEvent(self, event):
        event.accept()

    def mouseReleaseEvent(self, event):
        event.accept()

    def mouseDoubleClickEvent(self, event):
        event.accept()

    def wheelEvent(self, event):
        event.accept()

    def contextMenuEvent(self, event):
        event.accept()
