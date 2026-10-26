"""Sidebar default-state and preference persistence."""

import pytest

from src.gui.components.sidebar import COLLAPSED_WIDTH, EXPANDED_WIDTH, Sidebar


class _FakeConfig:
    """Minimal ConfigManager stand-in for sidebar preference reads."""

    def __init__(self, collapsed: bool = False):
        self.config = {"sidebar_start_collapsed": collapsed}

    def get(self, key, default=None):
        return self.config.get(key, default)

    def set(self, key, value):
        self.config[key] = value


@pytest.mark.parametrize(
    ("collapsed", "expected_width", "has_labels"),
    [(False, EXPANDED_WIDTH, True), (True, COLLAPSED_WIDTH, False)],
)
def test_sidebar_starts_in_configured_state(qapp, collapsed, expected_width, has_labels):
    sidebar = Sidebar(_FakeConfig(collapsed=collapsed))

    assert sidebar._collapsed is collapsed
    assert sidebar.width() == expected_width
    assert sidebar._nav_buttons[0].text() == ("  Analyze" if has_labels else "")
    sidebar.deleteLater()


def test_apply_preferences_reflects_new_setting(qapp):
    config = _FakeConfig(collapsed=False)
    sidebar = Sidebar(config)

    config.set("sidebar_start_collapsed", True)
    sidebar.apply_preferences()
    assert sidebar._collapsed is True

    config.set("sidebar_start_collapsed", False)
    sidebar.apply_preferences()
    assert sidebar._collapsed is False
    sidebar.deleteLater()
