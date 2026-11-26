# SPDX-License-Identifier: GPL-3.0-only
"""Sage theme: soft stone-green surfaces, forest ink, and a moss accent.

The classification and termination palettes use darker forest, moss, and
earth tones so move quality stays readable on the pale sage surface.
"""

from src.gui.theme.bundle import ThemeBundle
from src.gui.theme.palette import ThemePalette

SAGE_PALETTE = ThemePalette(
    background="#DCE3D8",
    surface="#EEF2EA",
    surface_light="#E4EADF",
    surface_card="#E8EEE3",
    border="#B9C4B2",
    border_light="#A6B29E",
    highlight="#D5DECE",
    text_primary="#1F2A22",
    text_secondary="#4C5A4F",
    text_muted="#63725F",
    accent="#4F7A4A",
    accent_hover="#3F633C",
    accent_subtle="rgba(79, 122, 74, 0.15)",
    piece_white="#F4F7F0",
    piece_black="#172019",
    board_highlight="#E7D36B",
    branch_colors=("#4F7A4A", "#2F6D9E", "#8A5A2B", "#6F4C8A"),
    eval_bar_background="#C3CDBD",
    eval_bar_foreground="#1F2A22",
    graph_grid="#C9D3C2",
    graph_pin="#2F6D9E",
    star_active="#A97A00",
    star_inactive="#8A9884",
    star_active_subtle="rgba(169, 122, 0, 0.12)",
    crown="#A97A00",
    board_dim="#000000",
    move_dot_on_dark="rgba(255, 255, 255, 0.90)",
    move_dot_on_light="rgba(23, 32, 25, 0.85)",
    danger_hover="#8F1B12",
    danger_pressed="#73150E",
)

SAGE_CLASSIFICATION_COLORS = {
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

SAGE_TERMINATION_COLORS = {
    "Time": "#A64A06",
    "Draw": "#4C5A4F",
    "3-Fold Repetition": "#1F6FB2",
    "Agreement": "#006F5D",
    "Stalemate": "#6F4C8A",
    "Insufficient vs Timeout": "#A64A06",
    "Insufficient Material": "#8A5F00",
    "50-Move Rule": "#5A675C",
}

SAGE_BUNDLE = ThemeBundle(
    id="sage",
    display_name="Sage",
    palette=SAGE_PALETTE,
    mode="light",
    description="Soft sage theme with forest ink and a moss accent.",
    owns_accent=True,
    classification_colors=SAGE_CLASSIFICATION_COLORS,
    termination_colors=SAGE_TERMINATION_COLORS,
    termination_fallback="#5A675C",
)

__all__ = ["SAGE_BUNDLE", "SAGE_PALETTE"]
