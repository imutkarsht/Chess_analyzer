"""Tests for ThemeManager, palettes, and dynamic theme switching.

``set_mode``/``set_accent`` recompile the whole global stylesheet, which costs
seconds per call, so the state-machine test stubs that out. One dedicated test
still exercises the real compilation.
"""

from src.gui.theme.manager import ThemeManager
from src.gui.theme.palette import DARK, LIGHT


def test_mode_and_accent_update_state_and_signals(qapp, qtbot, monkeypatch):
    """Mode and accent changes update the palette and emit their signals."""
    monkeypatch.setattr(ThemeManager, "apply_app_stylesheet", classmethod(lambda cls: None))
    mgr = ThemeManager.instance()

    with qtbot.waitSignal(mgr.theme_changed, timeout=1000):
        mgr.set_mode("light")
    assert mgr.mode() == "light"
    assert mgr.palette().background == LIGHT.background
    assert mgr.palette().surface == LIGHT.surface

    with qtbot.waitSignal(mgr.theme_changed, timeout=1000):
        mgr.set_mode("dark")
    assert mgr.mode() == "dark"
    assert mgr.palette().background == DARK.background
    assert mgr.palette().surface == DARK.surface

    custom_accent = "#3B82F6"
    with qtbot.waitSignal(mgr.accent_changed, timeout=1000) as blocker:
        mgr.set_accent(custom_accent)
    assert blocker.args == [custom_accent]
    assert mgr.accent() == custom_accent
    assert mgr.palette().accent == custom_accent


def test_apply_app_stylesheet(qapp):
    """apply_app_stylesheet compiles template and applies without error."""
    ThemeManager.apply_app_stylesheet()
    assert len(qapp.styleSheet()) > 50
