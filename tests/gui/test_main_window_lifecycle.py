from unittest.mock import MagicMock

from PyQt6.QtWidgets import QMessageBox

from src.backend.storage.models import GameAnalysis, GameMetadata
from src.gui.main_window import MainWindow


def test_mainwindow_lifecycle_and_page_switch(qapp, qtbot, monkeypatch):
    """Test that MainWindow initializes with proper defaults and switches pages correctly."""
    window = MainWindow()
    qtbot.addWidget(window)
    assert window.windowTitle() == "Chess Analyzer Pro"
    window.show()
    assert window.stack.currentIndex() == 0

    # Trigger switch to page 1
    window.switch_page(1)

    # Deferral: wait for singleShot + transition to complete
    qtbot.waitUntil(lambda: window.stack.currentIndex() == 1, timeout=1000)
    assert window.stack.currentIndex() == 1

    # Guard ongoing analysis: clicking active game returns to page 0; other game is blocked
    mock_worker = MagicMock()
    mock_worker.isRunning.return_value = True
    window.worker = mock_worker

    meta = GameMetadata(
        white="W", black="B", result="1-0", date="2024.01.01", event="E", headers={}
    )
    game_active = GameAnalysis(game_id="active_1", metadata=meta, moves=[])
    game_other = GameAnalysis(game_id="other_2", metadata=meta, moves=[])
    window.current_game = game_active

    window.load_game_from_history(game_active)
    qtbot.waitUntil(lambda: window.stack.currentIndex() == 0, timeout=1000)
    assert window.stack.currentIndex() == 0

    warning_called = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *args, **kwargs: warning_called.append(True))
    window.load_game_from_history(game_other)
    assert len(warning_called) == 1
    assert window.current_game.game_id == "active_1"

    window.close()
