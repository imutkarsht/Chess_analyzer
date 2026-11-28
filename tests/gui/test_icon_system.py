# SPDX-License-Identifier: GPL-3.0-only
"""Central icon resolution, icon packs, and style switching."""

from PyQt6.QtGui import QIcon

from src.gui.components import Button, Icon, IconLabel
from src.gui.icons import (
    IconSpec,
    IconStyleManager,
    IconVariant,
    icon_key,
    icon_pixmap,
    icon_qicon,
)


class _HeartPack:
    id = "test-heart"
    display_name = "Test Heart"
    default_variant = IconVariant.SOLID
    scale_factor = 1.0

    def glyph(self, key: str, variant: IconVariant) -> str | None:
        if key != "star":
            return None
        if variant is IconVariant.OUTLINE:
            return "fa5.heart"
        return "fa5s.heart"


def test_icon_key_normalizes_legacy_font_names():
    assert icon_key("fa5s.play") == "play"
    assert icon_key("fa6s.repeat") == "repeat"
    assert icon_key("mdi6.chess-knight") == "chess-knight"
    assert icon_key("assets/icons/chesscom.png") == "assets/icons/chesscom.png"


def test_resolver_supports_semantic_legacy_and_asset_icons(qapp):
    assert not icon_qicon("play", "#FFFFFF").isNull()
    assert not icon_qicon("fa5s.play", "#FFFFFF").isNull()
    assert not icon_qicon("assets/icons/chesscom.png", "#FFFFFF").isNull()


def test_phosphor_outline_pack_covers_common_keys(qapp):
    previous = IconStyleManager.active_pack_id()
    try:
        assert IconStyleManager.set_pack("phosphor") is True
        assert not icon_qicon("play", "#FFFFFF").isNull()
        assert not icon_qicon("star", "#FFFFFF").isNull()
        assert not icon_qicon("history", "#FFFFFF").isNull()
    finally:
        IconStyleManager.set_pack(previous)


def test_pack_falls_back_to_the_default_glyph():
    IconStyleManager.register_pack(_HeartPack())

    assert (
        IconStyleManager.resolve_glyph("star", pack_id="test-heart")
        == "fa5s.heart"
    )
    assert (
        IconStyleManager.resolve_glyph("play", pack_id="test-heart")
        == "fa5s.play"
    )
    assert IconStyleManager.resolve_glyph("fa6s.repeat") == "fa6s.repeat"


def test_variant_is_part_of_glyph_resolution():
    IconStyleManager.register_pack(_HeartPack())

    assert (
        IconStyleManager.resolve_glyph(
            "star", IconVariant.OUTLINE, "test-heart"
        )
        == "fa5.heart"
    )
    assert IconStyleManager.resolve_glyphs(
        "star", IconVariant.OUTLINE, "test-heart"
    )[:2] == ["fa5.heart", "fa5s.heart"]


def test_style_switch_re_resolves_labels_and_buttons(qtbot):
    IconStyleManager.register_pack(_HeartPack())
    previous = IconStyleManager.active_pack_id()
    try:
        label = IconLabel("star", size=16)
        button = Button(
            icon=IconSpec("star"),
            icon_position="only",
            tooltip="Star",
        )
        icon = Icon("star", size=16)
        qtbot.addWidget(label)
        qtbot.addWidget(button)
        qtbot.addWidget(icon)

        before_label = label.pixmap().cacheKey()
        before_button = button.icon().cacheKey()
        before_icon = icon.pixmap().cacheKey()
        assert before_label != 0
        assert before_button != 0
        assert before_icon != 0

        with qtbot.waitSignal(IconStyleManager.instance().style_changed):
            assert IconStyleManager.set_pack("test-heart") is True

        assert label.pixmap().cacheKey() != before_label
        assert button.icon().cacheKey() != before_button
        assert icon.pixmap().cacheKey() != before_icon
    finally:
        IconStyleManager.set_pack(previous)


def test_style_packs_change_supported_glyphs_and_fall_back(qapp):
    previous = IconStyleManager.active_pack_id()
    try:
        assert IconStyleManager.set_pack("fontawesome") is True
        solid_star = icon_pixmap("star", "#FFFFFF", 32)

        assert IconStyleManager.set_pack("phosphor") is True
        outline_star = icon_pixmap("star", "#FFFFFF", 32)
        assert solid_star is not None and outline_star is not None
        assert solid_star.toImage() != outline_star.toImage()

        # Phosphor has no chess pieces; those fall back to the solid pack.
        solid_chess = icon_pixmap(
            "chess-king", "#FFFFFF", 32, IconVariant.SOLID
        )
        outline_chess = icon_pixmap("chess-king", "#FFFFFF", 32)
        assert solid_chess is not None and outline_chess is not None
        assert solid_chess.toImage() == outline_chess.toImage()
    finally:
        IconStyleManager.set_pack(previous)


def test_icon_spec_applies_fallback_and_widget_overrides(qtbot):
    label = IconLabel(IconSpec("not-a-real-icon", fallback="?", size=20))
    qtbot.addWidget(label)

    assert label.text() == "?"
    assert label.width() == 20

    button = Button(icon=IconSpec("play", color="#FF0000"), icon_position="only")
    qtbot.addWidget(button)

    assert isinstance(button.icon(), QIcon)
    assert not button.icon().isNull()
    assert icon_pixmap("play", "#FF0000", 16) is not None


def test_unknown_pack_is_rejected():
    assert IconStyleManager.set_pack("not-registered") is False
