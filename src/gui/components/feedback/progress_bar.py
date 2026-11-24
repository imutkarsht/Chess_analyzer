# SPDX-License-Identifier: GPL-3.0-only
"""Themed progress bar for downloads and long-running setup work.

Two variants cover the app's existing bars: the standard labelled bar and the
thin accent-only bar used by update and splash screens. ``indeterminate``
switches the bar into busy mode.
"""

from __future__ import annotations

from enum import StrEnum

from PyQt6.QtWidgets import QProgressBar, QWidget

from src.gui.theme import ThemeManager


class ProgressBarVariant(StrEnum):
    """Visual variants for the shared progress bar."""

    DEFAULT = "default"
    THIN = "thin"


class ProgressBar(QProgressBar):
    """The app's only progress bar; styling and theme refresh live here."""

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        variant: ProgressBarVariant | str = ProgressBarVariant.DEFAULT,
        indeterminate: bool = False,
        text_visible: bool | None = None,
    ) -> None:
        super().__init__(parent)
        self._variant = ProgressBarVariant(variant)

        if self._variant is ProgressBarVariant.THIN:
            self.setFixedHeight(6)
        self.setTextVisible(
            self._variant is not ProgressBarVariant.THIN
            if text_visible is None
            else text_visible
        )
        if indeterminate:
            self.setRange(0, 0)

        manager = ThemeManager.instance()
        manager.theme_changed.connect(self._on_theme_changed)
        manager.accent_changed.connect(self._on_theme_changed)
        self.refresh_styles()

    @property
    def variant(self) -> ProgressBarVariant:
        return self._variant

    def refresh_styles(self) -> None:
        """Publish the variant property; the global matrix owns the styling."""
        self.setProperty("progressVariant", self._variant.value)
        self.style().unpolish(self)
        self.style().polish(self)

    def _on_theme_changed(self, *_args) -> None:
        self.refresh_styles()


__all__ = ["ProgressBar", "ProgressBarVariant"]
