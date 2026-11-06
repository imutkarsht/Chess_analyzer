# SPDX-License-Identifier: GPL-3.0-only
"""Typography tokens and generated QSS for the shared Label component."""

import pytest

from src.gui.styles import Styles
from src.gui.theme.manager import ThemeManager
from src.gui.theme.palette import LIGHT
from src.gui.theme.typography import (
    ALLOWED_SIZES,
    ALLOWED_WEIGHTS,
    ROLE_SPECS,
    TextRole,
    TextTone,
)


def test_every_role_and_tone_has_a_definition():
    assert set(ROLE_SPECS) == set(TextRole)
    assert len(TextTone) >= 10
    assert ROLE_SPECS[TextRole.PAGE_TITLE].size == 24
    assert ROLE_SPECS[TextRole.CARD_TITLE].uppercase is True
    assert ROLE_SPECS[TextRole.MONO].mono is True


def test_typography_qss_covers_roles_overrides_and_tones():
    qss = Styles.get_typography_qss()

    for role in TextRole:
        assert f'QLabel[role="{role.value}"]' in qss
    for size in ALLOWED_SIZES:
        assert f'QLabel[textSize="{size}"]' in qss
    for weight in ALLOWED_WEIGHTS:
        assert f'QLabel[textWeight="{weight}"]' in qss
    for tone in TextTone:
        assert f'QLabel[tone="{tone.value}"]' in qss

    assert "text-transform: uppercase" in qss
    assert "font-family: \"SFMono-Regular\"" in qss


def test_typography_qss_is_cached_until_the_style_revision_changes(monkeypatch):
    first = Styles.get_typography_qss()
    assert Styles.get_typography_qss() is first

    revision = ThemeManager.style_revision()
    monkeypatch.setattr(
        ThemeManager,
        "style_revision",
        classmethod(lambda cls: revision + 1),
    )
    second = Styles.get_typography_qss()

    assert second is not first


def test_typography_qss_follows_the_live_palette(monkeypatch):
    palette = LIGHT.with_accent("#123456")
    revision = ThemeManager.style_revision()

    monkeypatch.setattr(ThemeManager, "_palette", palette)
    monkeypatch.setattr(
        ThemeManager,
        "style_revision",
        classmethod(lambda cls: revision + 1000),
    )

    qss = Styles.get_typography_qss()

    assert (
        f'QLabel[tone="{TextTone.ACCENT.value}"] {{ color: {palette.accent}; '
        "background: transparent; border: none; }"
    ) in qss
    assert (
        f'QLabel[tone="{TextTone.PRIMARY.value}"] {{ color: {palette.text_primary}; '
        "background: transparent; border: none; }"
    ) in qss


@pytest.mark.parametrize("size", [0, 7, 19, 100])
def test_typography_qss_rejects_unguarded_sizes_in_label(qapp, size):
    # The component validates sizes; this guards the generated override set too.
    from src.gui.components import Label

    with pytest.raises(ValueError):
        Label("x", size=size)
