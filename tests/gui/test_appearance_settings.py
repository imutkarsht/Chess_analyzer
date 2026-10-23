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
