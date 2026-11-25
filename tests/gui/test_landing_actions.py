"""Landing quick actions that do not need a full MainWindow instance."""

from PyQt6.QtWidgets import QApplication

from src.gui.app.game_loading_controller import GameLoadingController
from src.gui.components import Button, WelcomePanel


class _PasteStub:
    """Captures the two outcomes of the landing Paste PGN action."""

    def __init__(self):
        self.loaded: list[str] = []
        self.dialogs: list[tuple[int, str | None]] = []

    def _parse_and_load_game(self, text, status_msg="", source_data=None):
        self.loaded.append(text)
        return True

    def open_load_dialog(self, initial_source=0, initial_text=None):
        self.dialogs.append((initial_source, initial_text))

    def controller(self) -> GameLoadingController:
        controller = GameLoadingController()
        controller._parse_and_load_game = self._parse_and_load_game
        controller.open_load_dialog = self.open_load_dialog
        return controller


def _with_clipboard(text: str, action):
    clipboard = QApplication.clipboard()
    original = clipboard.text()
    try:
        clipboard.setText(text)
        return action()
    finally:
        clipboard.setText(original)


def test_welcome_panel_actions_all_have_tooltips(qtbot):
    panel = WelcomePanel()
    qtbot.addWidget(panel)

    buttons = panel.findChildren(Button)
    assert len(buttons) == 6
    assert all(button.toolTip() for button in buttons)


def test_paste_quick_action_loads_clipboard_pgn(qapp):
    pgn = '[Event "Test"]\n\n1. e4 e5 1-0'
    stub = _PasteStub()

    _with_clipboard(pgn, lambda: stub.controller().paste_pgn_from_clipboard())

    assert stub.loaded == [pgn]
    assert stub.dialogs == []


def test_paste_quick_action_opens_pgn_tab_for_non_pgn(qapp):
    stub = _PasteStub()

    _with_clipboard(
        "not a game", lambda: stub.controller().paste_pgn_from_clipboard()
    )

    assert stub.loaded == []
    assert stub.dialogs == [(1, "not a game")]
