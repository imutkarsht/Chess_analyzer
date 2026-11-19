# SPDX-License-Identifier: GPL-3.0-only
"""Shared QLayout clearing helper."""

from __future__ import annotations

from PyQt6.QtWidgets import QLayout


def clear_layout(layout: QLayout | None) -> None:
    """Remove all widgets and sub-layouts from a layout."""
    if layout is None:
        return

    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget:
            # Hide immediately: deleteLater can leave the old widget painted
            # above its replacement until the event loop processes the delete.
            widget.hide()
            widget.deleteLater()
        elif item.layout():
            clear_layout(item.layout())
