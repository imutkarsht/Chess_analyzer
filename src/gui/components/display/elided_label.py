# SPDX-License-Identifier: GPL-3.0-only
"""Semantic label that ellipsizes and reveals the full text only when needed.

Label-only tooltips are noise when the label already fits. This component
keeps the full string, paints an ellipsized version when the available width
is too small, and attaches the full string as a tooltip only in that case.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QWidget

from src.gui.components.display.label import Label
from src.gui.components.feedback.tooltip import (
    Tooltip,
    TooltipKind,
    attach_tooltip,
    detach_tooltip,
)
from src.gui.theme.typography import TextRole, TextTone


class ElidedLabel(Label):
    """A label that ellipsizes instead of forcing its row wider.

    ``tooltip_when_elided`` is the normal mode. Set it to ``False`` for labels
    whose full text is available elsewhere and should never show a tooltip.
    """

    def __init__(
        self,
        text: str = "",
        role: TextRole | str = TextRole.BODY,
        tone: TextTone | str = TextTone.PRIMARY,
        *,
        size: int | None = None,
        weight: int | None = None,
        wrap: bool = False,
        selectable: bool = False,
        tooltip_when_elided: bool = True,
        parent: QWidget | None = None,
    ) -> None:
        self._full_text = str(text)
        self._tooltip_when_elided = bool(tooltip_when_elided)
        super().__init__(
            "",
            role=role,
            tone=tone,
            size=size,
            weight=weight,
            wrap=wrap,
            selectable=selectable,
            parent=parent,
        )
        self.setText(text)

    @property
    def full_text(self) -> str:
        return self._full_text

    def setText(self, text: str) -> None:
        self._full_text = str(text)
        self._update_elision()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._update_elision()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._update_elision()

    def refresh_styles(self) -> None:
        super().refresh_styles()
        self._update_elision()

    def _update_elision(self) -> None:
        if not hasattr(self, "_full_text"):
            return
        if not self._full_text:
            super().setText("")
            self._sync_tooltip("")
            return

        width = self.width()
        if width <= 0:
            super().setText(self._full_text)
            self._sync_tooltip(self._full_text)
            return

        elided = self.fontMetrics().elidedText(
            self._full_text,
            Qt.TextElideMode.ElideRight,
            width,
        )
        super().setText(elided)
        self._sync_tooltip(self._full_text if elided != self._full_text else "")

    def _sync_tooltip(self, full_text: str) -> None:
        if full_text and self._tooltip_when_elided:
            if self.toolTip() != full_text:
                attach_tooltip(self, Tooltip(full_text, TooltipKind.STATE))
            return
        if self.toolTip():
            detach_tooltip(self)


__all__ = ["ElidedLabel"]
