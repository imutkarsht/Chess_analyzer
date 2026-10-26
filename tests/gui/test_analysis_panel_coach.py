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
from src.gui.analysis.line_utils import lines_for_move

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
    reply.multi_pvs = [{"pv": ["g4d1"], "pv_san": "Bxd1", "cp": None, "mate": 1}]

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
        ("replay", "expected_move", "fen_from"),
        [
            # 5.Nxe5 is punished by 5...Bxd1: the opponent's line lives one ply later
            ("replay_refutation", 9, 8),
            # the alternatives belong to the played move's own position
            ("replay_best", 8, None),
        ],
    )
    def test_replay_shows_the_right_line(self, panel, replay, expected_move, fen_from):
        panel.set_selected_move(8)
        panel.tabs.set_current_index(2)

        getattr(panel, replay)()

        move = panel.current_game.moves[expected_move]
        shown = panel.lines_widget.lines
        assert len(shown) == len(move.multi_pvs)
        assert shown[0].first_move == move.multi_pvs[0]["pv"][0]

        if fen_from is None:
            assert panel._lines_fen == move.fen_before
        else:
            played = panel.current_game.moves[fen_from]
            board = chess.Board(played.fen_before)
            board.push_uci(played.uci)
            assert panel._lines_fen == board.fen()

    def test_replay_refutation_brings_the_evaluation_tab_forward(self, panel):
        """The lines widget lives in the Evaluation tab, so it must be shown."""
        panel.set_selected_move(8)
        panel.tabs.set_current_index(2)

        panel.replay_refutation()

        assert panel.tabs.current_index() == 0

    def test_replay_requests_the_matching_board_position(self, panel):
        panel.set_selected_move(8)
        requests = []
        panel.variation_requested.connect(lambda f, u: requests.append((f, u)))

        panel.replay_best()
        assert requests == [(panel.current_game.moves[8].fen_before, "d2d4")]

        requests.clear()
        panel.replay_refutation()
        after_blunder = chess.Board(panel.current_game.moves[8].fen_before)
        after_blunder.push_uci(panel.current_game.moves[8].uci)
        assert requests == [(after_blunder.fen(), "g4d1")]

    def test_line_click_opens_the_position_the_lines_belong_to(self, panel):
        move = panel.current_game.moves[8]
        requests = []
        panel.variation_requested.connect(lambda f, u: requests.append((f, u)))

        lines, lines_fen = lines_for_move(move)
        panel.update_lines(lines, fen=lines_fen)
        # Cached analysis stores the PV as "pv"; the row must still be clickable.
        assert panel.lines_widget.lines[0].first_move == "d2d4"

        panel._on_line_clicked("d2d4")
        assert requests == [(move.fen_before, "d2d4")]

        # Clearing the lines must also clear the FEN, or clicks would branch
        # from a position that is no longer displayed.
        panel.update_lines([], fen=None)
        panel._on_line_clicked("d2d4")
        assert requests == [(move.fen_before, "d2d4")]
