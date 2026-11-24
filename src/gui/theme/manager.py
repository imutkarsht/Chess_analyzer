from dataclasses import dataclass

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QGraphicsDropShadowEffect

from src.constants import DEFAULT_ACCENT, DEFAULT_BOARD_THEME
from src.gui.theme.bundle import ThemeBundle
from src.gui.theme.palette import BOARD_THEMES, CLASSIFICATION_COLORS, DARK, LIGHT, ThemePalette
from src.gui.theme.system import OSThemeWatcher, get_system_accent
from src.gui.utils.assets import tick_icon_path


@dataclass
class Elevation:
    blur_radius: int
    x_offset: int
    y_offset: int
    opacity: int


def _rgba(hex_color: str, alpha: float) -> str:
    """Convert a hex token to a QSS rgba() string for translucent states."""
    color = QColor(hex_color)
    return f"rgba({color.red()}, {color.green()}, {color.blue()}, {alpha:.2f})"


ELEVATIONS = {
    0: Elevation(0, 0, 0, 0),
    1: Elevation(10, 0, 2, 40),
    2: Elevation(16, 0, 4, 60),
    3: Elevation(24, 0, 8, 80),
}


class ThemeManager(QObject):
    theme_changed = pyqtSignal(str)
    accent_changed = pyqtSignal(str)

    _instance: "ThemeManager | None" = None

    _current_mode: str = "dark"
    _theme_mode: str = "system"  # "system" | dark/light | a bundle id
    _palette: ThemePalette = DARK
    _accent: str = DEFAULT_ACCENT
    _accent_mode: str = "system"  # "system" | "manual"
    _style_revision: int = 0
    _os_watcher: OSThemeWatcher | None = None

    # id -> ThemeBundle; built-ins are registered in theme/__init__.py.
    _bundles: dict[str, "ThemeBundle"] = {}
    _active_bundle_id: str | None = None

    def __init__(self, parent=None):
        super().__init__(parent)
        ThemeManager._instance = self
        self._os_watcher = OSThemeWatcher(self)
        self._os_watcher.color_scheme_changed.connect(self._on_os_scheme_changed)

    def _on_os_scheme_changed(self, mode: str):
        if self._theme_mode == "system":
            self.set_mode(mode)

    @classmethod
    def instance(cls) -> "ThemeManager":
        if cls._instance is not None:
            try:
                cls._instance.objectName()
            except RuntimeError:
                cls._instance = None

        if cls._instance is None:
            cls._instance = ThemeManager()
        return cls._instance

    @classmethod
    def palette(cls) -> ThemePalette:
        return cls._palette

    @classmethod
    def mode(cls) -> str:
        return cls._current_mode

    @classmethod
    def theme_mode(cls) -> str:
        return cls._theme_mode

    @classmethod
    def accent(cls) -> str:
        return cls._accent

    @classmethod
    def accent_mode(cls) -> str:
        return cls._accent_mode

    @classmethod
    def style_revision(cls) -> int:
        """Monotonic counter bumped whenever generated styles can change."""
        return cls._style_revision

    @classmethod
    def _bump_style_revision(cls) -> None:
        cls._style_revision += 1

    # ------------------------------------------------------------------
    # Theme bundle registry
    # ------------------------------------------------------------------
    @classmethod
    def register_bundle(cls, bundle: "ThemeBundle") -> None:
        """Register a theme bundle. Safe to call at import time from plugins."""
        cls._bundles[bundle.id] = bundle

    @classmethod
    def registered_bundles(cls) -> dict[str, "ThemeBundle"]:
        """All registered bundles, keyed by id (copy; mutate the registry only
        through register_bundle)."""
        return dict(cls._bundles)

    @classmethod
    def active_bundle_id(cls) -> str | None:
        return cls._active_bundle_id

    @classmethod
    def _active_bundle(cls) -> "ThemeBundle | None":
        if cls._active_bundle_id is None:
            return None
        return cls._bundles.get(cls._active_bundle_id)

    @classmethod
    def _palette_for_bundle(cls, bundle: "ThemeBundle", accent: str) -> ThemePalette:
        """Resolve a bundle palette, honouring accent-aware factories."""
        if bundle.palette_factory is not None:
            return bundle.palette_factory(accent)
        if bundle.owns_accent and accent == bundle.palette.accent:
            # Keep the signature accent ramp (hover/subtle) intact.
            return bundle.palette
        return bundle.palette.with_accent(accent)

    @classmethod
    def set_bundle(cls, bundle_id: str) -> None:
        """Activate a registered bundle by id and emit ``theme_changed``."""
        bundle = cls._bundles.get(bundle_id)
        if bundle is None:
            from src.utils.logger import logger

            logger.warning(f"ThemeManager: unknown bundle id '{bundle_id}'")
            return
        cls._active_bundle_id = bundle_id
        cls._theme_mode = bundle_id
        cls._current_mode = bundle.mode
        if bundle.owns_accent:
            cls._accent = bundle.palette.accent
        cls._palette = cls._palette_for_bundle(bundle, cls._accent)
        cls._bump_style_revision()
        cls.apply_app_stylesheet()
        cls.instance().theme_changed.emit(bundle_id)

    @classmethod
    def get_class_color(cls, classification: str) -> str:
        bundle = cls._active_bundle()
        colors = bundle.classification_colors if bundle else CLASSIFICATION_COLORS
        return colors.get(classification, cls._palette.text_primary)

    @classmethod
    def get_board_colors(cls, theme_name: str = DEFAULT_BOARD_THEME) -> dict:
        bundle = cls._active_bundle()
        board_themes = bundle.board_themes if bundle else BOARD_THEMES
        theme = board_themes.get(theme_name) or board_themes.get(DEFAULT_BOARD_THEME) or {}
        fallback = BOARD_THEMES[DEFAULT_BOARD_THEME]
        dark = theme.get("dark") or fallback["dark"]
        light = theme.get("light") or fallback["light"]
        if dark == "dynamic":
            dark = cls._accent
        return {"dark": dark, "light": light}

    @classmethod
    def set_theme_mode(cls, mode: str):
        """Set theme mode: 'system', 'dark', 'light', or a bundle id."""
        cls._theme_mode = mode
        if mode == "system":
            detected = OSThemeWatcher.current_scheme()
            cls.set_mode(detected)
        elif mode in cls._bundles:
            cls.set_bundle(mode)
        else:
            cls.set_mode(mode)

    @classmethod
    def apply_app_stylesheet(cls):
        """Compiles and applies the central QSS theme template globally to QApplication.

        The template and generated typography rules are loaded independently so
        a packaging mistake that loses the template can never wipe out all font
        styling again.
        """
        import os

        from PyQt6.QtWidgets import QApplication

        from src.gui.styles import Styles
        from src.utils.logger import logger
        from src.utils.path_utils import get_resource_path

        qss_path = os.path.join(os.path.dirname(__file__), "theme_template.qss")
        if not os.path.exists(qss_path):
            qss_path = get_resource_path("src/gui/theme/theme_template.qss")

        template_qss = ""
        try:
            with open(qss_path, encoding="utf-8") as f:
                template = f.read()

            p = cls._palette
            tick_path = tick_icon_path()

            template_qss = template.format(
                BACKGROUND=p.background,
                SURFACE=p.surface,
                SURFACE_LIGHT=p.surface_light,
                SURFACE_CARD=p.surface_card,
                BORDER=p.border,
                BORDER_LIGHT=p.border_light,
                HIGHLIGHT=p.highlight,
                TEXT_PRIMARY=p.text_primary,
                TEXT_SECONDARY=p.text_secondary,
                TEXT_MUTED=p.text_muted,
                ACCENT=p.accent,
                ACCENT_HOVER=p.accent_hover,
                ACCENT_SUBTLE=p.accent_subtle,
                DANGER=cls.get_class_color("Blunder"),
                BRILLIANT=cls.get_class_color("Brilliant"),
                DANGER_HOVER=p.danger_hover,
                DANGER_PRESSED=p.danger_pressed,
                ON_ACCENT=Styles.COLOR_ON_ACCENT,
                MONO_FONT=Styles.MONO_FONT_FAMILY,
                SURFACE_LIGHT_55=_rgba(p.surface_light, 0.55),
                TICK_PATH=tick_path,
            )
        except Exception as e:
            logger.error(f"Failed to load app stylesheet template from {qss_path}: {e}")

        # Typography is always applied, even if the template is missing, so
        # labels keep their roles, sizes, and semantic tones.
        typography_qss = Styles.get_typography_qss()

        app = QApplication.instance()
        if app:
            bundle = cls._active_bundle()
            extra = bundle.extra_qss if bundle and bundle.extra_qss else ""
            app.setStyleSheet(template_qss + "\n" + typography_qss + "\n" + extra)

    @classmethod
    def set_mode(cls, mode: str, force: bool = True):
        if not force and mode == cls._current_mode:
            return
        cls._current_mode = mode
        bundle = cls._bundles.get(mode)
        if bundle is not None:
            cls._active_bundle_id = mode
            cls._palette = cls._palette_for_bundle(bundle, cls._accent)
        else:
            cls._active_bundle_id = None
            cls._palette = (DARK if mode == "dark" else LIGHT).with_accent(cls._accent)
        cls._bump_style_revision()
        cls.apply_app_stylesheet()
        instance = cls.instance()
        instance.theme_changed.emit(mode)

    @classmethod
    def toggle_mode(cls):
        cls.set_mode("light" if cls._current_mode == "dark" else "dark")

    @classmethod
    def set_accent_mode(cls, mode: str):
        """Set accent mode: 'system' or 'manual'."""
        cls._accent_mode = mode
        if mode == "system":
            detected = get_system_accent()
            if detected:
                cls.set_accent(detected)

    @classmethod
    def set_accent(cls, hex_color: str):
        if not hex_color:
            hex_color = get_system_accent() or (
                DARK.accent if cls._current_mode == "dark" else LIGHT.accent
            )
        cls._accent = hex_color
        bundle = cls._active_bundle()
        if bundle is not None:
            cls._palette = cls._palette_for_bundle(bundle, hex_color)
        else:
            cls._palette = cls._palette.with_accent(hex_color)
        cls._bump_style_revision()
        cls.apply_app_stylesheet()
        instance = cls.instance()
        instance.accent_changed.emit(hex_color)

    @classmethod
    def refresh_system_accent(cls):
        """Re-read system accent and apply if in system mode."""
        if cls._accent_mode == "system":
            detected = get_system_accent(force=True)
            if detected:
                cls.set_accent(detected)

    @classmethod
    def drop_shadow(cls, elevation: int = 1) -> QGraphicsDropShadowEffect:
        elev = ELEVATIONS.get(elevation, ELEVATIONS[1])
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(elev.blur_radius)
        shadow.setOffset(elev.x_offset, elev.y_offset)
        shadow.setColor(QColor(0, 0, 0, elev.opacity))
        return shadow

    @classmethod
    def apply_elevation(cls, widget, elevation: int = 1):
        shadow = cls.drop_shadow(elevation)
        widget.setGraphicsEffect(shadow)
