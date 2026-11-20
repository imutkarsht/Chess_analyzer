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
            # Hide and detach immediately: deleteLater alone leaves the old
            # widget as a child until the event loop runs, which can duplicate
            # rows during synchronous refresh/test paths and paint stale UI.
            widget.hide()
            widget.setParent(None)
            widget.deleteLater()
        elif item.layout():
            clear_layout(item.layout())
