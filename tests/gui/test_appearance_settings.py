"""Board display toggles in the Appearance settings group."""

from src.gui.views.settings.appearance_settings import AppearanceSettings


class _FakeConfig:
    """Minimal ConfigManager stand-in; these widgets only read and assign keys."""

    def __init__(self, overrides=None):
        self.config = {
            "theme_mode": "system",
            "board_theme": "Green",
            "piece_theme": "Standard",
            "accent_mode": "system",
            "board_show_coordinates": True,
            "board_show_classification": True,
        }
        self.config.update(overrides or {})

    def get(self, key, default=None):
        return self.config.get(key, default)

    def set(self, key, value):
        self.config[key] = value


def test_board_display_toggles_reflect_saved_config(qapp):
    config = _FakeConfig(
        {"board_show_coordinates": False, "board_show_classification": False}
    )

    widget = AppearanceSettings(config)

    assert widget.coordinates_checkbox.isChecked() is False
    assert widget.classification_checkbox.isChecked() is False
    widget.deleteLater()


def test_board_display_toggles_write_config_and_request_repaint(qapp):
    config = _FakeConfig()
    widget = AppearanceSettings(config)
    repaints = []
    widget.theme_refreshed.connect(lambda: repaints.append(True))

    widget.coordinates_checkbox.setChecked(False)
    widget.classification_checkbox.setChecked(False)

    assert config.config["board_show_coordinates"] is False
    assert config.config["board_show_classification"] is False
    assert len(repaints) == 2
    widget.deleteLater()


def test_sidebar_mode_radio_reflects_saved_config(qapp):
    widget = AppearanceSettings(_FakeConfig({"sidebar_start_collapsed": True}))

    assert widget.sidebar_collapsed_radio.isChecked() is True
    assert widget.sidebar_expanded_radio.isChecked() is False
    widget.deleteLater()


def test_sidebar_mode_radio_writes_config_and_notifies(qapp):
    config = _FakeConfig()
    widget = AppearanceSettings(config)
    changes = []
    widget.sidebar_prefs_changed.connect(lambda: changes.append(True))

    widget.sidebar_collapsed_radio.click()

    assert config.config["sidebar_start_collapsed"] is True
    assert changes == [True]

    widget.sidebar_expanded_radio.click()

    assert config.config["sidebar_start_collapsed"] is False
    assert len(changes) == 2
    widget.deleteLater()
