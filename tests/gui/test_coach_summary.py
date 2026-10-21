"""
Coach-tab full-game summary: placement and the pulsing "AI is writing" state.

The prompt itself is covered in ``tests/backend/test_game_report.py`` and
``test_groq_service.py``; here only the panel's presentation contract matters.
"""

from __future__ import annotations

import pytest
from PyQt6.QtCore import QThread, pyqtSignal

from src.backend.storage.models import GameAnalysis, GameMetadata
from src.gui.analysis.analysis_panel import AnalysisPanel


class _StubConfig:
    def __init__(self, **data):
        self.data = dict(data)

    def get(self, key, default=None):
        return self.data.get(key, default)


class _StubService:
    client = object()
    model_name = "test/model"


class _StubSummaryThread(QThread):
    finished = pyqtSignal(str)

    created: list[_StubSummaryThread] = []

    def __init__(self, service, game, user_side=None):
        super().__init__()
        self.user_side = user_side
        _StubSummaryThread.created.append(self)

    def start(self):  # never actually runs
        pass


class _StubStore:
    """Stands in for the main window's history manager."""

    def __init__(self):
        self.saved: list[tuple[str, str]] = []

    def save_ai_summary(self, game_id: str, text: str) -> None:
        self.saved.append((game_id, text))


@pytest.fixture
def panel(qapp, monkeypatch):
    monkeypatch.setattr("src.gui.analysis.analysis_panel.GenerateSummaryThread", _StubSummaryThread)
    _StubSummaryThread.created.clear()
    widget = AnalysisPanel()
    widget.config_manager = _StubConfig(lichess_username="Bob")
    widget.groq_service = _StubService()
    widget.current_game = GameAnalysis(
        game_id="report",
        metadata=GameMetadata(white="Alice", black="Bob", result="1-0"),
    )
    yield widget
    widget.deleteLater()


def test_the_summary_lives_in_the_coach_tab_below_the_move_card(panel):
    layout = panel.ai_summary_layout

    assert panel.ai_summary_frame.parent() is panel.coach_tab
    assert layout.indexOf(panel.btn_generate_summary) > layout.indexOf(panel.txt_ai_summary)
    assert layout.indexOf(panel.btn_generate_summary) == layout.count() - 1


def test_generating_swaps_the_summary_for_the_pulsing_placeholder(panel):
    panel.generate_ai_summary()

    assert panel.ai_summary_skeleton.isHidden() is False
    assert panel.ai_summary_skeleton.is_animating() is True
    assert panel.txt_ai_summary.isHidden() is True
    assert panel.btn_generate_summary.isEnabled() is False
    assert _StubSummaryThread.created[0].user_side == "black"


def test_a_failed_generation_keeps_the_previous_report(panel, monkeypatch):
    monkeypatch.setattr("src.gui.analysis.analysis_panel.show_error_dialog", lambda *a: None)
    panel.current_game.ai_summary = "Game Comment: Old\n\nSummary:\nOld report."
    panel.generate_ai_summary()

    panel.on_summary_generated("Error: upstream timeout")

    assert panel.ai_summary_skeleton.isHidden() is True
    assert panel.ai_summary_skeleton.is_animating() is False
    assert panel.txt_ai_summary.toPlainText() == "Game Comment: Old\n\nSummary:\nOld report."
    assert panel.btn_generate_summary.isEnabled() is True
    assert "Regenerate" in panel.btn_generate_summary.text()


def test_a_finished_report_is_shown_and_stored(panel):
    store = _StubStore()
    panel.history_manager = store
    panel.generate_ai_summary()

    panel.on_summary_generated("Game Comment: Sharp\n\nSummary:\nA clean conversion.")

    assert panel.ai_summary_skeleton.isHidden() is True
    assert panel.txt_ai_summary.isHidden() is False
    assert "A clean conversion." in panel.txt_ai_summary.toPlainText()
    assert "Regenerate" in panel.btn_generate_summary.text()
    assert store.saved == [("report", panel.current_game.ai_summary)]
