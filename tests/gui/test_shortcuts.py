"""Tests for the keyboard shortcut system (issue #67).

Shortcuts are fired by emitting ``activated`` on the QShortcut bound to a key
sequence rather than by synthesising key presses: QShortcut only matches when
its window is the OS-active window, which is not reliable on CI runners. This
still verifies that the key is really bound, unambiguously, to the action.

Booting MainWindow costs seconds, so the whole module shares one window and
``_reset`` puts it back into a known state before every test.
"""

import pytest
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import QLabel, QLineEdit

from src.backend.storage.pgn_parser import PGNParser
from src.constants import PAGE_ANALYSIS, PAGE_EXPLORER, REPLAY_INTERVAL_MS
from src.utils.config import ConfigManager

PGN = """[Event "Shortcut test"]
[White "W"]
[Black "B"]
[Result "*"]

1. e4 e5 2. Nf3 Nc6 3. Bc4 Nd4 4. Nxe5 Qg5 *"""

# Classification per ply; critical moves (mistake/blunder/miss) at 2, 5 and 6.
CLASSIFICATIONS = ["Book", "Book", "Mistake", "Good", "Best", "Blunder", "Miss", "Best"]
LAST = len(CLASSIFICATIONS) - 1


@pytest.fixture(scope="module")
def shared_window(qapp, tmp_path_factory):
    """One MainWindow for the module, with config/history/cache in a temp dir.

    load_game() saves every game to history, so without the path patches the
    test game would land in the developer's real analysis_cache.db. Tours are
    reported as seen so their overlays never cover the window. The network
    update check is stubbed in conftest.
    """
    data_dir = str(tmp_path_factory.mktemp("shortcuts_data"))
    with pytest.MonkeyPatch.context() as mp:
        for module in (
            "src.utils.config",
            "src.backend.storage.game_history",
            "src.backend.storage.cache",
        ):
            mp.setattr(f"{module}.get_user_data_dir", lambda: data_dir)
        mp.setattr(ConfigManager, "_shared_config", None)
        mp.setattr(
            "src.gui.components.tour_manager.TourManager.has_seen_tour", lambda self, key: True
        )
        # Saved before boot so startup restoration of the preset can be checked.
        ConfigManager().set("shortcut_preset", "vim")

        from src.gui.main_window import MainWindow

        win = MainWindow()
        win.preset_at_startup = win.shortcut_manager.preset
        win.show()

        game = PGNParser.parse_pgn_text(PGN)[0]
        win.load_game(game)
        win.test_game = win.current_game
        yield win

        win._replay_timer.stop()
        win.close()


@pytest.fixture
def window(shared_window, qtbot):
    win = shared_window
    sm = win.shortcut_manager

    win._replay_timer.stop()
    win._replay_timer.setInterval(REPLAY_INTERVAL_MS)
    sm._on_focus_changed(None, None)
    card = win.settings_view.shortcut_settings
    card.preset_combo.setCurrentIndex(card.preset_combo.findData("standard"))
    sm.apply_preset("standard")

    win.current_game = win.test_game
    for move, classification in zip(win.current_game.moves, CLASSIFICATIONS, strict=True):
        move.classification = classification
    if win.board_widget.is_flipped:
        win.flip_board()
    if win.explorer_view.board_widget.is_flipped:
        win.explorer_view._flip_board()
    if win.stack.currentIndex() != PAGE_ANALYSIS:
        win.sidebar.set_active(PAGE_ANALYSIS)
        win._do_switch_page(PAGE_ANALYSIS)
    win.on_move_selected(-1)
    return win


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
def test_step_keys_navigate_by_default(window, qtbot, next_key, prev_key):
    expect_move(qtbot, window, next_key, 0)
    expect_move(qtbot, window, next_key, 1)
    expect_move(qtbot, window, prev_key, 0)
    expect_move(qtbot, window, prev_key, -1)
    expect_no_move(qtbot, window, prev_key)  # already at the start position


def test_jump_keys_and_game_end(window, qtbot):
    expect_move(qtbot, window, "End", LAST)
    expect_no_move(qtbot, window, "J")  # nothing after the last move
    expect_move(qtbot, window, "Home", -1)
    expect_move(qtbot, window, "Up", LAST)
    expect_move(qtbot, window, "Down", -1)


def test_vim_preset_adds_h_and_l_and_reverts(window, qtbot):
    assert not is_bound(window, "L")

    window.shortcut_manager.apply_preset("vim")
    expect_move(qtbot, window, "L", 0)
    expect_move(qtbot, window, "J", 1)
    expect_move(qtbot, window, "H", 0)
    expect_move(qtbot, window, "Right", 1)  # arrows keep working alongside

    window.shortcut_manager.apply_preset("standard")
    assert not is_bound(window, "L") and not is_bound(window, "H")
    assert all(is_bound(window, k) for k in ("Right", "Left", "J", "K"))


@pytest.mark.parametrize(
    ("key", "start", "stops"),
    [
        ("N", -1, [2, 5, 6]),
        ("Shift+Right", -1, [2, 5, 6]),
        ("P", LAST, [6, 5, 2]),
        ("Shift+Left", LAST, [6, 5, 2]),
    ],
)
def test_critical_move_jumps(window, qtbot, key, start, stops):
    window.on_move_selected(start)
    for expected in stops:
        expect_move(qtbot, window, key, expected)
    expect_no_move(qtbot, window, key)  # no more critical moves that way
    assert "No mistakes" in window._status_lbl.text()


def test_critical_navigation_needs_analysis(window, qtbot):
    for move in window.current_game.moves:
        move.classification = ""
    expect_no_move(qtbot, window, "N")
    assert "Analyze the game first" in window._status_lbl.text()


# --- Board ------------------------------------------------------------------


def test_f_flips_the_board_of_the_current_page(window, qtbot):
    press(window, "F")
    assert window.board_widget.is_flipped
    press(window, "F")
    assert not window.board_widget.is_flipped

    window.sidebar.set_active(PAGE_EXPLORER)
    window._do_switch_page(PAGE_EXPLORER)
    press(window, "F")
    assert window.explorer_view.board_widget.is_flipped
    assert not window.board_widget.is_flipped


def test_space_starts_and_pauses_replay(window, qtbot):
    window._replay_timer.setInterval(10)

    with qtbot.waitSignal(window.move_changed, timeout=2000):
        press(window, "Space")  # first tick advances on its own
    assert window._replay_timer.isActive()

    press(window, "Space")
    assert not window._replay_timer.isActive()
    with qtbot.assertNotEmitted(window.move_changed, wait=50):
        pass


def test_replay_stops_at_end_and_space_restarts(window, qtbot):
    window._replay_timer.setInterval(5)
    press(window, "Space")
    qtbot.waitUntil(lambda: not window._replay_timer.isActive(), timeout=3000)
    assert index(window) == LAST

    with qtbot.waitSignal(window.move_changed, check_params_cb=lambda i: i == -1):
        press(window, "Space")  # at the end: rewinds before replaying
    assert window._replay_timer.isActive()


def test_space_without_game_does_not_start_replay(window):
    window.current_game = None
    press(window, "Space")
    assert not window._replay_timer.isActive()


# --- Pages ------------------------------------------------------------------


# --- Presets, settings card & help dialog ----------------------------------


def test_saved_preset_restored_on_startup(window):
    assert window.preset_at_startup == "vim"


def test_settings_preset_combo_applies_and_persists(window):
    card = window.settings_view.shortcut_settings
    card.preset_combo.setCurrentIndex(card.preset_combo.findData("vim"))

    assert window.shortcut_manager.preset == "vim"
    assert window.config_manager.get("shortcut_preset") == "vim"
    assert is_bound(window, "H")


def test_unknown_preset_falls_back_to_default(window):
    window.shortcut_manager.apply_preset("emacs")
    assert window.shortcut_manager.preset == "standard"
    assert is_bound(window, "Right")


def test_duplicate_registration_rejected(window):
    with pytest.raises(ValueError):
        window.shortcut_manager.register("flip_board", "dup", "X", lambda: None)


def test_help_dialog_lists_active_bindings(window, qtbot):
    from src.gui.dialogs import ShortcutHelpDialog

    window.shortcut_manager.apply_preset("vim")
    dialog = ShortcutHelpDialog(window)
    qtbot.addWidget(dialog)

    texts = {label.text() for label in dialog.findChildren(QLabel)}
    assert {"Flip board", "Next mistake / blunder / miss", "Show this help"} <= texts
    right = QKeySequence("Right").toString(QKeySequence.SequenceFormat.NativeText)
    assert f"{right}  /  J  /  L" in texts


# --- Typing guard -------------------------------------------------------------


def test_single_key_shortcuts_pause_while_typing(window):
    sm = window.shortcut_manager
    field = window.settings_view.chesscom_input
    sm._on_focus_changed(None, field)

    assert not any(is_bound(window, k) for k in ("F", "J", "N", "Space", "1"))
    # Arrows and modifier combos stay live: the text field handles its own.
    assert is_bound(window, "Right") and is_bound(window, "Ctrl+O")

    # A preset switch while typing must not re-enable the new single keys.
    sm.apply_preset("vim")
    assert not is_bound(window, "H")

    sm._on_focus_changed(field, None)
    assert is_bound(window, "F") and is_bound(window, "H")


def test_read_only_text_does_not_block_shortcuts(window):
    viewer = QLineEdit()
    viewer.setReadOnly(True)
    window.shortcut_manager._on_focus_changed(None, viewer)
    assert is_bound(window, "J")
