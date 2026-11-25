"""Tests for ThemeManager, palettes, and dynamic theme switching.

``set_mode``/``set_accent`` recompile the whole global stylesheet, which costs
seconds per call, so the state-machine test stubs that out. One dedicated test
still exercises the real compilation.
"""

import pytest

from src.gui.theme.manager import ThemeManager
from src.gui.theme.palette import DARK, LIGHT


def test_accent_is_adjusted_for_readability(qapp, monkeypatch):
    """Light-on-light and dark-on-dark accents get a readable UI variant."""
    from src.gui.styles import Styles

    monkeypatch.setattr(ThemeManager, "apply_app_stylesheet", classmethod(lambda cls: None))
    previous_accent = ThemeManager.accent()
    previous_mode = ThemeManager.theme_mode()

    try:
        for mode, accent in (("light", "#FFF59D"), ("dark", "#001122")):
            ThemeManager.set_theme_mode(mode)
            ThemeManager.set_accent(accent)
            palette = ThemeManager.palette()
            assert palette.accent == accent
            assert Styles.contrast_ratio(palette.ui_accent, palette.surface) >= 4.5
            assert Styles.contrast_ratio(palette.on_accent, palette.ui_accent) >= 4.5
    finally:
        ThemeManager.set_theme_mode(previous_mode)
        ThemeManager.set_accent(previous_accent)


@pytest.fixture(autouse=True)
def _reset_tint():
    """Prevent tint state leaking between theme tests."""
    previous = ThemeManager.tint_enabled()
    ThemeManager.set_tint_enabled(False, apply=False)
    yield
    ThemeManager.set_tint_enabled(previous, apply=False)


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


def test_theme_template_qss_path_exists():
    """The central QSS template must exist next to ThemeManager in dev and be packaged."""
    import os

    import src.gui.theme.manager as manager_module

    qss_path = os.path.join(os.path.dirname(manager_module.__file__), "theme_template.qss")
    assert os.path.exists(qss_path)


def test_dracula_bundle_palette_and_semantics(qapp, monkeypatch):
    """Dracula applies its official palette and semantic colour remaps."""
    monkeypatch.setattr(ThemeManager, "apply_app_stylesheet", classmethod(lambda cls: None))

    assert "dracula" in ThemeManager.registered_bundles()
    try:
        ThemeManager.set_bundle("dracula")
        palette = ThemeManager.palette()
        assert palette.background == "#282A36"
        assert palette.surface == "#30323F"
        assert palette.text_primary == "#F8F8F2"
        # A signature theme adopts its own accent (classic Dracula purple).
        assert palette.accent == "#BD93F9"
        assert ThemeManager.accent() == "#BD93F9"
        assert ThemeManager.get_class_color("Blunder") == "#FF5555"
        assert ThemeManager.get_class_color("Miss") == "#FF79C6"
        assert ThemeManager.get_class_color("Best") == "#50FA7B"
    finally:
        ThemeManager.set_theme_mode("dark")


def test_restore_saved_theme_preserves_signature_accent(qapp, monkeypatch):
    """Dracula must stay purple on restart even if a custom accent was saved."""
    from src.gui.main_window.theme_mixin import ThemeMixin

    monkeypatch.setattr(ThemeManager, "apply_app_stylesheet", classmethod(lambda cls: None))
    previous_accent = ThemeManager.accent()
    previous_accent_mode = ThemeManager.accent_mode()

    class Cfg:
        theme_mode = "dracula"
        accent_color = "#123456"
        accent_mode = "custom"

    class Host(ThemeMixin):
        pass

    host = Host()
    host.config_manager = Cfg()
    try:
        host.restore_saved_theme()
        assert ThemeManager.active_bundle_id() == "dracula"
        assert ThemeManager.active_bundle_owns_accent() is True
        assert ThemeManager.palette().accent == "#BD93F9"
    finally:
        ThemeManager.set_theme_mode("dark")
        ThemeManager.set_accent_mode(previous_accent_mode)
        ThemeManager.set_accent(previous_accent)


def test_restore_saved_theme_applies_custom_accent_for_regular_themes(qapp, monkeypatch):
    """Non-signature themes still restore the user's saved custom accent."""
    from src.gui.main_window.theme_mixin import ThemeMixin

    monkeypatch.setattr(ThemeManager, "apply_app_stylesheet", classmethod(lambda cls: None))
    previous_accent = ThemeManager.accent()
    previous_accent_mode = ThemeManager.accent_mode()

    class Cfg:
        theme_mode = "dark"
        accent_color = "#123456"
        accent_mode = "custom"

    class Host(ThemeMixin):
        pass

    host = Host()
    host.config_manager = Cfg()
    try:
        host.restore_saved_theme()
        assert ThemeManager.palette().accent == "#123456"
    finally:
        ThemeManager.set_accent_mode(previous_accent_mode)
        ThemeManager.set_accent(previous_accent)


def test_tint_toggle_derives_light_and_dark_palettes(qapp, monkeypatch):
    """The tint setting rebuilds Light and Dark surfaces from the live accent."""
    monkeypatch.setattr(ThemeManager, "apply_app_stylesheet", classmethod(lambda cls: None))
    previous_accent = ThemeManager.accent()
    previous_tint = ThemeManager.tint_enabled()

    try:
        ThemeManager.set_theme_mode("dark")
        ThemeManager.set_tint_enabled(True)
        assert ThemeManager.supports_tint() is True
        dark_bg = ThemeManager.palette().background
        assert dark_bg != DARK.background

        ThemeManager.set_accent("#E11D48")
        assert ThemeManager.palette().background != dark_bg
        assert ThemeManager.palette().accent == "#E11D48"

        ThemeManager.set_theme_mode("light")
        light_bg = ThemeManager.palette().background
        assert light_bg != LIGHT.background
        assert ThemeManager.palette().surface != LIGHT.surface
        assert ThemeManager.palette().surface_card != LIGHT.surface_card

        ThemeManager.set_tint_enabled(False)
        assert ThemeManager.palette().background == LIGHT.background
        assert ThemeManager.tint_enabled() is False
    finally:
        ThemeManager.set_tint_enabled(False, apply=False)
        ThemeManager.set_theme_mode("dark")
        ThemeManager.set_accent(previous_accent)
        ThemeManager.set_tint_enabled(previous_tint)

    assert ThemeManager.palette().background == DARK.background


def test_registered_bundles_and_set_bundle_state(qapp, qtbot, monkeypatch):
    """A registered bundle drives palette, mode, class colours, and extra QSS."""
    from src.gui.theme.bundle import ThemeBundle
    from src.gui.theme.palette import ThemePalette

    monkeypatch.setattr(ThemeManager, "apply_app_stylesheet", classmethod(lambda cls: None))

    bundle = ThemeBundle(
        id="test-oled",
        display_name="Test OLED",
        palette=ThemePalette(
            background="#000000",
            surface="#0A0A0A",
            surface_light="#141414",
            surface_card="#101010",
            border="#262626",
            border_light="#333333",
            highlight="#1E1E1E",
            text_primary="#F2F2F2",
            text_secondary="#A3A3A3",
            text_muted="#737373",
        ),
        mode="dark",
        classification_colors={"Blunder": "#FF0000"},
        extra_qss="QLabel { letter-spacing: 0px; }",
    )
    ThemeManager.register_bundle(bundle)

    try:
        assert "test-oled" in ThemeManager.registered_bundles()
        with qtbot.waitSignal(ThemeManager.instance().theme_changed, timeout=1000) as blocker:
            ThemeManager.set_theme_mode("test-oled")
        assert blocker.args == ["test-oled"]
        assert ThemeManager.active_bundle_id() == "test-oled"
        assert ThemeManager.mode() == "dark"
        assert ThemeManager.palette().background == "#000000"
        assert ThemeManager.get_class_color("Blunder") == "#FF0000"
        # Board themes fall back to the built-in defaults for the bundle.
        assert ThemeManager.get_board_colors("Green")["dark"].startswith("#")
    finally:
        ThemeManager._bundles.pop("test-oled", None)
        ThemeManager.set_theme_mode("dark")
        ThemeManager.set_mode("dark")
