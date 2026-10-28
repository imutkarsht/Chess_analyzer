"""Behavioural checks for the redesigned Load Game dialog shell."""

import pytest
from PyQt6.QtCore import QDate

from src.gui.dialogs.load_game.helpers import format_display_date, game_row
from src.gui.dialogs.load_game.online_fetch_panel import (
    _STATE_ERROR,
    _STATE_FORM,
    _STATE_LOADING,
)
from src.gui.dialogs.load_game_dialog import LoadGameDialog


def test_game_row_formats_dates_and_metadata():
    assert format_display_date("2024-05-06") == "May 06, 2024"
    assert format_display_date("????.??.??") == "Unknown date"

    line1, line2 = game_row(
        date="2024-05-06",
        time_class="blitz",
        result="1-0",
        moves=42,
        white="Alice",
        black="Bob",
        white_elo=2100,
        black_elo=2000,
        opening="Sicilian Defense",
    )

    assert line1 == "May 06, 2024  ·  BLITZ  ·  1-0  ·  42 moves"
    assert line2 == "Alice (2100)  vs  Bob (2000)  ·  Sicilian Defense"


@pytest.fixture
def dialog(qtbot):
    dlg = LoadGameDialog()
    qtbot.addWidget(dlg)
    dlg.show()
    yield dlg
    dlg.close()


def test_shell_has_tabs_and_pgn_modes(dialog):
    panel = dialog._online_fetch_panel

    assert dialog.pages.count() == 2
    assert panel.date_picker.maximum() == QDate.currentDate()
    assert dialog.pgn_stack.count() == 2
    assert dialog.pgn_mode.value() == "file"


def test_switching_tabs_preserves_pgn_text(dialog):
    dialog.tabs.set_current_index(1)
    dialog.pgn_mode.set_value("text")
    dialog._on_pgn_mode_changed("text")
    dialog._pgn_text_panel._text_edit.setPlainText('[White "A"]\n\n1. e4 e5 *')

    dialog.tabs.set_current_index(0)
    dialog.tabs.set_current_index(1)

    assert "1. e4 e5" in dialog._pgn_text_panel._text_edit.toPlainText()


def test_switching_to_pgn_cancels_an_inflight_fetch(dialog):
    dialog.tabs.set_current_index(0)
    panel = dialog._online_fetch_panel

    class _FakeWorker:
        def __init__(self):
            self.cancelled = False

        def cancel(self):
            self.cancelled = True

    worker = _FakeWorker()
    panel._worker = worker
    panel.state_stack.setCurrentIndex(_STATE_LOADING)

    dialog.tabs.set_current_index(1)

    assert worker.cancelled is True
    assert panel._worker is None
    assert panel.state_stack.currentIndex() == _STATE_FORM


def test_mode_controls_visibility_and_button_copy(dialog):
    dialog.tabs.set_current_index(0)
    panel = dialog._online_fetch_panel

    panel.mode_selector.tabs.set_current_index(1)
    panel._on_mode_changed("date")
    assert panel.date_field.isVisible() is True
    assert panel.url_field.isVisible() is False
    assert panel.fetch_btn.text() == "Fetch games"

    panel.mode_selector.tabs.set_current_index(2)
    panel._on_mode_changed("url")
    assert panel.date_field.isVisible() is False
    assert panel.url_field.isVisible() is True
    assert panel.fetch_btn.text() == "Fetch game"


def test_url_platform_detection(dialog):
    panel = dialog._online_fetch_panel

    assert panel._platform_for_url("https://lichess.org/abcd1234") == "lichess"
    assert panel._platform_for_url("https://www.chess.com/game/live/123") == "chesscom"
    assert panel._platform_for_url("https://example.com/game") is None


def test_empty_and_error_states_have_recovery_paths(dialog):
    panel = dialog._online_fetch_panel

    panel._show_state(_STATE_ERROR)
    panel._error_message.setText("offline")
    panel._show_filters()
    assert panel.state_stack.currentIndex() == _STATE_FORM

    panel._show_state(3)
    assert panel._empty_icon.pixmap().isNull() is False
