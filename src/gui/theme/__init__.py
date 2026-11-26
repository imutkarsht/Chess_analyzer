from src.gui.theme.bundle import ThemeBundle
from src.gui.theme.bundles.dark import DARK_BUNDLE
from src.gui.theme.bundles.dracula import DRACULA_BUNDLE
from src.gui.theme.bundles.light import LIGHT_BUNDLE
from src.gui.theme.bundles.nord import NORD_BUNDLE
from src.gui.theme.bundles.oled import OLED_BUNDLE
from src.gui.theme.bundles.parchment import PARCHMENT_BUNDLE
from src.gui.theme.manager import ELEVATIONS, Elevation, ThemeManager
from src.gui.theme.motion import Motion, MotionDuration, MotionEasing
from src.gui.theme.palette import (
    ACCENT_PRESETS,
    BOARD_THEMES,
    CLASSIFICATION_COLORS,
    DARK,
    LIGHT,
    AccentPreset,
    ThemePalette,
)
from src.gui.theme.system import OSThemeWatcher, get_system_accent
from src.gui.theme.tokens import Radius, Spacing, TypeScale
from src.gui.theme.typography import (
    ALLOWED_SIZES,
    ALLOWED_WEIGHTS,
    MONO_FAMILIES,
    ROLE_SPECS,
    RoleSpec,
    TextRole,
    TextTone,
)

for _bundle in (
    DARK_BUNDLE,
    LIGHT_BUNDLE,
    DRACULA_BUNDLE,
    OLED_BUNDLE,
    PARCHMENT_BUNDLE,
    NORD_BUNDLE,
):
    ThemeManager.register_bundle(_bundle)

__all__ = [
    "ACCENT_PRESETS",
    "AccentPreset",
    "BOARD_THEMES",
    "CLASSIFICATION_COLORS",
    "DARK",
    "ELEVATIONS",
    "Elevation",
    "LIGHT",
    "Motion",
    "MotionDuration",
    "MotionEasing",
    "OSThemeWatcher",
    "Radius",
    "Spacing",
    "ThemeBundle",
    "ThemeManager",
    "ThemePalette",
    "TypeScale",
    "get_system_accent",
    "ALLOWED_SIZES",
    "ALLOWED_WEIGHTS",
    "MONO_FAMILIES",
    "ROLE_SPECS",
    "RoleSpec",
    "TextRole",
    "TextTone",
]
