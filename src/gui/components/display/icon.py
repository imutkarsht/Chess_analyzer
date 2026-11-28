# SPDX-License-Identifier: GPL-3.0-only
"""Shared icon widget facade."""

from __future__ import annotations

from dataclasses import replace

from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import QWidget

from src.gui.components.display.icon_label import IconLabel
from src.gui.icons import IconSpec, IconVariant


class Icon(IconLabel):
    """Icon widget with an explicit pack variant.

    ``IconLabel`` remains the compatibility surface; new UI code should use
    this class when it needs to choose a variant.
    """

    def __init__(
        self,
        icon: str | QIcon | QPixmap | IconSpec | None = None,
        *,
        variant: IconVariant | str | None = None,
        parent: QWidget | None = None,
        **kwargs,
    ) -> None:
        if isinstance(icon, IconSpec) and variant is not None:
            icon = replace(icon, variant=variant)
        super().__init__(icon, variant=variant, parent=parent, **kwargs)
