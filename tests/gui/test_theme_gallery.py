# SPDX-License-Identifier: GPL-3.0-only
"""Appearance gallery structure, previews, and keyboard semantics."""

from PyQt6.QtCore import Qt

from src.gui.theme import DARK, LIGHT, ThemeManager
from src.gui.views.settings.theme_gallery import ThemeGallery


class _FakeConfig:
    def __init__(self, overrides=None):
        self.config = {
            "theme_mode": "system",
            "accent_mode": "system",
            "accent_color": "#FF9500",
            "tint_enabled": False,
            "toast_position": "top_right",
        }
        self.config.update(overrides or {})

    def get(self, key, default=None):
        return self.config.get(key, default)

    def set(self, key, value):
        self.config[key] = value


def test_gallery_groups_and_order(qapp):
    gallery = ThemeGallery(_FakeConfig())

    assert [card.value for card in gallery.sections["Automatic"].cards] == ["system"]
    assert [card.value for card in gallery.sections["Base"].cards] == ["light", "dark"]
    assert [card.value for card in gallery.sections["Themes"].cards] == [
        "dracula",
        "oled",
        "parchment",
        "nord",
    ]
    assert gallery.selected_mode == "system"
    gallery.deleteLater()


def test_theme_card_swatches_use_resolved_palette(qapp, monkeypatch):
    palette = DARK.with_accent("#3B82F6")
    monkeypatch.setattr(
        ThemeManager,
        "preview_palette",
        classmethod(lambda cls, bundle_id: palette),
    )
    gallery = ThemeGallery(_FakeConfig())

    assert gallery.cards["dark"].swatch_colors == (
        palette.background,
        palette.surface,
        palette.accent,
    )
    gallery.deleteLater()


def test_system_card_previews_both_base_modes(qapp, monkeypatch):
    monkeypatch.setattr(
        ThemeManager,
        "accent",
        classmethod(lambda cls: "#3B82F6"),
    )
    gallery = ThemeGallery(_FakeConfig())

    assert gallery.cards["system"].swatch_colors == (
        LIGHT.background,
        DARK.background,
        LIGHT.surface,
        DARK.surface,
        "#3B82F6",
    )
    gallery.deleteLater()


def test_gallery_preview_refreshes_on_accent_change(qapp, monkeypatch):
    accent = {"value": "#FF9500"}
    monkeypatch.setattr(
        ThemeManager,
        "accent",
        classmethod(lambda cls: accent["value"]),
    )
    monkeypatch.setattr(
        ThemeManager,
        "preview_palette",
        classmethod(lambda cls, bundle_id: DARK.with_accent(accent["value"])),
    )
    gallery = ThemeGallery(_FakeConfig())

    accent["value"] = "#123456"
    ThemeManager.instance().accent_changed.emit("#123456")

    assert gallery.cards["dark"].swatch_colors[2] == "#123456"
    gallery.deleteLater()


def test_keyboard_selection_and_selected_semantics(qapp, qtbot, monkeypatch):
    applied = []
    monkeypatch.setattr(ThemeManager, "set_theme_mode", lambda mode: applied.append(mode))
    config = _FakeConfig()
    gallery = ThemeGallery(config)
    qtbot.addWidget(gallery)

    light = gallery.cards["light"]
    light.setFocus()
    qtbot.keyClick(light, Qt.Key.Key_Space)

    assert config.config["theme_mode"] == "light"
    assert applied == ["light"]
    assert light.isChecked() is True
    assert light.badge.isHidden() is False
    assert "Selected" in light.accessibleDescription()

    dark = gallery.cards["dark"]
    dark.setFocus()
    qtbot.keyClick(dark, Qt.Key.Key_Return)

    assert config.config["theme_mode"] == "dark"
    assert applied == ["light", "dark"]
    assert dark.isChecked() is True
    assert light.isChecked() is False


def test_theme_cards_keep_their_height_in_tight_layouts(qapp):
    """The Button base class's SM minimum must not squash the preview card."""
    gallery = ThemeGallery(_FakeConfig())

    for card in gallery.cards.values():
        assert card.minimumHeight() >= 56
    gallery.deleteLater()


def test_sections_collapse_from_two_columns_to_one(qapp):
    gallery = ThemeGallery(_FakeConfig())
    section = gallery.sections["Themes"]

    assert section.columns_for_width(1200) == 5
    assert section.columns_for_width(900) == 4
    assert section.columns_for_width(700) == 3
    assert section.columns_for_width(400) == 1

    section.set_columns(1)
    assert section.column_count == 1
    section.set_columns(3)
    assert section.column_count == 3
    section.set_columns(5)
    assert section.column_count == 5
    gallery.deleteLater()
