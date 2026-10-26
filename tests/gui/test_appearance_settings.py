"""Appearance cards: board display, layout, theme, and sound controls."""

import pytest

from src.gui.views.settings.board_pieces_settings import BoardPiecesSettings
from src.gui.views.settings.sound_settings import SoundSettings
from src.gui.views.settings.theme_accent_settings import ThemeAccentSettings
from src.gui.views.settings.window_layout_settings import WindowLayoutSettings


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
            "board_show_best_move_arrow": True,
            "board_show_last_move": True,
            "board_show_eval_bar": True,
            "sidebar_start_collapsed": False,
            "history_view_mode": "compact",
            "remember_window_geometry": True,
            "sound_enabled": True,
            "sound_volume": 50,
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

    widget = BoardPiecesSettings(config)

    assert widget.coordinates_checkbox.isChecked() is False
    assert widget.classification_checkbox.isChecked() is False
    widget.deleteLater()


def test_board_display_toggles_write_config_and_request_repaint(qapp):
    config = _FakeConfig()
    widget = BoardPiecesSettings(config)
    repaints = []
    widget.theme_refreshed.connect(lambda: repaints.append(True))

    widget.coordinates_checkbox.setChecked(False)
    widget.classification_checkbox.setChecked(False)

    assert config.config["board_show_coordinates"] is False
    assert config.config["board_show_classification"] is False
    assert len(repaints) == 2
    widget.deleteLater()


@pytest.mark.parametrize(
    ("attribute", "key"),
    [
        ("best_move_arrow_checkbox", "board_show_best_move_arrow"),
        ("last_move_checkbox", "board_show_last_move"),
        ("eval_bar_checkbox", "board_show_eval_bar"),
    ],
)
def test_board_annotation_toggles_persist_and_repaint(qapp, attribute, key):
    config = _FakeConfig()
    widget = BoardPiecesSettings(config)
    repaints = []
    widget.theme_refreshed.connect(lambda: repaints.append(True))

    checkbox = getattr(widget, attribute)
    assert checkbox.isChecked() is True

    checkbox.setChecked(False)

    assert config.config[key] is False
    assert repaints == [True]
    widget.deleteLater()


def test_board_advanced_rows_hide_in_basic_mode(qapp):
    widget = BoardPiecesSettings(_FakeConfig())

    widget.set_advanced_visible(False)

    assert widget.best_move_arrow_checkbox.parentWidget().isHidden() is True
    assert widget.last_move_checkbox.parentWidget().isHidden() is True
    assert widget.eval_bar_checkbox.parentWidget().isHidden() is True
    assert widget.coordinates_checkbox.parentWidget().isHidden() is False
    widget.deleteLater()


def test_sidebar_mode_radio_reflects_saved_config(qapp):
    widget = WindowLayoutSettings(_FakeConfig({"sidebar_start_collapsed": True}))

    assert widget.sidebar_collapsed_radio.isChecked() is True
    assert widget.sidebar_expanded_radio.isChecked() is False
    widget.deleteLater()


def test_sidebar_mode_radio_writes_config_and_notifies(qapp):
    config = _FakeConfig()
    widget = WindowLayoutSettings(config)
    changes = []
    widget.sidebar_prefs_changed.connect(lambda: changes.append(True))

    widget.sidebar_collapsed_radio.click()

    assert config.config["sidebar_start_collapsed"] is True
    assert changes == [True]

    widget.sidebar_expanded_radio.click()

    assert config.config["sidebar_start_collapsed"] is False
    assert len(changes) == 2
    widget.deleteLater()


def test_history_view_mode_persists_and_notifies(qapp):
    config = _FakeConfig({"history_view_mode": "compact"})
    widget = WindowLayoutSettings(config)
    changes = []
    widget.history_view_changed.connect(lambda: changes.append(True))

    assert widget.history_view_combo.currentData() == "compact"
    widget.history_view_combo.setCurrentIndex(
        widget.history_view_combo.findData("detailed")
    )

    assert config.config["history_view_mode"] == "detailed"
    assert changes == [True]
    widget.deleteLater()


def test_remember_window_geometry_toggle_persists(qapp):
    config = _FakeConfig()
    widget = WindowLayoutSettings(config)

    assert widget.remember_window_checkbox.isChecked() is True

    widget.remember_window_checkbox.setChecked(False)

    assert config.config["remember_window_geometry"] is False
    widget.deleteLater()


def test_board_theme_change_persists_and_requests_repaint(qapp):
    config = _FakeConfig()
    widget = BoardPiecesSettings(config)
    repaints = []
    widget.theme_refreshed.connect(lambda: repaints.append(True))

    widget.theme_combo.setCurrentIndex(widget.theme_combo.findData("Blue"))

    assert config.config["board_theme"] == "Blue"
    assert repaints == [True]
    widget.deleteLater()


def test_theme_mode_radio_persists_and_applies_theme(qapp, monkeypatch):
    from src.gui.theme import ThemeManager

    applied = []
    monkeypatch.setattr(ThemeManager, "set_theme_mode", lambda mode: applied.append(mode))
    config = _FakeConfig()
    widget = ThemeAccentSettings(config)

    widget.theme_mode_choice.radios()[2].click()  # Dark

    assert config.config["theme_mode"] == "dark"
    assert applied == ["dark"]
    widget.deleteLater()


def test_custom_accent_mode_reveals_colour_picker(qapp, monkeypatch):
    from src.gui.theme import ThemeManager

    monkeypatch.setattr(ThemeManager, "set_accent_mode", lambda mode: None)
    config = _FakeConfig()
    widget = ThemeAccentSettings(config)
    assert widget.color_btn.isHidden() is True

    widget.accent_mode_custom.click()

    assert config.config["accent_mode"] == "custom"
    assert widget.color_btn.isHidden() is False
    widget.deleteLater()


def test_sound_volume_defaults_and_persists(qapp):
    config = _FakeConfig()
    widget = SoundSettings(config)

    assert widget.volume_input.text() == "50"

    widget.volume_input.setValue(80)
    widget.volume_input.editingFinished.emit()

    assert config.config["sound_volume"] == 80
    widget.deleteLater()


def test_sound_volume_is_advanced_only(qapp):
    widget = SoundSettings(_FakeConfig())

    widget.set_advanced_visible(False)

    assert widget.volume_input.parentWidget().isHidden() is True
    assert widget.sound_checkbox.parentWidget().isHidden() is False
    widget.deleteLater()
