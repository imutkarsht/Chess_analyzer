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

    @property
    def player_usernames(self):
        names = (
            self.data.get("chesscom_username", ""),
            self.data.get("lichess_username", ""),
        )
        return tuple(name.strip().casefold() for name in names if name.strip())


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
    monkeypatch.setattr(
        "src.gui.analysis.summary_panel.GenerateSummaryThread", _StubSummaryThread
    )
    _StubSummaryThread.created.clear()
    widget = AnalysisPanel()
    widget.config_manager = _StubConfig(lichess_username="Bob")
    game = GameAnalysis(
        game_id="report",
        metadata=GameMetadata(white="Alice", black="Bob", result="1-0"),
    )
    widget.current_game = game
    widget.coach_tab.set_llm_service(_StubService())
    widget.coach_tab.summary_panel.set_context(game, widget._user_side())
    yield widget
    widget.deleteLater()


def test_the_summary_lives_in_the_coach_tab_below_the_move_card(panel):
    summary = panel.coach_tab.summary_panel
    layout = summary.ai_summary_layout

    assert summary.parent() is panel.coach_tab
    assert layout.indexOf(summary.btn_generate_summary) > layout.indexOf(summary.txt_ai_summary)
    assert layout.indexOf(summary.btn_generate_summary) == layout.count() - 1


def test_generating_swaps_the_summary_for_the_pulsing_placeholder(panel):
    panel.coach_tab.summary_panel.generate_ai_summary()

    summary = panel.coach_tab.summary_panel
    assert summary.ai_summary_skeleton.isHidden() is False
    assert summary.ai_summary_skeleton.is_animating() is True
    assert summary.txt_ai_summary.isHidden() is True
    assert summary.btn_generate_summary.isEnabled() is False
    assert _StubSummaryThread.created[0].user_side == "black"


def test_a_failed_generation_keeps_the_previous_report(panel, monkeypatch):
    monkeypatch.setattr(
        "src.gui.analysis.summary_panel.show_error_dialog", lambda *a: None
    )
    summary = panel.coach_tab.summary_panel
    panel.current_game.ai_summary = "Game Comment: Old\n\nSummary:\nOld report."
    summary.generate_ai_summary()

    summary.on_summary_generated("Error: upstream timeout")

    assert summary.ai_summary_skeleton.isHidden() is True
    assert summary.ai_summary_skeleton.is_animating() is False
    assert summary.txt_ai_summary.toPlainText() == "Game Comment: Old\n\nSummary:\nOld report."
    assert summary.btn_generate_summary.isEnabled() is True
    assert "Regenerate" in summary.btn_generate_summary.text()


def test_a_finished_report_is_shown_and_stored(panel):
    store = _StubStore()
    panel.history_manager = store
    summary = panel.coach_tab.summary_panel
    summary.generate_ai_summary()

    summary.on_summary_generated("Game Comment: Sharp\n\nSummary:\nA clean conversion.")

    assert summary.ai_summary_skeleton.isHidden() is True
    assert summary.txt_ai_summary.isHidden() is False
    assert "A clean conversion." in summary.txt_ai_summary.toPlainText()
    assert "Regenerate" in summary.btn_generate_summary.text()
    assert store.saved == [("report", panel.current_game.ai_summary)]
