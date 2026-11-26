# SPDX-License-Identifier: GPL-3.0-only
"""Nord theme: cool blue-grey surfaces with a frost-blue accent.

Move-quality and termination colours are remapped onto Nord's muted palette
and lightened where needed for readable text on the blue-grey surface.
"""

from src.gui.theme.bundle import ThemeBundle
from src.gui.theme.palette import ThemePalette

NORD_PALETTE = ThemePalette(
    background="#2E3440",
    surface="#3B4252",
    surface_light="#434C5E",
    surface_card="#353C4A",
    border="#4C566A",
    border_light="#5E6A80",
    highlight="#434C5E",
    text_primary="#ECEFF4",
    text_secondary="#C8D0DE",
    text_muted="#A8B3C6",
    accent="#88C0D0",
    accent_hover="#9FD3E0",
    accent_subtle="rgba(136, 192, 208, 0.16)",
    piece_white="#ECEFF4",
    piece_black="#1B222C",
    board_highlight="#EBCB8B",
    branch_colors=("#BF616A", "#88C0D0", "#A3BE8C", "#B48EAD"),
    eval_bar_background="#434C5E",
    eval_bar_foreground="#ECEFF4",
    graph_grid="#434C5E",
    graph_pin="#88C0D0",
    star_active="#EBCB8B",
    star_inactive="#5E6A80",
    star_active_subtle="rgba(235, 203, 139, 0.12)",
    crown="#EBCB8B",
    board_dim="#000000",
    move_dot_on_dark="rgba(236, 239, 244, 0.90)",
    move_dot_on_light="rgba(27, 34, 44, 0.85)",
    danger_hover="#C85A63",
    danger_pressed="#A94A53",
)

NORD_CLASSIFICATION_COLORS = {
    "Brilliant": "#8FBCBB",
    "Great": "#8FB3D9",
    "Best": "#A3BE8C",
    "Excellent": "#B5D48A",
    "Good": "#8FBC8F",
    "Inaccuracy": "#EBCB8B",
    "Mistake": "#E0A080",
    "Blunder": "#F0A1A8",
    "Miss": "#EF9AA2",
    "Book": "#C9A5C7",
}

NORD_TERMINATION_COLORS = {
    "Time": "#E0A080",
    "Draw": "#A8B3C6",
    "3-Fold Repetition": "#8FB3D9",
    "Agreement": "#8FBCBB",
    "Stalemate": "#C9A5C7",
    "Insufficient vs Timeout": "#E0A080",
    "Insufficient Material": "#EBCB8B",
    "50-Move Rule": "#A8B3C6",
}

NORD_BUNDLE = ThemeBundle(
    id="nord",
    display_name="Nord",
    palette=NORD_PALETTE,
    mode="dark",
    description="Cool blue-grey theme with a frost-blue accent.",
    owns_accent=True,
    classification_colors=NORD_CLASSIFICATION_COLORS,
    termination_colors=NORD_TERMINATION_COLORS,
    termination_fallback="#A8B3C6",
)

__all__ = ["NORD_BUNDLE", "NORD_PALETTE"]
