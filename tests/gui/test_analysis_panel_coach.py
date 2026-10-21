"""
Tests for the Coach tab wiring inside ``AnalysisPanel`` (Phase 4/5).

These exercise the panel's own responsibilities — building the deterministic
facts on selection, the debounce/limiter before dispatch, and the line replay.
The card's own state machine lives in ``test_coach_card.py`` and the network
path in ``test_coach_worker.py``.
"""

from __future__ import annotations

import chess
import pytest
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import QDialog

from src.backend.storage.cache import AnalysisCache
from src.backend.storage.models import GameAnalysis, GameMetadata, MoveAnalysis
from src.gui.analysis.analysis_panel import AnalysisPanel
from src.gui.analysis.coach_card_widget import CoachState

LEGAL_PATH = ["e4", "e5", "Nf3", "Nc6", "Bc4", "d6", "Nc3", "Bg4", "Nxe5", "Bxd1"]


class _StubConfig:
    def __init__(self, **data):
        self.data = dict(data)

    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value):
        self.data[key] = value

    def save_config(self):
        pass


class _StubService:
    """A configured look-alike; the actual request is never made in these tests."""

    client = object()
    model_name = "test/model"

    @staticmethod
    def _lang_code():
        return "en"


class _StubWorker(QThread):
    finished = pyqtSignal(int, int, str)
    error = pyqtSignal(int, int, str)

    created: list[_StubWorker] = []

    def __init__(self, service, insight, **kwargs):
        super().__init__()
        self.insight = insight
        self.kwargs = kwargs
        _StubWorker.created.append(self)

    def start(self):  # never actually runs
        pass

    def isRunning(self):
        return False

    def cancel(self):
        pass


def _game() -> GameAnalysis:
    """Legal's mate with analysis on both the blunder and its refutation."""
    board = chess.Board()
    moves: list[MoveAnalysis] = []
    for ply, san in enumerate(LEGAL_PATH, start=0):
        uci = board.parse_san(san).uci()
        fen_before = board.fen()
        board.push_san(san)
        moves.append(MoveAnalysis(ply // 2 + 1, ply, san, uci, fen_before))

    blunder, reply = moves[8], moves[9]  # 5.Nxe5 and 5...Bxd1
    blunder.classification = "Blunder"
    blunder.best_move = chess.Board(blunder.fen_before).parse_san("d4").uci()
    blunder.multi_pvs = [{"pv": ["d2d4"], "pv_san": "d4", "cp": 30, "mate": None}]
    reply.classification = "Blunder"
    reply.multi_pvs = [{"pv": ["g4d1"], "pv_san": "Bxd1", "cp": None, "mate": 0}]

    meta = GameMetadata(white="A", black="B", white_elo="1600", black_elo="1500")
    return GameAnalysis(game_id="coach", metadata=meta, moves=moves)


@pytest.fixture
def panel(qapp, tmp_path):
    widget = AnalysisPanel()
    widget.config_manager = _StubConfig()
    widget.groq_service = _StubService()
    widget._explanation_cache = AnalysisCache(str(tmp_path / "coach.db"))
    widget.current_game = _game()
    _StubWorker.created.clear()
    yield widget
    widget._cancel_explanation_worker()
    widget.deleteLater()


class TestSelection:
    def test_a_selection_renders_the_offline_summary_without_any_request(self, panel):
        panel.set_selected_move(8)  # 5.Nxe5

        assert panel.coach_card.state == CoachState.OFFLINE
        assert panel.coach_card.san_label.text() == "5.Nxe5"
        assert panel.coach_card.body_text()
        assert panel._coach_insight.ply == 8
        assert _StubWorker.created == []  # nothing leaves the machine unasked


class TestAskGate:
    def test_the_ask_button_only_arms_the_debounce(self, panel):
        panel.set_selected_move(8)

        panel.coach_card.btn_ask.click()

        assert panel._coach_debounce.isActive() is True
        assert panel._coach_debounce.isSingleShot() is True
        assert _StubWorker.created == []  # debounce holds the request back

    def test_unconfigured_provider_shows_the_settings_prompt(self, panel, monkeypatch):
        monkeypatch.setattr(
            "src.gui.dialogs.llm_error_dialog.LlmNotConfiguredDialog.exec",
            lambda self: QDialog.DialogCode.Rejected,
        )
        panel.groq_service = _StubService()
        panel.groq_service.client = None
        panel.set_selected_move(8)

        panel.coach_card.btn_ask.click()

        assert panel._coach_debounce.isActive() is False
        assert _StubWorker.created == []

    def test_dispatch_uses_the_current_seq_and_shows_loading(self, panel, monkeypatch):
        monkeypatch.setattr("src.gui.analysis.analysis_panel.ExplainMoveWorker", _StubWorker)
        panel.set_selected_move(8)

        panel._dispatch_explanation()

        assert len(_StubWorker.created) == 1
        worker = _StubWorker.created[0]
        assert worker.kwargs["seq"] == 1
        assert worker.kwargs["lang_code"] == "en"
        assert worker.kwargs["model_name"] == "test/model"
        assert worker.kwargs["cache"] is panel._explanation_cache
        assert panel.coach_card.state == CoachState.LOADING

    def test_rate_limiter_trips_before_a_worker_is_created(self, panel, monkeypatch):
        monkeypatch.setattr("src.gui.analysis.analysis_panel.ExplainMoveWorker", _StubWorker)
        toasts = []
        monkeypatch.setattr(panel, "_toast", toasts.append)
        panel.set_selected_move(8)

        panel._coach_limiter.allow()  # consume the only slot in the window
        panel._coach_limiter._min_interval_s = 999.0
        panel._dispatch_explanation()

        assert _StubWorker.created == []
        assert len(toasts) == 1 and "cooling off" in toasts[0]


class TestReplay:
    @pytest.mark.parametrize(
        ("replay", "expected_move", "turn"),
        [
            # 5.Nxe5 is punished by 5...Bxd1: the opponent's line lives one ply later
            ("replay_refutation", 9, chess.BLACK),
            # the alternatives belong to the played move's own position
            ("replay_best", 8, chess.WHITE),
        ],
    )
    def test_replay_shows_the_right_line_and_turn(self, panel, replay, expected_move, turn):
        panel.set_selected_move(8)
        panel.tabs.setCurrentIndex(2)

        getattr(panel, replay)()

        assert (
            panel.lines_widget._last_multi_pvs == panel.current_game.moves[expected_move].multi_pvs
        )
        assert panel.lines_widget._last_turn_color == turn

    def test_replay_refutation_brings_the_evaluation_tab_forward(self, panel):
        """The lines widget lives in the Evaluation tab, so it must be shown."""
        panel.set_selected_move(8)
        panel.tabs.setCurrentIndex(2)

        panel.replay_refutation()

        assert panel.tabs.currentIndex() == 0
