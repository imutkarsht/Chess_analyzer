"""
Tests for MainWindow geometry persistence.

Verifies that the last-known window position and size are saved on
close and restored on the next launch.
"""
import json
import os
from unittest.mock import patch

import pytest
from PyQt6.QtCore import QPoint, QSize
from PyQt6.QtGui import QGuiApplication


@pytest.fixture
def isolated_config(tmp_path, monkeypatch):
    """Point the ConfigManager at a per-test directory."""
    monkeypatch.setattr("src.utils.config.get_user_data_dir", lambda: str(tmp_path))
    return tmp_path / "config.json"


def _safe_origin(qtbot):
    """A position guaranteed to lie on a connected screen."""
    screen = QGuiApplication.primaryScreen().availableGeometry()
    return QPoint(screen.x() + 50, screen.y() + 50)


def test_close_saves_current_geometry(qtbot, isolated_config):
    """Closing the window writes the current geometry to config.json."""
    from src.gui.main_window import MainWindow

    window = MainWindow()
    qtbot.addWidget(window)

    target_pos = _safe_origin(qtbot)
    target_size = QSize(1200, 800)
    window.resize(target_size)
    window.move(target_pos)
    # Process events so the resize/move are actually applied before save.
    QGuiApplication.processEvents()

    window.close()
    QGuiApplication.processEvents()

    assert isolated_config.exists()
    saved = json.loads(isolated_config.read_text())
    state = saved["window_state"]

    assert state["width"] == 1200
    assert state["height"] == 800
    # Qt may apply a small offset for the window frame on some platforms;
    # assert the saved point is the one we requested, exact match is the
    # contract when running on a real desktop window manager.
    assert state["x"] == target_pos.x()
    assert state["y"] == target_pos.y()


def test_restore_uses_saved_geometry(qtbot, isolated_config):
    """A new MainWindow adopts the geometry stored in config.json."""
    from src.gui.main_window import MainWindow

    # Seed a config with a known geometry on a real screen.
    screen = QGuiApplication.primaryScreen().availableGeometry()
    seed = {
        "engine_path": "stockfish",
        "theme": "dark",
        "window_state": {
            "x": screen.x() + 25,
            "y": screen.y() + 35,
            "width": 1100,
            "height": 700,
        },
    }
    isolated_config.write_text(json.dumps(seed))

    with patch("src.utils.config.get_user_data_dir", return_value=str(isolated_config.parent)):
        window = MainWindow()
        qtbot.addWidget(window)

    assert window.width() == 1100
    assert window.height() == 700
    assert window.x() == screen.x() + 25
    assert window.y() == screen.y() + 35


def test_offscreen_position_is_ignored(qtbot, isolated_config):
    """A saved position that is off-screen must not be applied."""
    from src.gui.main_window import MainWindow

    # A position far outside any real monitor.
    seed = {
        "window_state": {
            "x": -100_000,
            "y": -100_000,
            "width": 1024,
            "height": 768,
        },
    }
    isolated_config.write_text(json.dumps(seed))

    with patch("src.utils.config.get_user_data_dir", return_value=str(isolated_config.parent)):
        window = MainWindow()
        qtbot.addWidget(window)

    # Size is still applied (we always trust it), but the position is
    # left to Qt's default, which keeps the window reachable.
    assert window.width() == 1024
    assert window.height() == 768
    screen = QGuiApplication.primaryScreen().availableGeometry()
    assert screen.intersects(window.frameGeometry())


# ---------------------------------------------------------------------------
# Defensive parsing: config may hold surprising values (booleans, strings,
# None, missing keys). _restore_window_state must never crash and must
# never silently coerce a bool to 1 px.
# ---------------------------------------------------------------------------

def test_restore_ignores_boolean_dimensions(qtbot, isolated_config):
    """A `True` value in the config must not be treated as the integer 1.

    In Python, ``isinstance(True, int)`` is True and ``int(True) == 1``,
    so the previous `isinstance(value, (int, float))` check would have
    silently turned a stray boolean into a 1-pixel window. The fix is
    to reject booleans explicitly.
    """
    from src.gui.main_window import MainWindow

    seed = {
        "window_state": {
            "x": True,        # would otherwise become 1
            "y": False,       # would otherwise become 0
            "width": True,    # would otherwise become 1
            "height": False,  # would otherwise become 0
        },
    }
    isolated_config.write_text(json.dumps(seed))

    with patch("src.utils.config.get_user_data_dir", return_value=str(isolated_config.parent)):
        window = MainWindow()
        qtbot.addWidget(window)

    # The window must keep a sensible default size and stay on a
    # reachable position, i.e. it must not have been resized to 1×1.
    assert window.width() > 100
    assert window.height() > 100
    screen = QGuiApplication.primaryScreen().availableGeometry()
    assert screen.intersects(window.frameGeometry())


def test_restore_ignores_non_numeric_dimensions(qtbot, isolated_config):
    """String, None, and list values must not crash the restore code."""
    from src.gui.main_window import MainWindow

    seed = {
        "window_state": {
            "x": "100",        # str, not int
            "y": None,
            "width": [1024],   # list, not int
            "height": {"v": 768},  # dict, not int
        },
    }
    isolated_config.write_text(json.dumps(seed))

    with patch("src.utils.config.get_user_data_dir", return_value=str(isolated_config.parent)):
        window = MainWindow()
        qtbot.addWidget(window)

    # All values were rejected, so we get Qt's default geometry, which
    # is at least sane and visible.
    assert window.width() > 100
    assert window.height() > 100
    screen = QGuiApplication.primaryScreen().availableGeometry()
    assert screen.intersects(window.frameGeometry())
