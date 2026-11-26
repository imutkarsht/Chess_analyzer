# SPDX-License-Identifier: GPL-3.0-only
"""Dracula theme: the classic purple-on-charcoal palette.

Official Dracula colours: background ``#282A36``, current line ``#44475A``,
foreground ``#F8F8F2``, comment ``#6272A4``, plus cyan/green/orange/pink/
purple/red/yellow accents. The classification and termination palettes are
remapped onto those accents so move quality stays readable and on-theme.
"""

from src.gui.theme.bundle import ThemeBundle
from src.gui.theme.palette import ThemePalette

DRACULA_BACKGROUND = "#282A36"
DRACULA_CURRENT_LINE = "#44475A"
DRACULA_FOREGROUND = "#F8F8F2"
DRACULA_COMMENT = "#6272A4"
DRACULA_CYAN = "#8BE9FD"
DRACULA_GREEN = "#50FA7B"
DRACULA_ORANGE = "#FFB86C"
DRACULA_PINK = "#FF79C6"
DRACULA_PURPLE = "#BD93F9"
DRACULA_RED = "#FF5555"
DRACULA_YELLOW = "#F1FA8C"

DRACULA_PALETTE = ThemePalette(
    background=DRACULA_BACKGROUND,
    surface="#30323F",
    surface_light=DRACULA_CURRENT_LINE,
    surface_card="#2C2E3B",
    border=DRACULA_CURRENT_LINE,
    border_light=DRACULA_COMMENT,
    highlight=DRACULA_CURRENT_LINE,
    text_primary=DRACULA_FOREGROUND,
    text_secondary="#BFC2D9",
    text_muted=DRACULA_COMMENT,
    accent=DRACULA_PURPLE,
    accent_hover="#D6B8FF",
    accent_subtle="rgba(189, 147, 249, 0.15)",
    piece_white=DRACULA_FOREGROUND,
    piece_black="#191A21",
    board_highlight=DRACULA_YELLOW,
    branch_colors=(
        DRACULA_PINK,
        DRACULA_CYAN,
        DRACULA_GREEN,
        DRACULA_ORANGE,
    ),
    eval_bar_background=DRACULA_CURRENT_LINE,
    eval_bar_foreground=DRACULA_FOREGROUND,
    graph_grid=DRACULA_CURRENT_LINE,
    graph_pin=DRACULA_CYAN,
    star_active=DRACULA_YELLOW,
    star_inactive=DRACULA_COMMENT,
    star_active_subtle="rgba(241, 250, 140, 0.12)",
    crown=DRACULA_ORANGE,
    board_dim="#000000",
    move_dot_on_dark="rgba(248,248,242,0.90)",
    move_dot_on_light="rgba(25,26,33,0.85)",
)

DRACULA_CLASSIFICATION_COLORS = {
    "Brilliant": DRACULA_CYAN,
    "Great": DRACULA_PURPLE,
    "Best": DRACULA_GREEN,
    "Excellent": "#69FF94",
    "Good": "#8BE9A0",
    "Inaccuracy": DRACULA_YELLOW,
    "Mistake": DRACULA_ORANGE,
    "Blunder": DRACULA_RED,
    "Miss": DRACULA_PINK,
    "Book": DRACULA_COMMENT,
}

DRACULA_TERMINATION_COLORS = {
    "Time": DRACULA_ORANGE,
    "Draw": DRACULA_COMMENT,
    "3-Fold Repetition": DRACULA_CYAN,
    "Agreement": DRACULA_GREEN,
    "Stalemate": DRACULA_PURPLE,
    "Insufficient vs Timeout": DRACULA_ORANGE,
    "Insufficient Material": DRACULA_YELLOW,
    "50-Move Rule": DRACULA_COMMENT,
}

DRACULA_BUNDLE = ThemeBundle(
    id="dracula",
    display_name="Dracula",
    palette=DRACULA_PALETTE,
    mode="dark",
    description="Dark purple-on-charcoal theme with vivid move-quality colours.",
    owns_accent=True,
    classification_colors=DRACULA_CLASSIFICATION_COLORS,
    termination_colors=DRACULA_TERMINATION_COLORS,
    termination_fallback=DRACULA_COMMENT,
)

__all__ = ["DRACULA_BUNDLE", "DRACULA_PALETTE"]
