# SPDX-License-Identifier: GPL-3.0-only
"""Lazy-rendered metric sub-view base."""

from __future__ import annotations

from PyQt6.QtWidgets import QVBoxLayout, QWidget

from src.gui.styles import Styles


class LazyRenderView(QWidget):
    """A transparent page that renders only when made visible and dirty."""

    def __init__(self, parent: QWidget | None = None, *, spacing: int = 12) -> None:
        super().__init__(parent)
        Styles.apply_transparent(self, borderless=False)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(spacing)
        self._dirty = True

    def mark_dirty(self) -> None:
        self._dirty = True

    def ensure_rendered(self) -> None:
        if not self._dirty:
            return
        self._render()
        self._dirty = False

    def _render(self) -> None:
        raise NotImplementedError
