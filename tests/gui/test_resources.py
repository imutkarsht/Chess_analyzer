# SPDX-License-Identifier: GPL-3.0-only
"""Resource manager degradation when QtMultimedia is unavailable."""

from __future__ import annotations

import src.gui.resources as resources


def test_sound_is_disabled_when_qtmultimedia_is_unavailable(qapp, monkeypatch):
    """Headless/minimal Linux installs must still construct the manager."""
    monkeypatch.setattr(resources, "QSoundEffect", None)
    monkeypatch.setattr(resources, "_SOUND_AVAILABLE", False)
    monkeypatch.setattr(resources.ResourceManager, "_instance", None)

    manager = resources.ResourceManager()

    assert manager.sounds == {}
    manager.play_sound("move")
