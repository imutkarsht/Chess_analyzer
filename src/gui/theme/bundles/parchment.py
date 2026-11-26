# SPDX-License-Identifier: GPL-3.0-only
"""Parchment theme: warm paper surfaces, dark ink, and a rust accent.

Classification and termination colours are deliberately darker than the
default light palette so they stay readable on the cream surface.
"""

from src.gui.theme.bundle import ThemeBundle
from src.gui.theme.palette import ThemePalette

PARCHMENT_PALETTE = ThemePalette(
    background="#E8DCC6",
    surface="#F7F0E1",
    surface_light="#EFE5D2",
    surface_card="#F2E9D8",
    border="#C7B79B",
    border_light="#B4A486",
    highlight="#E0D3BB",
    text_primary="#2A241B",
    text_secondary="#5C5142",
    text_muted="#6F624F",
    accent="#B4441F",
    accent_hover="#9C3817",
    accent_subtle="rgba(180, 68, 31, 0.15)",
    piece_white="#F5EFE3",
    piece_black="#1F1A14",
    board_highlight="#E8C45A",
    branch_colors=("#B4441F", "#1F6FB2", "#356E4D", "#7B4B94"),
    eval_bar_background="#CBBBA0",
    eval_bar_foreground="#2A241B",
    graph_grid="#D3C4AA",
    graph_pin="#1F6FB2",
    star_active="#B07A00",
    star_inactive="#9C8D75",
    star_active_subtle="rgba(176, 122, 0, 0.12)",
    crown="#B07A00",
    board_dim="#000000",
    move_dot_on_dark="rgba(255, 255, 255, 0.90)",
    move_dot_on_light="rgba(31, 26, 20, 0.85)",
    danger_hover="#8F1B12",
    danger_pressed="#73150E",
)

PARCHMENT_CLASSIFICATION_COLORS = {
    "Brilliant": "#006F5D",
    "Great": "#1F6FB2",
    "Best": "#2F7A3B",
    "Excellent": "#426A16",
    "Good": "#356E4D",
    "Inaccuracy": "#8A5F00",
    "Mistake": "#A64A06",
    "Blunder": "#B42318",
    "Miss": "#C62828",
    "Book": "#7A5C3E",
}

PARCHMENT_TERMINATION_COLORS = {
    "Time": "#A64A06",
    "Draw": "#5C5142",
    "3-Fold Repetition": "#1F6FB2",
    "Agreement": "#006F5D",
    "Stalemate": "#7B4B94",
    "Insufficient vs Timeout": "#A64A06",
    "Insufficient Material": "#8A5F00",
    "50-Move Rule": "#6B5E4C",
}

PARCHMENT_BUNDLE = ThemeBundle(
    id="parchment",
    display_name="Parchment",
    palette=PARCHMENT_PALETTE,
    mode="light",
    description="Warm paper theme with dark ink and a rust accent.",
    owns_accent=True,
    classification_colors=PARCHMENT_CLASSIFICATION_COLORS,
    termination_colors=PARCHMENT_TERMINATION_COLORS,
    termination_fallback="#6B5E4C",
)

__all__ = ["PARCHMENT_BUNDLE", "PARCHMENT_PALETTE"]
