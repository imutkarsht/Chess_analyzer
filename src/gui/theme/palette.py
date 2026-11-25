from dataclasses import dataclass

from src.gui.theme.color_math import (
    blend_hex,
    on_color,
    readable_color,
    relative_luminance,
    rgba,
)


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
    branch_colors: tuple[str, ...] = (
        "#FF9F0A",
        "#64D2FF",
        "#30D158",
        "#BF5AF2",
    )

    # Component colours that are independent of the classification palette.
    eval_bar_background: str = "#404040"
    eval_bar_foreground: str = "#FFFFFF"
    graph_grid: str = "#444444"
    graph_pin: str = "#00E5FF"
    star_active: str = "#FFB800"
    star_inactive: str = "#4B5563"
    star_active_subtle: str = "rgba(255, 184, 0, 0.1)"
    crown: str = "#EAB308"
    board_dim: str = "#000000"
    move_dot_on_dark: str = "rgba(255,255,255,0.90)"
    move_dot_on_light: str = "rgba(0,0,0,0.85)"
    # Destructive-action shades for the danger button states. The resting
    # danger colour resolves through the classification palette (Blunder);
    # these two cover the pressed/hover ramps the QSS matrix needs.
    danger_hover: str = "#B01020"
    danger_pressed: str = "#900010"

    def with_accent(self, hex_color: str) -> "ThemePalette":
        ui_accent = readable_color(hex_color, self.surface)
        hover_target = "#FFFFFF" if relative_luminance(self.surface) < 0.5 else "#000000"
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
            accent_hover=blend_hex(ui_accent, hover_target, 0.12),
            accent_subtle=rgba(ui_accent, 0.15),
            piece_white=self.piece_white,
            piece_black=self.piece_black,
            board_highlight=self.board_highlight,
            branch_colors=self.branch_colors,
            eval_bar_background=self.eval_bar_background,
            eval_bar_foreground=self.eval_bar_foreground,
            graph_grid=self.graph_grid,
            graph_pin=self.graph_pin,
            star_active=self.star_active,
            star_inactive=self.star_inactive,
            star_active_subtle=self.star_active_subtle,
            crown=self.crown,
            board_dim=self.board_dim,
            move_dot_on_dark=self.move_dot_on_dark,
            move_dot_on_light=self.move_dot_on_light,
            danger_hover=self.danger_hover,
            danger_pressed=self.danger_pressed,
        )

    @property
    def ui_accent(self) -> str:
        """Accent adjusted for readable text, icons, and borders."""
        return readable_color(self.accent, self.surface)

    @property
    def on_accent(self) -> str:
        """Black or white ink for text placed on the adjusted accent."""
        return on_color(self.ui_accent)

    # ------------------------------------------------------------------
    # Tooltip surface
    # ------------------------------------------------------------------
    # Tooltips invert the interface: a near-black bubble on light themes and
    # a near-white bubble on dark themes. Deriving both from ``text_primary``
    # keeps custom bundles consistent without adding per-theme constants.
    @property
    def tooltip_surface(self) -> str:
        return self.text_primary

    @property
    def tooltip_text(self) -> str:
        return on_color(self.text_primary)

    @property
    def tooltip_border(self) -> str:
        """Hairline that keeps the inverted bubble legible on any surface."""
        return rgba(self.tooltip_text, 0.12)

    @property
    def tooltip_shadow(self) -> str:
        """Shadow ink; alpha is resolved by ``tooltip_shadow_alpha``."""
        return self.piece_black

    @property
    def tooltip_shadow_alpha(self) -> float:
        """Stronger shadow on dark surfaces where contrast is scarce."""
        return 0.30 if relative_luminance(self.background) > 0.5 else 0.58


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
    branch_colors=("#FF9F0A", "#64D2FF", "#30D158", "#BF5AF2"),
)

LIGHT = ThemePalette(
    background="#EAEAEF",
    surface="#FFFFFF",
    surface_light="#F0F0F4",
    surface_card="#FFFFFF",
    border="#C9C9D1",
    border_light="#B4B4BE",
    highlight="#E2E2E8",
    text_primary="#1D1D1F",
    text_secondary="#55555C",
    text_muted="#66666C",
    accent="#FF9500",
    accent_hover="#E08600",
    accent_subtle="rgba(255, 149, 0, 0.18)",
    piece_white="#F0F0F0",
    piece_black="#111111",
    board_highlight="#F7EC74",
    branch_colors=("#C76A00", "#007AFF", "#248A3D", "#8944AB"),
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

TERMINATION_COLORS = {
    "Time": "#E67E22",
    "Draw": "#888888",
    "3-Fold Repetition": "#3498DB",
    "Agreement": "#1ABC9C",
    "Stalemate": "#9B59B6",
    "Insufficient vs Timeout": "#E67E22",
    "Insufficient Material": "#F1C40F",
    "50-Move Rule": "#95A5A6",
}
TERMINATION_FALLBACK_COLOR = "#888888"

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
