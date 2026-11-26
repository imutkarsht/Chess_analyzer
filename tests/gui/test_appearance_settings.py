"""Appearance cards: board display, layout, theme, and sound controls."""

import pytest
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QColorDialog

from src.gui.components import TooltipManager
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
            "accent_color": "#FF9500",
            "tint_enabled": False,
            "toast_position": "top_right",
            "board_show_coordinates": True,
            "board_show_classification": True,
            "board_show_best_move_arrow": True,
            "board_show_last_move": True,
            "board_show_eval_bar": True,
            "board_wheel_navigation": True,
            "sidebar_start_collapsed": False,
            "history_view_mode": "compact",
            "remember_window_geometry": True,
            "tooltips_enabled": True,
            "sound_enabled": True,
            "sound_volume": 50,
        }
        self.config.update(overrides or {})

    def get(self, key, default=None):
        return self.config.get(key, default)

    def set(self, key, value):
        self.config[key] = value

    @property
    def board_theme(self):
        return self.config["board_theme"]

    @property
    def piece_theme(self):
        return self.config["piece_theme"]

    @property
    def sidebar_start_collapsed(self):
        return self.config["sidebar_start_collapsed"]


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


def test_wheel_navigation_toggle_persists_and_repaints(qapp):
    config = _FakeConfig()
    widget = BoardPiecesSettings(config)
    repaints = []
    widget.theme_refreshed.connect(lambda: repaints.append(True))

    assert widget.wheel_navigation_checkbox.isChecked() is True
    widget.wheel_navigation_checkbox.setChecked(False)

    assert config.config["board_wheel_navigation"] is False
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


def test_tooltips_toggle_persists_and_updates_the_manager(qapp):
    manager = TooltipManager.instance(qapp)
    manager.set_enabled(True)
    config = _FakeConfig()
    widget = WindowLayoutSettings(config)

    assert widget.tooltips_checkbox.isChecked() is True

    widget.tooltips_checkbox.setChecked(False)

    assert config.config["tooltips_enabled"] is False
    assert manager.enabled is False

    widget.deleteLater()
    manager.set_enabled(True)
    manager.shutdown()


def test_board_theme_change_persists_and_requests_repaint(qapp):
    config = _FakeConfig()
    widget = BoardPiecesSettings(config)
    repaints = []
    widget.theme_refreshed.connect(lambda: repaints.append(True))

    widget.board_buttons["Blue"].click()

    assert config.config["board_theme"] == "Blue"
    assert repaints == [True]
    widget.deleteLater()


def test_piece_theme_change_persists_and_requests_repaint(qapp):
    config = _FakeConfig()
    widget = BoardPiecesSettings(config)
    repaints = []
    widget.theme_refreshed.connect(lambda: repaints.append(True))

    assert "Standard" in widget.piece_buttons
    widget.piece_buttons["Standard"].click()

    assert config.config["piece_theme"] == "Standard"
    assert repaints == [True]
    widget.deleteLater()


def test_theme_card_selection_persists_and_applies_theme(qapp, monkeypatch):
    from src.gui.theme import ThemeManager

    applied = []
    monkeypatch.setattr(ThemeManager, "set_theme_mode", lambda mode: applied.append(mode))
    config = _FakeConfig()
    widget = ThemeAccentSettings(config)

    widget.gallery.cards["dark"].click()

    assert config.config["theme_mode"] == "dark"
    assert applied == ["dark"]
    assert widget.gallery.cards["dark"].isChecked() is True
    widget.deleteLater()


def test_tint_row_is_visible_only_for_light_and_dark(qapp, monkeypatch):
    from src.gui.theme import ThemeManager

    monkeypatch.setattr(ThemeManager, "set_theme_mode", lambda mode: None)
    config = _FakeConfig({"theme_mode": "system"})
    widget = ThemeAccentSettings(config)
    assert widget.tint_row.isHidden() is True

    widget.gallery.cards["dark"].click()
    assert widget.tint_row.isHidden() is False

    widget.gallery.cards["dracula"].click()
    assert widget.tint_row.isHidden() is True
    widget.deleteLater()


def test_tint_checkbox_persists_and_applies(qapp, monkeypatch):
    from src.gui.theme import ThemeManager

    applied = []
    monkeypatch.setattr(ThemeManager, "set_tint_enabled", lambda enabled: applied.append(enabled))
    config = _FakeConfig({"theme_mode": "dark"})
    widget = ThemeAccentSettings(config)

    assert widget.tint_row.isHidden() is False
    widget.tint_checkbox.setChecked(True)

    assert config.config["tint_enabled"] is True
    assert applied == [True]
    widget.deleteLater()


def test_accent_preset_writes_config_and_applies(qapp, monkeypatch):
    from src.gui.theme import ThemeManager

    applied = []
    monkeypatch.setattr(ThemeManager, "set_accent_mode", lambda mode: None)
    monkeypatch.setattr(ThemeManager, "set_accent", lambda color: applied.append(color))
    monkeypatch.setattr(ThemeManager, "mode", classmethod(lambda cls: "light"))
    config = _FakeConfig()
    widget = ThemeAccentSettings(config)

    widget.accent_buttons["Blue"].click()

    assert config.config["accent_color"] == "#3B82F6"
    assert config.config["accent_mode"] == "custom"
    assert applied == ["#3B82F6"]
    assert widget.accent_buttons["Blue"].isChecked() is True
    assert widget.custom_accent_btn.isChecked() is False
    widget.deleteLater()


def test_dark_mode_accent_presets_are_softer(qapp, monkeypatch):
    from src.gui.theme import ThemeManager

    monkeypatch.setattr(ThemeManager, "set_accent_mode", lambda mode: None)
    monkeypatch.setattr(ThemeManager, "mode", classmethod(lambda cls: "dark"))
    widget = ThemeAccentSettings(_FakeConfig())

    assert widget.accent_buttons["Blue"].color == "#6F9BD8"
    assert widget.accent_buttons["Green"].color == "#5FB894"
    assert widget.accent_buttons["Orange"].color == "#D9A15E"

    monkeypatch.setattr(ThemeManager, "mode", classmethod(lambda cls: "light"))
    widget._refresh_accent_presets()

    assert widget.accent_buttons["Blue"].color == "#3B82F6"
    widget.deleteLater()


def test_preset_accent_remaps_when_theme_mode_changes(qapp, monkeypatch):
    from src.gui.theme import ThemeManager

    applied = []
    mode = {"value": "dark"}
    monkeypatch.setattr(ThemeManager, "mode", classmethod(lambda cls: mode["value"]))
    monkeypatch.setattr(
        ThemeManager,
        "active_bundle_owns_accent",
        classmethod(lambda cls: False),
    )
    monkeypatch.setattr(ThemeManager, "set_accent_mode", lambda _mode: None)
    monkeypatch.setattr(ThemeManager, "set_accent", lambda color: applied.append(color))
    config = _FakeConfig(
        {"theme_mode": "dark", "accent_mode": "custom", "accent_color": "#6F9BD8"}
    )
    widget = ThemeAccentSettings(config)
    assert widget.accent_buttons["Blue"].isChecked() is True

    mode["value"] = "light"
    widget._refresh_accent_presets()
    assert config.config["accent_color"] == "#3B82F6"
    assert applied == ["#3B82F6"]
    assert widget.accent_buttons["Blue"].isChecked() is True

    mode["value"] = "dark"
    widget._refresh_accent_presets()
    assert config.config["accent_color"] == "#6F9BD8"
    assert applied == ["#3B82F6", "#6F9BD8"]
    widget.deleteLater()


@pytest.mark.parametrize(
    ("accent_mode", "accent_color"),
    [("system", "#6F9BD8"), ("custom", "#123456")],
)
def test_non_preset_accents_do_not_remap_on_theme_change(
    qapp, monkeypatch, accent_mode, accent_color
):
    from src.gui.theme import ThemeManager

    applied = []
    mode = {"value": "dark"}
    monkeypatch.setattr(ThemeManager, "mode", classmethod(lambda cls: mode["value"]))
    monkeypatch.setattr(
        ThemeManager,
        "active_bundle_owns_accent",
        classmethod(lambda cls: False),
    )
    monkeypatch.setattr(ThemeManager, "set_accent_mode", lambda _mode: None)
    monkeypatch.setattr(ThemeManager, "set_accent", lambda color: applied.append(color))
    config = _FakeConfig(
        {
            "theme_mode": "dark",
            "accent_mode": accent_mode,
            "accent_color": accent_color,
        }
    )
    widget = ThemeAccentSettings(config)

    mode["value"] = "light"
    widget._refresh_accent_presets()

    assert config.config["accent_color"] == accent_color
    assert applied == []
    widget.deleteLater()


def test_system_accent_action_restores_system_mode(qapp, monkeypatch):
    from src.gui.theme import ThemeManager

    applied = []
    monkeypatch.setattr(ThemeManager, "set_accent_mode", lambda mode: applied.append(mode))
    monkeypatch.setattr(ThemeManager, "set_accent", lambda color: None)
    config = _FakeConfig({"accent_mode": "custom", "accent_color": "#3B82F6"})
    widget = ThemeAccentSettings(config)

    widget.system_accent_btn.click()

    assert config.config["accent_mode"] == "system"
    assert applied == ["system"]
    assert widget.system_accent_btn.isChecked() is True
    assert all(not swatch.isChecked() for swatch in widget.accent_buttons.values())
    widget.deleteLater()


def test_custom_accent_dialog_persists_colour(qapp, monkeypatch):
    from src.gui.theme import ThemeManager

    applied = []
    monkeypatch.setattr(ThemeManager, "set_accent_mode", lambda mode: None)
    monkeypatch.setattr(ThemeManager, "set_accent", lambda color: applied.append(color))
    monkeypatch.setattr(
        QColorDialog,
        "getColor",
        lambda *args, **kwargs: QColor("#123456"),
    )
    config = _FakeConfig()
    widget = ThemeAccentSettings(config)

    widget.custom_accent_btn.click()

    assert config.config["accent_color"] == "#123456"
    assert config.config["accent_mode"] == "custom"
    assert applied == ["#123456"]
    assert widget.custom_accent_btn.isChecked() is True
    widget.deleteLater()


def test_stored_custom_accent_selects_matching_preset(qapp, monkeypatch):
    from src.gui.theme import ThemeManager

    monkeypatch.setattr(ThemeManager, "set_accent_mode", lambda mode: None)
    widget = ThemeAccentSettings(
        _FakeConfig({"accent_mode": "custom", "accent_color": "#3B82F6"})
    )

    assert widget.accent_buttons["Blue"].isChecked() is True
    assert widget.custom_accent_btn.isChecked() is False
    widget.deleteLater()


def test_stored_custom_accent_without_preset_marks_custom(qapp, monkeypatch):
    from src.gui.theme import ThemeManager

    monkeypatch.setattr(ThemeManager, "set_accent_mode", lambda mode: None)
    widget = ThemeAccentSettings(
        _FakeConfig({"accent_mode": "custom", "accent_color": "#123456"})
    )

    assert widget.custom_accent_btn.isChecked() is True
    assert all(not swatch.isChecked() for swatch in widget.accent_buttons.values())
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
