# SPDX-License-Identifier: GPL-3.0-only
"""High Contrast theme: pure black, white ink, yellow focus, and 2px borders.

This is the accessibility theme. Text and semantic colours aim for at least
7:1 contrast on the near-black surface, and focusable controls get an explicit
yellow focus border instead of a subtle tint change.
"""

from src.gui.theme.bundle import ThemeBundle
from src.gui.theme.palette import ThemePalette

HIGH_CONTRAST_PALETTE = ThemePalette(
    background="#000000",
    surface="#000000",
    surface_light="#141414",
    surface_card="#0A0A0A",
    border="#FFFFFF",
    border_light="#FFFFFF",
    highlight="#262626",
    text_primary="#FFFFFF",
    text_secondary="#E6E6E6",
    text_muted="#BFBFBF",
    accent="#FFD400",
    accent_hover="#FFE14D",
    accent_subtle="rgba(255, 212, 0, 0.18)",
    piece_white="#FFFFFF",
    piece_black="#000000",
    board_highlight="#FFD400",
    branch_colors=("#FFD400", "#66CCFF", "#66FF99", "#FF99CC"),
    eval_bar_background="#000000",
    eval_bar_foreground="#FFFFFF",
    graph_grid="#666666",
    graph_pin="#FFD400",
    star_active="#FFD400",
    star_inactive="#808080",
    star_active_subtle="rgba(255, 212, 0, 0.18)",
    crown="#FFD400",
    board_dim="#000000",
    move_dot_on_dark="rgba(255, 255, 255, 0.95)",
    move_dot_on_light="rgba(0, 0, 0, 0.90)",
    danger_hover="#CC0000",
    danger_pressed="#990000",
)

HIGH_CONTRAST_CLASSIFICATION_COLORS = {
    "Brilliant": "#00FFD0",
    "Great": "#66B3FF",
    "Best": "#33FF66",
    "Excellent": "#99FF66",
    "Good": "#66FF99",
    "Inaccuracy": "#FFFF00",
    "Mistake": "#FFA500",
    "Blunder": "#FF6B6B",
    "Miss": "#FF9A9A",
    "Book": "#FFCC99",
}

HIGH_CONTRAST_TERMINATION_COLORS = {
    "Time": "#FFA500",
    "Draw": "#BFBFBF",
    "3-Fold Repetition": "#66B3FF",
    "Agreement": "#00FFD0",
    "Stalemate": "#FF99CC",
    "Insufficient vs Timeout": "#FFA500",
    "Insufficient Material": "#FFFF00",
    "50-Move Rule": "#BFBFBF",
}

HIGH_CONTRAST_EXTRA_QSS = """
QPushButton,
QLineEdit,
QTextEdit,
QSpinBox,
QDoubleSpinBox {
    border-width: 2px;
}
QCheckBox::indicator,
QRadioButton::indicator {
    border-width: 2px;
}
QPushButton#ThemeCard,
QPushButton#ThemeCard:hover,
QPushButton#ThemeCard:focus,
QPushButton#ThemeCard:checked {
    border-width: 2px;
}
QLineEdit:focus,
QTextEdit:focus,
QSpinBox:focus,
QDoubleSpinBox:focus,
QPushButton:focus,
QToolButton:focus,
QCheckBox:focus,
QRadioButton:focus {
    border: 2px solid #FFD400;
}
"""

HIGH_CONTRAST_BUNDLE = ThemeBundle(
    id="high_contrast",
    display_name="High Contrast",
    palette=HIGH_CONTRAST_PALETTE,
    mode="dark",
    description="Maximum-contrast theme with 2px borders and a yellow focus accent.",
    owns_accent=True,
    classification_colors=HIGH_CONTRAST_CLASSIFICATION_COLORS,
    termination_colors=HIGH_CONTRAST_TERMINATION_COLORS,
    termination_fallback="#BFBFBF",
    extra_qss=HIGH_CONTRAST_EXTRA_QSS,
)

__all__ = ["HIGH_CONTRAST_BUNDLE", "HIGH_CONTRAST_PALETTE"]
