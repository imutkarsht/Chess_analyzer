# SPDX-License-Identifier: GPL-3.0-only
"""Theme token utilities: accuracy, classification, board colors, and accent."""

from __future__ import annotations

from src.constants import DEFAULT_BOARD_THEME
from src.gui.theme import ThemeManager


class _TokensMixin:
    @classmethod
    def get_accuracy_color(cls, accuracy: float) -> str:
        acc = max(0.0, min(100.0, float(accuracy)))
        if acc <= 50.0:
            t = acc / 50.0
            r = int(0xD0 + (0xF1 - 0xD0) * t)
            g = int(0x20 + (0xC4 - 0x20) * t)
            b = int(0x30 + (0x0F - 0x30) * t)
        elif acc <= 75.0:
            t = (acc - 50.0) / 25.0
            r = int(0xF1 + (0x2E - 0xF1) * t)
            g = int(0xC4 + (0xCC - 0xC4) * t)
            b = int(0x0F + (0x71 - 0x0F) * t)
        else:
            t = (acc - 75.0) / 25.0
            r = int(0x2E + (0x00 - 0x2E) * t)
            g = int(0xCC + (0xD4 - 0xCC) * t)
            b = int(0x71 + (0xAA - 0x71) * t)
        return f"#{r:02X}{g:02X}{b:02X}"

    @classmethod
    def set_accent_color(cls, color_hex):
        ThemeManager.set_accent(color_hex)

    @classmethod
    def get_class_color(cls, classification: str) -> str:
        return ThemeManager.get_class_color(classification)

    @classmethod
    def get_board_colors(cls, theme_name=DEFAULT_BOARD_THEME):
        return ThemeManager.get_board_colors(theme_name)
