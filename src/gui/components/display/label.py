# SPDX-License-Identifier: GPL-3.0-only
"""Shared label with semantic typography and tone properties.

``Label`` deliberately owns no stylesheet. It publishes ``role``, ``tone``, and
optional ``size``/``weight`` properties; ``Styles.get_typography_qss`` turns
those into global rules. Theme and accent changes therefore recolour every
label without per-widget signal wiring.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QWidget

from src.gui.theme.typography import (
    ALLOWED_SIZES,
    ALLOWED_WEIGHTS,
    TextRole,
    TextTone,
)


class Label(QLabel):
    """A plain-text label driven by a semantic role and tone.

    Use raw ``QLabel`` for rich text, hyperlinks, pixmaps, clocks, and painted
    content. ``Label`` always renders plain text.
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
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(text, parent)
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setWordWrap(wrap)
        if selectable:
            self.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
                | Qt.TextInteractionFlag.TextSelectableByKeyboard
            )

        self._role = TextRole(role)
        self._tone = TextTone(tone)
        self._size = self._validate_size(size)
        self._weight = self._validate_weight(weight)
        self._apply_properties()

    @property
    def role(self) -> TextRole:
        return self._role

    @property
    def tone(self) -> TextTone:
        return self._tone

    def set_role(self, role: TextRole | str) -> None:
        role = TextRole(role)
        if role == self._role:
            return
        self._role = role
        self._apply_properties()
        self._repolish()

    def set_tone(self, tone: TextTone | str) -> None:
        tone = TextTone(tone)
        if tone == self._tone:
            return
        self._tone = tone
        self._apply_properties()
        self._repolish()

    def set_size(self, size: int | None) -> None:
        size = self._validate_size(size)
        if size == self._size:
            return
        self._size = size
        self._apply_properties()
        self._repolish()

    def set_weight(self, weight: int | None) -> None:
        weight = self._validate_weight(weight)
        if weight == self._weight:
            return
        self._weight = weight
        self._apply_properties()
        self._repolish()

    def refresh_styles(self) -> None:
        """Re-apply properties after an external palette/style change."""
        self._apply_properties()
        self._repolish()

    def _apply_properties(self) -> None:
        self.setProperty("role", self._role.value)
        self.setProperty("tone", self._tone.value)
        # ``size`` is a reserved QWidget property (QSize); use explicit names.
        self.setProperty("textSize", str(self._size) if self._size is not None else "")
        self.setProperty(
            "textWeight", str(self._weight) if self._weight is not None else ""
        )

    def _repolish(self) -> None:
        style = self.style()
        style.unpolish(self)
        style.polish(self)
        self.update()

    @staticmethod
    def _validate_size(size: int | None) -> int | None:
        if size is None:
            return None
        if size not in ALLOWED_SIZES:
            raise ValueError(f"Unsupported label size: {size}")
        return size

    @staticmethod
    def _validate_weight(weight: int | None) -> int | None:
        if weight is None:
            return None
        if weight not in ALLOWED_WEIGHTS:
            raise ValueError(f"Unsupported label weight: {weight}")
        return weight
