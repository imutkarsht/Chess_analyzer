"""Tests for ThemeManager, palettes, and dynamic theme switching."""
from src.gui.theme.manager import ThemeManager
from src.gui.theme.palette import DARK, LIGHT, CLASSIFICATION_COLORS, BOARD_THEMES


def test_theme_manager_singleton(qapp):
    """ThemeManager instance() returns a shared singleton."""
    mgr1 = ThemeManager.instance()
    mgr2 = ThemeManager.instance()
    assert mgr1 is mgr2


def test_theme_mode_switching(qapp, qtbot):
    """Switching between dark and light modes updates background/surface colors and emits signal."""
    mgr = ThemeManager.instance()

    with qtbot.waitSignal(mgr.theme_changed, timeout=1000) as blocker:
        mgr.set_mode("light")

    assert mgr.mode() == "light"
    assert mgr.palette().background == LIGHT.background
    assert mgr.palette().surface == LIGHT.surface

    with qtbot.waitSignal(mgr.theme_changed, timeout=1000) as blocker:
        mgr.set_mode("dark")

    assert mgr.mode() == "dark"
    assert mgr.palette().background == DARK.background
    assert mgr.palette().surface == DARK.surface


def test_accent_color_update(qapp, qtbot):
    """Setting accent color updates palette and emits accent_changed signal."""
    mgr = ThemeManager.instance()
    custom_accent = "#3B82F6"

    with qtbot.waitSignal(mgr.accent_changed, timeout=1000) as blocker:
        mgr.set_accent(custom_accent)

    assert blocker.args == [custom_accent]
    assert mgr.accent() == custom_accent
    assert mgr.palette().accent == custom_accent


def test_classification_colors():
    """Classification colors are properly resolved."""
    assert ThemeManager.get_class_color("Brilliant") == CLASSIFICATION_COLORS["Brilliant"]
    assert ThemeManager.get_class_color("Blunder") == CLASSIFICATION_COLORS["Blunder"]
    assert ThemeManager.get_class_color("Best") == CLASSIFICATION_COLORS["Best"]


def test_board_colors_resolution():
    """Board themes return correct dark and light square colors."""
    green = ThemeManager.get_board_colors("Green")
    assert "dark" in green and "light" in green
    assert green["dark"] == BOARD_THEMES["Green"]["dark"]
    assert green["light"] == BOARD_THEMES["Green"]["light"]


def test_apply_app_stylesheet(qapp):
    """apply_app_stylesheet compiles template and applies without error."""
    ThemeManager.apply_app_stylesheet()
    assert len(qapp.styleSheet()) > 50

