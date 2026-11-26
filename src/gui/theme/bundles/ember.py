# SPDX-License-Identifier: GPL-3.0-only
"""Ember theme: warm charcoal surfaces, cream text, and a copper accent.

Move-quality and termination colours stay in the amber/copper/coral family
and are light enough for readable text on the warm charcoal surface.
"""

from src.gui.theme.bundle import ThemeBundle
from src.gui.theme.palette import ThemePalette

EMBER_PALETTE = ThemePalette(
    background="#1C1816",
    surface="#2A2420",
    surface_light="#352C27",
    surface_card="#302823",
    border="#4A3D35",
    border_light="#5E4D42",
    highlight="#3A302A",
    text_primary="#F0E6DC",
    text_secondary="#CDBFAF",
    text_muted="#A89786",
    accent="#D97745",
    accent_hover="#E38A5A",
    accent_subtle="rgba(217, 119, 69, 0.16)",
    piece_white="#F2E8DE",
    piece_black="#14100D",
    board_highlight="#E8C15A",
    branch_colors=("#D97745", "#7FA7B8", "#A8B87A", "#B58AA5"),
    eval_bar_background="#3A302A",
    eval_bar_foreground="#F0E6DC",
    graph_grid="#3A302A",
    graph_pin="#E0A080",
    star_active="#EBCB8B",
    star_inactive="#5E4D42",
    star_active_subtle="rgba(235, 203, 139, 0.12)",
    crown="#EBCB8B",
    board_dim="#000000",
    move_dot_on_dark="rgba(240, 230, 220, 0.90)",
    move_dot_on_light="rgba(20, 16, 13, 0.85)",
    danger_hover="#C85A63",
    danger_pressed="#A94A53",
)

EMBER_CLASSIFICATION_COLORS = {
    "Brilliant": "#8FD1C0",
    "Great": "#8FB3D9",
    "Best": "#B5C98A",
    "Excellent": "#C9D98A",
    "Good": "#A8C29A",
    "Inaccuracy": "#EBCB8B",
    "Mistake": "#E0A080",
    "Blunder": "#F0A1A8",
    "Miss": "#F2A0A0",
    "Book": "#C9A5C7",
}

EMBER_TERMINATION_COLORS = {
    "Time": "#E0A080",
    "Draw": "#A89786",
    "3-Fold Repetition": "#8FB3D9",
    "Agreement": "#8FD1C0",
    "Stalemate": "#C9A5C7",
    "Insufficient vs Timeout": "#E0A080",
    "Insufficient Material": "#EBCB8B",
    "50-Move Rule": "#A89786",
}

EMBER_BUNDLE = ThemeBundle(
    id="ember",
    display_name="Ember",
    palette=EMBER_PALETTE,
    mode="dark",
    description="Warm charcoal theme with cream text and a copper accent.",
    owns_accent=True,
    classification_colors=EMBER_CLASSIFICATION_COLORS,
    termination_colors=EMBER_TERMINATION_COLORS,
    termination_fallback="#A89786",
)

__all__ = ["EMBER_BUNDLE", "EMBER_PALETTE"]
