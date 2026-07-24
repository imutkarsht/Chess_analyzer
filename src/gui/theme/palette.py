from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ThemePalette:
    background: str
    surface: str
    surface_light: str
    surface_card: str
    border: str
    border_light: str
    highlight: str
    text_primary: str
    text_secondary: str
    text_muted: str
    accent: str = "#FF9500"
    accent_hover: str = "#FFB340"
    accent_subtle: str = "rgba(255, 149, 0, 0.15)"

    piece_white: str = "#F0F0F0"
    piece_black: str = "#111111"
    board_highlight: str = "#F7EC74"

    def with_accent(self, hex_color: str) -> "ThemePalette":
        r = int(hex_color[1:3], 16)
        g = int(hex_color[3:5], 16)
        b = int(hex_color[5:7], 16)
        subtle = f"rgba({r}, {g}, {b}, 0.15)"
        return ThemePalette(
            background=self.background,
            surface=self.surface,
            surface_light=self.surface_light,
            surface_card=self.surface_card,
            border=self.border,
            border_light=self.border_light,
            highlight=self.highlight,
            text_primary=self.text_primary,
            text_secondary=self.text_secondary,
            text_muted=self.text_muted,
            accent=hex_color,
            accent_hover=hex_color,
            accent_subtle=subtle,
            piece_white=self.piece_white,
            piece_black=self.piece_black,
            board_highlight=self.board_highlight,
        )


DARK = ThemePalette(
    background="#1A1A1D",
    surface="#252529",
    surface_light="#2E2E33",
    surface_card="#2A2A2E",
    border="#3E3E45",
    border_light="#4A4A52",
    highlight="#3A3A40",
    text_primary="#E4E4E7",
    text_secondary="#9CA3AF",
    text_muted="#6B7280",
    accent="#FF9500",
    accent_hover="#FFB340",
    accent_subtle="rgba(255, 149, 0, 0.15)",
    piece_white="#F0F0F0",
    piece_black="#111111",
    board_highlight="#F7EC74",
)

LIGHT = ThemePalette(
    background="#F5F5F7",
    surface="#FFFFFF",
    surface_light="#EBEBED",
    surface_card="#F0F0F2",
    border="#C7C7CC",
    border_light="#B0B0B5",
    highlight="#DCDCE0",
    text_primary="#1D1D1F",
    text_secondary="#6E6E73",
    text_muted="#8E8E93",
    accent="#FF9500",
    accent_hover="#E08600",
    accent_subtle="rgba(255, 149, 0, 0.15)",
    piece_white="#F0F0F0",
    piece_black="#111111",
    board_highlight="#F7EC74",
)

CLASSIFICATION_COLORS = {
    "Brilliant": "#00D4AA",
    "Great": "#4CACEB",
    "Best": "#3AAA55",
    "Excellent": "#6BBF3E",
    "Good": "#4CAF76",
    "Inaccuracy": "#F1C40F",
    "Mistake": "#E67E22",
    "Blunder": "#D02030",
    "Miss": "#FF5252",
    "Book": "#B8956E",
}

BOARD_THEMES = {
    "Green": {"dark": "#769656", "light": "#EEEED2"},
    "Blue": {"dark": "#4B7399", "light": "#E0E0E0"},
    "Brown": {"dark": "#B58863", "light": "#F0D9B5"},
    "Gray": {"dark": "#888888", "light": "#E0E0E0"},
    "Purple": {"dark": "#9b59b6", "light": "#ecf0f1"},
    "Teal": {"dark": "#1abc9c", "light": "#ffffff"},
    "Cherry": {"dark": "#c0392b", "light": "#ecf0f1"},
    "Neon": {"dark": "dynamic", "light": "#E0E0E0"},
}
