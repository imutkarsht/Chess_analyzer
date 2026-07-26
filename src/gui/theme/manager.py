from dataclasses import dataclass

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QGraphicsDropShadowEffect

from .palette import ThemePalette, DARK, LIGHT, CLASSIFICATION_COLORS, BOARD_THEMES
from .system import OSThemeWatcher, get_system_accent


@dataclass
class Elevation:
    blur_radius: int
    x_offset: int
    y_offset: int
    opacity: int


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
    _theme_mode: str = "system"  # "system" | "dark" | "light"
    _palette: ThemePalette = DARK
    _accent: str = "#FF9500"
    _accent_mode: str = "system"  # "system" | "manual"
    _os_watcher: OSThemeWatcher | None = None

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
    def get_class_color(cls, classification: str) -> str:
        return CLASSIFICATION_COLORS.get(classification, cls._palette.text_primary)

    @classmethod
    def get_board_colors(cls, theme_name: str = "Green") -> dict:
        theme = BOARD_THEMES.get(theme_name, BOARD_THEMES["Green"])
        dark = theme["dark"]
        light = theme["light"]
        if dark == "dynamic":
            dark = cls._accent
        return {"dark": dark, "light": light}

    @classmethod
    def set_theme_mode(cls, mode: str):
        """Set theme mode: 'system', 'dark', or 'light'."""
        cls._theme_mode = mode
        if mode == "system":
            detected = OSThemeWatcher.current_scheme()
            cls.set_mode(detected)
        else:
            cls.set_mode(mode)

    @classmethod
    def apply_app_stylesheet(cls):
        """Compiles and applies the central QSS theme template globally to QApplication."""
        from PyQt6.QtWidgets import QApplication
        import os
        from src.utils.path_utils import get_resource_path

        qss_path = os.path.join(os.path.dirname(__file__), "theme_template.qss")
        if not os.path.exists(qss_path):
            qss_path = get_resource_path("src/gui/theme/theme_template.qss")

        try:
            with open(qss_path, "r", encoding="utf-8") as f:
                template = f.read()

            p = cls._palette
            tick_path = get_resource_path("assets/images/tick.svg").replace("\\", "/")

            qss = template.format(
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
                TICK_PATH=tick_path
            )
            app = QApplication.instance()
            if app:
                app.setStyleSheet(qss)
        except Exception as e:
            from src.utils.logger import logger
            logger.error(f"Failed to apply app stylesheet: {e}")

    @classmethod
    def set_mode(cls, mode: str, force: bool = True):
        if not force and mode == cls._current_mode:
            return
        cls._current_mode = mode
        cls._palette = DARK if mode == "dark" else LIGHT
        cls._palette = cls._palette.with_accent(cls._accent)
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
            hex_color = get_system_accent() or (DARK.accent if cls._current_mode == "dark" else LIGHT.accent)
        cls._accent = hex_color
        cls._palette = cls._palette.with_accent(hex_color)
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
