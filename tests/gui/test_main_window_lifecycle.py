from unittest.mock import MagicMock

from PyQt6.QtWidgets import QMessageBox

from src.backend.storage.models import GameAnalysis, GameMetadata
from src.gui.main_window import MainWindow


def test_mainwindow_lifecycle_and_page_switch(qapp, qtbot, monkeypatch):
    """Test that MainWindow initializes with proper defaults and switches pages correctly."""
    window = MainWindow()
    qtbot.addWidget(window)
    assert window.windowTitle() == "Chess Analyzer Pro"
    # The hidden Explorer must not start a Stockfish search on launch.
    assert window.explorer_view.session.current_fen is None
    window.show()
    assert window.stack.currentIndex() == 0

    # Initial Hero Focus state (no game loaded)
    assert window.left_widget.isHidden()
    assert window.analysis_panel.isHidden()
    assert not window.welcome_panel.isHidden()
    assert not window.empty_state_cta.isHidden()
    assert window.btn_analyze.isHidden()
    assert window.board_widget.eval_bar.isHidden()
    assert window.left_widget.maximumWidth() == 420
    # Landing has no generic "Analysis View" header or duplicate Load button.
    assert window.analysis_header_bar.isHidden()
    assert not window.btn_load.isVisible()
    assert not window.btn_hero_load.isHidden()
    assert not window.btn_hero_paste.isHidden()

    # Historic puzzle can be revealed directly from the landing bar.
    qtbot.waitUntil(lambda: window.historic_info_bar.isVisible(), timeout=2000)
    window._load_random_historic_position()
    assert window.btn_hib_reveal.isEnabled()
    assert not window.btn_hib_reveal.isHidden()
    assert window.btn_hib_explore.isHidden()
    window._reveal_historic_move()
    assert window._historic_move_found is True
    assert window.btn_hib_reveal.isHidden()
    assert not window.btn_hib_explore.isHidden()
    assert window._hib_celebration.isVisible()

    # Dragging a PGN highlights the hero card as the drop target.
    window._set_drop_highlight(True)
    assert window.lbl_hero_hint.text() == "Drop to load game"
    assert window.lbl_hero_keys.isHidden()
    window._set_drop_highlight(False)
    assert window.lbl_hero_hint.text() == window._hero_hint_default
    assert not window.lbl_hero_keys.isHidden()

    # The revealed position opens directly in the Explorer.
    revealed_fen = window.board_widget.board.fen()
    window._explore_historic_position()
    qtbot.waitUntil(lambda: window.stack.currentIndex() == 1, timeout=2500)
    assert window.explorer_view.starting_fen == revealed_fen

    # Trigger switch to page 1
    window.switch_page(1)

    # Deferral: wait for singleShot + transition to complete
    qtbot.waitUntil(lambda: window.stack.currentIndex() == 1, timeout=2500)
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

    # Loading a game expands to 3-column analysis workspace
    window.load_game(game_active)
    assert not window.left_widget.isHidden()
    assert not window.analysis_panel.isHidden()
    assert not window.analysis_header_bar.isHidden()
    assert window.welcome_panel.isHidden()
    assert window.empty_state_cta.isHidden()
    assert not window.btn_analyze.isHidden()
    assert not window.board_widget.eval_bar.isHidden()

    window.load_game_from_history(game_active)
    qtbot.waitUntil(lambda: window.stack.currentIndex() == 0, timeout=2500)
    assert window.stack.currentIndex() == 0
    assert window.btn_load.isVisible()

    warning_called = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *args, **kwargs: warning_called.append(True))
    window.load_game_from_history(game_other)
    assert len(warning_called) == 1
    assert window.current_game.game_id == "active_1"

    window.close()
