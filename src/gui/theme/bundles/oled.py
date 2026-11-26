# SPDX-License-Identifier: GPL-3.0-only
"""OLED Black theme: a pure-black palette for OLED displays.

This bundle is the proof that a new theme is one file plus one
``register_bundle`` call — it overrides only the palette and inherits the
classification, termination, and board-theme defaults.
"""

from src.gui.theme.bundle import ThemeBundle
from src.gui.theme.palette import DARK, ThemePalette

OLED_PALETTE = ThemePalette(
    background="#000000",
    surface="#0A0A0A",
    surface_light="#141414",
    surface_card="#101010",
    border="#262626",
    border_light="#333333",
    highlight="#1E1E1E",
    text_primary="#F2F2F2",
    text_secondary="#A3A3A3",
    text_muted="#737373",
    accent=DARK.accent,
    accent_hover=DARK.accent_hover,
    accent_subtle=DARK.accent_subtle,
    piece_white=DARK.piece_white,
    piece_black=DARK.piece_black,
    board_highlight=DARK.board_highlight,
    branch_colors=DARK.branch_colors,
)

OLED_BUNDLE = ThemeBundle(
    id="oled",
    display_name="OLED Black",
    palette=OLED_PALETTE,
    mode="dark",
    description="Pure-black theme for OLED displays.",
)

__all__ = ["OLED_BUNDLE"]
