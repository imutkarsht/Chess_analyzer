"""Tests for the keyboard shortcut system (issue #67).

Shortcuts are fired by emitting ``activated`` on the QShortcut bound to a key
sequence rather than by synthesising key presses: QShortcut only matches when
its window is the OS-active window, which is not reliable on CI runners. This
still verifies that the key is really bound, unambiguously, to the action.
"""

import pytest
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import QLabel, QLineEdit

from src.backend.storage.pgn_parser import PGNParser
from src.constants import PAGE_ANALYSIS, PAGE_EXPLORER, PAGE_NAMES
from src.utils.config import ConfigManager

PGN = """[Event "Shortcut test"]
[White "W"]
[Black "B"]
[Result "*"]

1. e4 e5 2. Nf3 Nc6 3. Bc4 Nd4 4. Nxe5 Qg5 *"""

# Classification per ply; critical moves (mistake/blunder/miss) at 2, 5 and 6.
CLASSIFICATIONS = ["Book", "Book", "Mistake", "Good", "Best", "Blunder", "Miss", "Best"]


@pytest.fixture
def isolated_app(tmp_path, monkeypatch):
    """Keep config.json and the history/cache DB in a temp dir.

    load_game() saves every game to history, so without this the test game
    would land in the developer's real analysis_cache.db. Tours are marked as
    seen so their overlays never cover the window. The network update check is
    stubbed in conftest.
    """
    for module in (
        "src.utils.config",
        "src.backend.storage.game_history",
        "src.backend.storage.cache",
    ):
        monkeypatch.setattr(f"{module}.get_user_data_dir", lambda: str(tmp_path))
    monkeypatch.setattr(ConfigManager, "_shared_config", None)
    monkeypatch.setattr(
        "src.gui.components.tour_manager.TourManager.has_seen_tour", lambda self, key: True
    )

    from src.gui.main_window import MainWindow

    return MainWindow


@pytest.fixture
def window(qapp, qtbot, isolated_app):
    win = isolated_app()
    qtbot.addWidget(win)
    yield win
    win._replay_timer.stop()
    win.close()


@pytest.fixture
def game_window(window):
    game = PGNParser.parse_pgn_text(PGN)[0]
    for move, classification in zip(game.moves, CLASSIFICATIONS, strict=True):
        move.classification = classification
    window.load_game(game)
    window.on_move_selected(-1)
    return window


def press(window, key: str):
    """Fire the single enabled QShortcut bound to ``key`` on ``window``."""
    seq = QKeySequence(key)
    matches = [s for s in window.findChildren(QShortcut) if s.isEnabled() and s.key() == seq]
    assert len(matches) == 1, f"expected exactly one shortcut for {key!r}, found {len(matches)}"
    matches[0].activated.emit()


def is_bound(window, key: str) -> bool:
    seq = QKeySequence(key)
    return any(s.isEnabled() and s.key() == seq for s in window.findChildren(QShortcut))


def index(window) -> int:
    return window.board_widget.current_move_index


def expect_move(qtbot, window, key: str, expected: int):
    """Press ``key`` and assert MainWindow.move_changed fires with ``expected``."""
    with qtbot.waitSignal(
        window.move_changed, timeout=1000, check_params_cb=lambda i: i == expected
    ):
        press(window, key)
    assert index(window) == expected


def expect_no_move(qtbot, window, key: str):
    with qtbot.assertNotEmitted(window.move_changed):
        press(window, key)


# --- Move navigation --------------------------------------------------------


@pytest.mark.parametrize(("next_key", "prev_key"), [("Right", "Left"), ("J", "K")])
def test_arrows_and_jk_navigate_by_default(game_window, qtbot, next_key, prev_key):
    expect_move(qtbot, game_window, next_key, 0)
    expect_move(qtbot, game_window, next_key, 1)
    expect_move(qtbot, game_window, prev_key, 0)


def test_arrows_and_jk_mix_freely(game_window, qtbot):
    expect_move(qtbot, game_window, "Right", 0)
    expect_move(qtbot, game_window, "J", 1)
    expect_move(qtbot, game_window, "Left", 0)
    expect_move(qtbot, game_window, "K", -1)


def test_first_and_last_move(game_window, qtbot):
    last = len(CLASSIFICATIONS) - 1
    expect_move(qtbot, game_window, "End", last)
    expect_move(qtbot, game_window, "Home", -1)
    expect_move(qtbot, game_window, "Up", last)
    expect_move(qtbot, game_window, "Down", -1)


def test_no_signal_past_either_end(game_window, qtbot):
    expect_no_move(qtbot, game_window, "Left")
    game_window.on_move_selected(len(CLASSIFICATIONS) - 1)
    expect_no_move(qtbot, game_window, "J")


def test_vim_preset_adds_h_and_l(game_window, qtbot):
    assert not is_bound(game_window, "L")

    game_window.shortcut_manager.apply_preset("vim")

    expect_move(qtbot, game_window, "L", 0)
    expect_move(qtbot, game_window, "J", 1)
    expect_move(qtbot, game_window, "H", 0)
    expect_move(qtbot, game_window, "K", -1)
    # Arrows keep working alongside the Vim keys.
    expect_move(qtbot, game_window, "Right", 0)


def test_switching_back_to_standard_unbinds_h_and_l(game_window):
    game_window.shortcut_manager.apply_preset("vim")
    game_window.shortcut_manager.apply_preset("standard")
    assert not is_bound(game_window, "L")
    assert not is_bound(game_window, "H")
    for key in ("Right", "Left", "J", "K"):
        assert is_bound(game_window, key)


@pytest.mark.parametrize("key", ["N", "Shift+Right"])
def test_next_critical_move(game_window, qtbot, key):
    expect_move(qtbot, game_window, key, 2)
    expect_move(qtbot, game_window, key, 5)
    expect_move(qtbot, game_window, key, 6)
    expect_no_move(qtbot, game_window, key)  # nothing after the last miss


@pytest.mark.parametrize("key", ["P", "Shift+Left"])
def test_previous_critical_move(game_window, qtbot, key):
    game_window.on_move_selected(len(CLASSIFICATIONS) - 1)
    expect_move(qtbot, game_window, key, 6)
    expect_move(qtbot, game_window, key, 5)
    expect_move(qtbot, game_window, key, 2)
    expect_no_move(qtbot, game_window, key)


def test_critical_navigation_needs_analysis(game_window, qtbot):
    for move in game_window.current_game.moves:
        move.classification = ""
    expect_no_move(qtbot, game_window, "N")
    assert "Analyze the game first" in game_window._status_lbl.text()


# --- Board ------------------------------------------------------------------


def test_f_flips_board(game_window):
    assert not game_window.board_widget.is_flipped
    press(game_window, "F")
    assert game_window.board_widget.is_flipped
    press(game_window, "F")
    assert not game_window.board_widget.is_flipped


def test_f_flips_explorer_board_on_explorer_page(game_window, qtbot):
    game_window.show()
    game_window.stack.setCurrentIndex(PAGE_EXPLORER)
    # FadedStackedWidget animates, so currentIndex() only changes once the fade ends.
    qtbot.waitUntil(lambda: game_window.stack.currentIndex() == PAGE_EXPLORER, timeout=2000)
    press(game_window, "F")
    assert game_window.explorer_view.board_widget.is_flipped
    assert not game_window.board_widget.is_flipped


def test_space_toggles_auto_replay(game_window, qtbot):
    game_window._replay_timer.setInterval(10)

    with qtbot.waitSignal(game_window.move_changed, timeout=2000):
        press(game_window, "Space")  # first tick advances on its own
    assert game_window._replay_timer.isActive()

    press(game_window, "Space")
    assert not game_window._replay_timer.isActive()
    with qtbot.assertNotEmitted(game_window.move_changed, wait=100):
        pass


def test_auto_replay_stops_at_last_move(game_window, qtbot):
    game_window._replay_timer.setInterval(5)
    press(game_window, "Space")
    qtbot.waitUntil(lambda: not game_window._replay_timer.isActive(), timeout=3000)
    assert index(game_window) == len(CLASSIFICATIONS) - 1


def test_space_at_end_restarts_from_beginning(game_window):
    game_window.on_move_selected(len(CLASSIFICATIONS) - 1)
    press(game_window, "Space")
    assert index(game_window) == -1
    assert game_window._replay_timer.isActive()


def test_space_without_game_does_not_start_replay(window):
    press(window, "Space")
    assert not window._replay_timer.isActive()


# --- Pages ------------------------------------------------------------------


def test_number_keys_switch_pages(window, qtbot):
    window.show()

    for page in reversed(range(len(PAGE_NAMES))):
        press(window, str(page + 1))
        qtbot.waitUntil(lambda p=page: window.stack.currentIndex() == p, timeout=2000)
        assert window.sidebar._nav_buttons[page].isChecked()
    assert window.stack.currentIndex() == PAGE_ANALYSIS


def test_rapid_page_switch_lands_on_last_page(window, qtbot):
    """Pressing 2 then 1 mid-fade must end on page 1, not get stuck on page 2."""
    window.show()

    press(window, "2")
    qtbot.waitUntil(lambda: window.stack.currentIndex() == PAGE_EXPLORER, timeout=2000)
    press(window, "1")  # fade-in to the explorer is still running here
    qtbot.waitUntil(lambda: window.stack.currentIndex() == PAGE_ANALYSIS, timeout=2000)
    qtbot.wait(400)
    assert window.stack.currentIndex() == PAGE_ANALYSIS
    assert window.stack.currentWidget().graphicsEffect() is None


# --- Settings card & help dialog -------------------------------------------


def test_settings_preset_combo_applies_and_persists(window):
    card = window.settings_view.shortcut_settings
    card.preset_combo.setCurrentIndex(card.preset_combo.findData("vim"))

    assert window.shortcut_manager.preset == "vim"
    assert window.config_manager.get("shortcut_preset") == "vim"
    assert is_bound(window, "J")

    texts = [label.text() for label in card.sheet.findChildren(QLabel)]
    assert "Right  /  J  /  L" in texts
    assert "Left  /  K  /  H" in texts


def test_saved_preset_restored_on_startup(qapp, qtbot, isolated_app):
    ConfigManager().set("shortcut_preset", "vim")

    win = isolated_app()
    qtbot.addWidget(win)
    try:
        assert win.shortcut_manager.preset == "vim"
        assert win.settings_view.shortcut_settings.current_preset() == "vim"
        assert is_bound(win, "H")
    finally:
        win.close()


def test_unknown_preset_falls_back_to_default(window):
    window.shortcut_manager.apply_preset("emacs")
    assert window.shortcut_manager.preset == "standard"
    assert is_bound(window, "Right")


def test_help_dialog_lists_active_bindings(window, qtbot):
    from src.gui.dialogs import ShortcutHelpDialog

    window.shortcut_manager.apply_preset("vim")
    dialog = ShortcutHelpDialog(window)
    qtbot.addWidget(dialog)

    texts = {label.text() for label in dialog.findChildren(QLabel)}
    assert "Flip board" in texts
    assert "Next mistake / blunder / miss" in texts
    assert any("J" in t and "Right" in t for t in texts)
    assert "Show this help" in texts


def test_duplicate_registration_rejected(window):
    with pytest.raises(ValueError):
        window.shortcut_manager.register("flip_board", "dup", "X", lambda: None)


# --- Upstream shortcuts now owned by ShortcutManager ------------------------


def test_escape_leaves_explorer(window, qtbot):
    window.show()
    window._go_to_page(PAGE_EXPLORER)
    qtbot.waitUntil(lambda: window.stack.currentIndex() == PAGE_EXPLORER, timeout=2000)
    press(window, "Escape")
    qtbot.waitUntil(lambda: window.stack.currentIndex() == PAGE_ANALYSIS, timeout=2000)


def test_variation_branch_keys_are_bound(window):
    assert window.shortcut_manager.keys_for("prev_branch") == ["Alt+Up"]
    assert window.shortcut_manager.keys_for("next_branch") == ["Alt+Down"]
    assert is_bound(window, "Alt+Up")
    assert is_bound(window, "Alt+Down")


# --- Typing guard -------------------------------------------------------------


def test_single_key_shortcuts_pause_while_typing(window, qtbot):
    window.show()
    qtbot.waitExposed(window)
    field = window.settings_view.chesscom_input
    window.shortcut_manager._on_focus_changed(None, field)

    for key in ("F", "J", "N", "Space", "1"):
        assert not is_bound(window, key), key
    # Arrows and modifier combos stay live: the text field handles its own.
    assert is_bound(window, "Right")
    assert is_bound(window, "Ctrl+O")

    window.shortcut_manager._on_focus_changed(field, None)
    assert is_bound(window, "F")


def test_read_only_text_does_not_block_shortcuts(window):
    viewer = QLineEdit()
    viewer.setReadOnly(True)
    window.shortcut_manager._on_focus_changed(None, viewer)
    assert is_bound(window, "J")


def test_preset_switch_while_typing_keeps_keys_paused(window):
    field = window.settings_view.chesscom_input
    window.shortcut_manager._on_focus_changed(None, field)
    window.shortcut_manager.apply_preset("vim")
    assert not is_bound(window, "H")
    window.shortcut_manager._on_focus_changed(field, None)
    assert is_bound(window, "H")
