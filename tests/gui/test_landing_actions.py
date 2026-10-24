"""Landing quick actions that do not need a full MainWindow instance."""

from PyQt6.QtWidgets import QApplication

from src.gui.main_window import MainWindow


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


def _with_clipboard(text: str, action):
    clipboard = QApplication.clipboard()
    original = clipboard.text()
    try:
        clipboard.setText(text)
        return action()
    finally:
        clipboard.setText(original)


def test_paste_quick_action_loads_clipboard_pgn(qapp):
    pgn = '[Event "Test"]\n\n1. e4 e5 1-0'
    stub = _PasteStub()

    _with_clipboard(pgn, lambda: MainWindow.paste_pgn_from_clipboard(stub))

    assert stub.loaded == [pgn]
    assert stub.dialogs == []


def test_paste_quick_action_opens_pgn_tab_for_non_pgn(qapp):
    stub = _PasteStub()

    _with_clipboard(
        "not a game", lambda: MainWindow.paste_pgn_from_clipboard(stub)
    )

    assert stub.loaded == []
    assert stub.dialogs == [(1, "not a game")]
