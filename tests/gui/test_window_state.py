"""
Tests for MainWindow geometry persistence.

Verifies that the last-known window position and size are saved on
close and restored on the next launch.

Booting a full ``MainWindow`` costs seconds, so the coercion rules are
exercised against a bare ``QMainWindow`` that borrows the two geometry
methods, and the save/restore round-trip reuses a single window.
"""

from unittest.mock import patch

import pytest
from PyQt6.QtCore import QPoint, QSize
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import QMainWindow

from src.gui.main_window import MainWindow


class _FakeConfig:
    def __init__(self, data=None):
        self.data = dict(data or {})

    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value):
        self.data[key] = value


@pytest.fixture
def isolated_config(tmp_path, monkeypatch):
    """Point the ConfigManager at a per-test directory."""
    monkeypatch.setattr("src.utils.config.get_user_data_dir", lambda: str(tmp_path))
    return tmp_path / "config.json"


def _geometry_host(config: _FakeConfig) -> QMainWindow:
    """A bare window wired to the real geometry methods, without MainWindow's boot cost."""
    window = QMainWindow()
    window.config_manager = config
    window._restore_window_state = MainWindow._restore_window_state.__get__(window)
    window._save_window_state = MainWindow._save_window_state.__get__(window)
    window.resize(800, 600)
    return window


def _safe_origin():
    """A position guaranteed to lie on a connected screen."""
    screen = QGuiApplication.primaryScreen().availableGeometry()
    return QPoint(screen.x() + 50, screen.y() + 50)


@pytest.mark.parametrize(
    "state",
    [
        # Off-screen position is rejected; size is still applied.
        {"x": -100_000, "y": -100_000, "width": 1024, "height": 768},
        # Booleans must not be coerced to 1px.
        {"x": True, "y": False, "width": True, "height": False},
        # Strings, lists, None and dicts are rejected safely.
        {"x": "100", "y": None, "width": [1024], "height": {"v": 768}},
        # Malformed container must not raise.
        ["not", "a", "dict"],
    ],
)
def test_restore_window_state_defensive(qapp, state):
    screen = QGuiApplication.primaryScreen().availableGeometry()
    config = _FakeConfig({"window_state": state})
    window = _geometry_host(config)

    window._restore_window_state()

    assert window.width() > 100
    assert window.height() > 100
    assert screen.intersects(window.frameGeometry())
    window.close()


def test_remember_geometry_toggle_skips_restore_and_save(qapp):
    config = _FakeConfig(
        {
            "remember_window_geometry": False,
            "window_state": {"x": 40, "y": 40, "width": 1111, "height": 777},
        }
    )
    window = _geometry_host(config)

    window._restore_window_state()
    assert (window.width(), window.height()) == (800, 600)

    window.resize(1234, 789)
    window._save_window_state()
    assert config.get("window_state")["width"] == 1111

    config.set("remember_window_geometry", True)
    window._save_window_state()
    assert config.get("window_state")["width"] == 1234
    window.close()


def test_window_geometry_save_and_restore(qtbot, isolated_config):
    """Closing saves geometry, and restore applies it to the same window."""
    with patch("src.utils.config.get_user_data_dir", return_value=str(isolated_config.parent)):
        window = MainWindow()
        qtbot.addWidget(window)

        target_pos = _safe_origin()
        window.resize(QSize(1200, 800))
        window.move(target_pos)
        QGuiApplication.processEvents()

        window.close()
        QGuiApplication.processEvents()

    assert isolated_config.exists()
    state = window.config_manager.get("window_state")
    assert (state["width"], state["height"]) == (1200, 800)
    assert (state["x"], state["y"]) == (target_pos.x(), target_pos.y())

    # Restore on the same instance: shrink first so the assertions are meaningful.
    window.resize(640, 480)
    window._restore_window_state()
    assert (window.width(), window.height()) == (1200, 800)
    assert (window.x(), window.y()) == (target_pos.x(), target_pos.y())
