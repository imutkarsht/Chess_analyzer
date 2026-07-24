import subprocess
import sys

from PyQt6.QtCore import QObject, Qt, pyqtSignal
from PyQt6.QtGui import QGuiApplication, QPalette
from PyQt6.QtWidgets import QApplication

MACOS_ACCENT_MAP = {
    -1: "#8E8E93",  # Graphite
    0: "#FF3B30",   # Red
    1: "#FF9500",   # Orange
    2: "#FFCC00",   # Yellow
    3: "#34C759",   # Green
    4: "#007AFF",   # Blue
    5: "#AF52DE",   # Purple
    6: "#FF2D55",   # Pink
}

_ACCENT_CACHE: str | None = None


def get_system_accent(force: bool = False) -> str | None:
    global _ACCENT_CACHE
    if _ACCENT_CACHE and not force:
        return _ACCENT_CACHE

    if sys.platform == "darwin":
        try:
            result = subprocess.run(
                ["defaults", "read", "-g", "AppleAccentColor"],
                capture_output=True, text=True, timeout=2,
            )
            if result.returncode == 0:
                value = int(result.stdout.strip())
                color = MACOS_ACCENT_MAP.get(value)
                if color:
                    _ACCENT_CACHE = color
                    return color
        except (ValueError, subprocess.TimeoutExpired, FileNotFoundError):
            pass

    try:
        palette = QApplication.style().standardPalette()
        accent = palette.color(QPalette.ColorRole.Accent)
        color = accent.name()
        _ACCENT_CACHE = color
        return color
    except Exception:
        return None


class OSThemeWatcher(QObject):
    color_scheme_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        hints = QGuiApplication.styleHints()
        hints.colorSchemeChanged.connect(self._on_scheme_changed)

    def _on_scheme_changed(self, scheme):
        mode = "dark" if scheme == Qt.ColorScheme.Dark else "light"
        self.color_scheme_changed.emit(mode)

    @staticmethod
    def current_scheme() -> str:
        scheme = QGuiApplication.styleHints().colorScheme()
        return "dark" if scheme == Qt.ColorScheme.Dark else "light"

    def cleanup(self):
        try:
            hints = QGuiApplication.styleHints()
            hints.colorSchemeChanged.disconnect(self._on_scheme_changed)
        except (TypeError, RuntimeError):
            pass
