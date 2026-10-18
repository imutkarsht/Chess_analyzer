"""
Tests for MainWindow geometry persistence.

Verifies that the last-known window position and size are saved on
close and restored on the next launch.
"""

import json
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


def test_window_geometry_save_and_restore(qtbot, isolated_config):
    """Closing the window saves geometry, and a new window restores it."""
    from src.gui.main_window import MainWindow

    # 1. Test save on close
    window = MainWindow()
    qtbot.addWidget(window)

    target_pos = _safe_origin(qtbot)
    target_size = QSize(1200, 800)
    window.resize(target_size)
    window.move(target_pos)
    QGuiApplication.processEvents()

    window.close()
    QGuiApplication.processEvents()

    assert isolated_config.exists()
    saved = json.loads(isolated_config.read_text())
    state = saved["window_state"]

    assert state["width"] == 1200
    assert state["height"] == 800
    assert state["x"] == target_pos.x()
    assert state["y"] == target_pos.y()

    # 2. Test restore on a new instance
    with patch("src.utils.config.get_user_data_dir", return_value=str(isolated_config.parent)):
        restored = MainWindow()
        qtbot.addWidget(restored)

    assert restored.width() == 1200
    assert restored.height() == 800
    assert restored.x() == target_pos.x()
    assert restored.y() == target_pos.y()
    restored.close()


def test_restore_window_state_defensive(qtbot, isolated_config):
    """_restore_window_state rejects offscreen coordinates, booleans, and malformed types."""
    from src.gui.main_window import MainWindow

    with patch("src.utils.config.get_user_data_dir", return_value=str(isolated_config.parent)):
        window = MainWindow()
        qtbot.addWidget(window)

    screen = QGuiApplication.primaryScreen().availableGeometry()

    # Case 1: Off-screen position is rejected; size is applied
    window.config_manager.set(
        "window_state",
        {"x": -100_000, "y": -100_000, "width": 1024, "height": 768},
    )
    window._restore_window_state()
    assert window.width() == 1024
    assert window.height() == 768
    assert screen.intersects(window.frameGeometry())

    # Case 2: Booleans are rejected (not coerced to 1px)
    window.config_manager.set(
        "window_state",
        {"x": True, "y": False, "width": True, "height": False},
    )
    window._restore_window_state()
    assert window.width() > 100
    assert window.height() > 100
    assert screen.intersects(window.frameGeometry())

    # Case 3: Strings, lists, None, dicts are rejected safely
    window.config_manager.set(
        "window_state",
        {"x": "100", "y": None, "width": [1024], "height": {"v": 768}},
    )
    window._restore_window_state()
    assert window.width() > 100
    assert window.height() > 100
    assert screen.intersects(window.frameGeometry())
    window.close()
