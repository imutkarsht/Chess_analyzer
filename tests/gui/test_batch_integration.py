"""MainWindow batch gating, recovery, and exit integration."""

from unittest.mock import MagicMock

import chess
import pytest
from PyQt6.QtGui import QCloseEvent
from PyQt6.QtWidgets import QMessageBox

from src.backend.models.analysis_batch import (
    BATCH_PAUSED,
    AnalysisBatch,
    AnalysisBatchItem,
)
from src.backend.storage.game_history import GameHistoryManager
from src.backend.storage.models import GameAnalysis, GameMetadata, MoveAnalysis
from src.gui.main_window import MainWindow
from src.gui.theme import ThemeManager


@pytest.fixture(autouse=True)
def _restore_theme_mode():
    """MainWindow applies the saved theme; later tests expect their own mode."""
    mode = ThemeManager.mode()
    yield
    ThemeManager.set_mode(mode)


def _game(game_id: str = "g1") -> GameAnalysis:
    return GameAnalysis(
        game_id=game_id,
        metadata=GameMetadata(white="Alice", black="Bob"),
        moves=[
            MoveAnalysis(
                move_number=1,
                ply=1,
                san="e4",
                uci="e2e4",
                fen_before=chess.STARTING_FEN,
            )
        ],
        pgn_content="1. e4 *",
    )


def test_main_window_batch_recovery_gating_live_lock_and_exit(qtbot, qapp, tmp_path, monkeypatch):
    window = MainWindow()
    qtbot.addWidget(window)
    manager = GameHistoryManager(str(tmp_path / "integration.db"))
    manager.save_game(_game(), "1. e4 *")
    manager.save_analysis_batch(
        AnalysisBatch(
            state=BATCH_PAUSED,
            items=[AnalysisBatchItem("g1", 1)],
        )
    )
    window.history_manager = manager
    window.history_view.history_manager = manager
    window.history_view.load_history()
    window._recover_persisted_batch()

    assert window.analysis_coordinator.batch_paused is True
    assert "Batch paused" in window.history_view.batch_queue_card.title_label.text()

    monkeypatch.setattr(window, "_resolve_paused_batch_conflict", lambda: "discard")
    monkeypatch.setattr(window, "_ensure_engine_ready", lambda: True)
    started = []
    monkeypatch.setattr(window, "_start_batch_worker", started.append)
    window.start_batch_analysis(["g1"])

    assert len(started) == 1
    assert window.analysis_coordinator.batch_running is True
    assert manager.get_analysis_batch().state == "running"
    assert "Batch analysis" in window.history_view.batch_queue_card.title_label.text()

    window.load_game(manager.get_game_analysis("g1"))
    window.analysis_coordinator.set_batch_runtime("g1", 1, 1, {"g1"})
    window._update_analyze_button(running=False)
    assert window.btn_analyze.isEnabled() is False
    assert "In batch (1/1)" in window.btn_analyze.text()

    window.worker = None
    window.start_analysis()
    assert window.worker is None

    warnings = []
    monkeypatch.setattr(
        QMessageBox, "warning", lambda *args, **kwargs: warnings.append(True)
    )
    window.on_game_action_requested(window.current_game, "analyze")
    assert warnings

    window._set_batch_engine_lock(True)
    assert window.move_list_panel._analysis_locked is True
    assert window.explorer_view._analysis_locked is True
    assert window.analysis_panel.toggle_checkbox.isEnabled() is False
    window._set_batch_engine_lock(False)
    assert window.move_list_panel._analysis_locked is False

    batch_worker = MagicMock()
    batch_worker.isRunning.return_value = True
    window._batch_worker = batch_worker
    answers = [False, True]
    monkeypatch.setattr(
        "src.gui.utils.gui_utils.confirm_dialog",
        lambda *args, **kwargs: answers.pop(0),
    )

    ignored = QCloseEvent()
    window.closeEvent(ignored)
    assert ignored.isAccepted() is False

    accepted = QCloseEvent()
    window.closeEvent(accepted)
    assert accepted.isAccepted() is True
    batch_worker.pause.assert_called_once()
    batch_worker.wait.assert_called_once()
