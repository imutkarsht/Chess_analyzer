# SPDX-License-Identifier: GPL-3.0-only
"""Themed checkbox used across the app.

Three variants cover the app's existing visual languages:

* ``DEFAULT`` - pill-shaped toggle beside analysis/explorer views
* ``FLAT`` - borderless settings-row toggle
* ``COMPACT`` - smaller flat toggle for dense panels and dialogs

All styling lives in the global QSS matrix via the ``checkboxVariant``
property; the component owns only variant state and theme refresh.
"""

from __future__ import annotations

from enum import StrEnum

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QCheckBox, QWidget

from src.gui.theme import ThemeManager


class CheckboxVariant(StrEnum):
    """Visual variants; all share the same tick indicator."""

    DEFAULT = "default"
    FLAT = "flat"
    COMPACT = "compact"


class Checkbox(QCheckBox):
    """The app's only checkbox; styling and theme refresh live here."""

    def __init__(
        self,
        text: str = "",
        variant: CheckboxVariant | str = CheckboxVariant.DEFAULT,
        *,
        visual_only: bool = False,
        max_width: int | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(text, parent)
        self._variant = CheckboxVariant(variant)
        self._visual_only = bool(visual_only)

        if self._visual_only:
            self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        else:
            self.setCursor(Qt.CursorShape.PointingHandCursor)

        if max_width is not None:
            self.setMaximumWidth(max_width)

        manager = ThemeManager.instance()
        manager.theme_changed.connect(self._on_theme_changed)
        manager.accent_changed.connect(self._on_theme_changed)
        self.refresh_styles()

    @property
    def variant(self) -> CheckboxVariant:
        return self._variant

    def set_variant(self, variant: CheckboxVariant | str) -> None:
        self._variant = CheckboxVariant(variant)
        self.refresh_styles()

    def refresh_styles(self) -> None:
        """Publish the variant property; the global matrix owns the styling."""
        self.setProperty("checkboxVariant", self._variant.value)
        self.style().unpolish(self)
        self.style().polish(self)

    def _on_theme_changed(self, *_args) -> None:
        self.refresh_styles()


__all__ = ["Checkbox", "CheckboxVariant"]
