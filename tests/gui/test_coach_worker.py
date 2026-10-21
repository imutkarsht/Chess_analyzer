"""
Tests for the Coach explanation worker and its request limiter (Phase 3).

The worker is exercised synchronously (``run()`` is called directly) so no
threads are spawned and the suite stays fast.
"""

from __future__ import annotations

import chess
import pytest

from src.backend.analysis.tactics.insight import build_move_insight
from src.backend.storage.cache import AnalysisCache
from src.backend.storage.models import GameMetadata, MoveAnalysis
from src.constants import EXPLANATION_PROMPT_VERSION
from src.gui.analysis.coach_worker import ExplainMoveWorker, RequestLimiter

LEGAL = ["e4", "e5", "Nf3", "Nc6", "Bc4", "d6", "Nc3", "Bg4", "Nxe5", "Bxd1"]
MODEL = "openai/gpt-oss-120b"


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def _insight():
    """The 5.Nxe5 blunder from Legal's mate, with its refutation 5...Bxd1."""
    board = chess.Board()
    for san in LEGAL[:8]:
        board.push_san(san)
    fen_before = board.fen()
    played = MoveAnalysis(
        5, 8, "Nxe5", board.parse_san("Nxe5").uci(), fen_before, classification="Blunder"
    )
    reply_board = chess.Board(fen_before)
    reply_board.push_san("Nxe5")
    reply = MoveAnalysis(
        5,
        9,
        "Bxd1",
        reply_board.parse_san("Bxd1").uci(),
        reply_board.fen(),
        classification="Blunder",
        multi_pvs=[{"pv": ["g4d1"], "cp": 0, "mate": None}],
    )
    meta = GameMetadata(white="A", black="B", white_elo="1600", black_elo="1500")
    return build_move_insight([played, reply], 0, metadata=meta)


def _worker(insight, service, cache=None, **kwargs):
    return ExplainMoveWorker(
        service,
        insight,
        seq=kwargs.pop("seq", 1),
        cache=cache,
        lang_code="en",
        model_name=MODEL,
        **kwargs,
    )


class StubService:
    def __init__(self, reply: str = "You left your knight loose, so Bxd1 wins material."):
        self.reply = reply
        self.calls: list[tuple[str, str]] = []
        self.model_name = MODEL

    def explain_move(self, facts_text: str, classification: str) -> str:
        self.calls.append((facts_text, classification))
        return self.reply


@pytest.fixture
def cache(tmp_path):
    instance = AnalysisCache(str(tmp_path / "cache.db"))
    yield instance
    instance.close()


class TestRequestLimiter:
    def test_enforces_a_minimum_gap_between_requests(self):
        clock = FakeClock()
        limiter = RequestLimiter(min_interval_s=3.0, max_per_minute=20, clock=clock)

        assert limiter.allow() is True
        assert limiter.allow() is False  # same instant
        clock.advance(2.9)
        assert limiter.allow() is False
        clock.advance(0.2)
        assert limiter.allow() is True

    def test_enforces_a_per_minute_cap_and_recovers(self):
        clock = FakeClock()
        limiter = RequestLimiter(min_interval_s=0.0, max_per_minute=3, clock=clock)

        assert [limiter.allow() for _ in range(4)] == [True, True, True, False]
        clock.advance(61)
        assert limiter.allow() is True


class TestExplainMoveWorker:
    def test_cache_hit_emits_without_calling_the_service(self, qapp, cache):
        insight = _insight()
        cache.set_explanation(
            insight.fen_before, insight.uci, MODEL, "en", EXPLANATION_PROMPT_VERSION, "Cached text."
        )
        service = StubService()
        worker = _worker(insight, service, cache)
        results, errors = [], []
        worker.finished.connect(lambda *a: results.append(a))
        worker.error.connect(lambda *a: errors.append(a))

        worker.run()

        assert results == [(1, insight.ply, "Cached text.")]
        assert errors == []
        assert service.calls == []

    def test_valid_reply_is_emitted_and_cached(self, qapp, cache):
        insight = _insight()
        service = StubService("Bxd1 wins material; Nxe5 was better.")
        worker = _worker(insight, service, cache, seq=7)
        results, errors = [], []
        worker.finished.connect(lambda *a: results.append(a))
        worker.error.connect(lambda *a: errors.append(a))

        worker.run()

        assert errors == []
        assert results == [(7, insight.ply, "Bxd1 wins material; Nxe5 was better.")]
        # the fact sheet, not the raw position, is what the model receives
        facts, classification = service.calls[0]
        assert "FACT SHEET" in facts
        assert "5.Nxe5" in facts
        assert classification == "Blunder"
        assert (
            cache.get_explanation(
                insight.fen_before, insight.uci, MODEL, "en", EXPLANATION_PROMPT_VERSION
            )
            == "Bxd1 wins material; Nxe5 was better."
        )

    def test_hallucinated_move_is_rejected_and_not_cached(self, qapp, cache):
        insight = _insight()
        service = StubService("You should have played Qh5 instead.")
        worker = _worker(insight, service, cache)
        results, errors = [], []
        worker.finished.connect(lambda *a: results.append(a))
        worker.error.connect(lambda *a: errors.append(a))

        worker.run()

        assert results == []
        assert len(errors) == 1
        assert "Qh5" in errors[0][2]
        assert (
            cache.get_explanation(
                insight.fen_before, insight.uci, MODEL, "en", EXPLANATION_PROMPT_VERSION
            )
            is None
        )

    def test_cancelled_worker_emits_nothing(self, qapp, cache):
        insight = _insight()
        service = StubService()
        worker = _worker(insight, service, cache)
        worker.cancel()
        results, errors = [], []
        worker.finished.connect(lambda *a: results.append(a))
        worker.error.connect(lambda *a: errors.append(a))

        worker.run()

        assert results == [] and errors == []
        assert service.calls == []
