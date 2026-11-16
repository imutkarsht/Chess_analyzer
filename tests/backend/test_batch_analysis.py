"""Deterministic tests for the pure batch runner and queue reconciliation."""

import pytest

from src.backend.analysis.batch import BatchAnalysisRunner, reconcile_batch
from src.backend.models.analysis_batch import (
    INTENT_ANALYZE,
    INTENT_RESUME,
    INTENT_SKIP,
    OUTCOME_COMPLETED,
    OUTCOME_FAILED,
    OUTCOME_NOT_STARTED,
    OUTCOME_PAUSED,
    OUTCOME_PENDING,
    OUTCOME_SKIPPED,
    AnalysisBatch,
    AnalysisBatchItem,
    GameProgress,
    GameStarted,
)
from src.backend.storage.models import GameAnalysis, GameMetadata, MoveAnalysis


def _game(game_id: str, moves: int = 1) -> GameAnalysis:
    return GameAnalysis(
        game_id=game_id,
        metadata=GameMetadata(white=f"White {game_id}", black=f"Black {game_id}"),
        moves=[
            MoveAnalysis(
                move_number=index + 1,
                ply=index + 1,
                san="e4",
                uci="e2e4",
                fen_before="start",
            )
            for index in range(moves)
        ],
    )


class FakeAnalyzer:
    """Small analyzer stand-in that saves status through a shared map."""

    def __init__(self, statuses, *, fail=None, cancel_ids=()):
        self.statuses = statuses
        self.fail = fail or {}
        self.cancel_ids = set(cancel_ids)
        self.calls: list[tuple[str, bool]] = []

    def __call__(self, game, resume, on_progress, token):
        self.calls.append((game.game_id, resume))
        error = self.fail.get(game.game_id)
        if error is not None:
            raise error
        total = len(game.moves)
        # Classification callbacks carry a third move-data dict; it must not
        # be mistaken for the game id.
        on_progress(1, total, {"index": 0, "classification": "Best"})
        on_progress(total + 1, total)
        # The analyzer replays 1..total while classifying; the runner must
        # suppress those callbacks after the final-position marker.
        on_progress(1, total)
        if game.game_id in self.cancel_ids:
            token.set()
            self.statuses[game.game_id] = "paused"
        else:
            self.statuses[game.game_id] = "completed"


class FakeEngineDown(Exception):
    pass


def _items(*game_ids: str) -> list[AnalysisBatchItem]:
    return [
        AnalysisBatchItem(game_id=game_id, position=index)
        for index, game_id in enumerate(game_ids, start=1)
    ]


def test_runner_processes_order_skips_completed_and_resumes_paused():
    statuses = {
        "done": "completed",
        "paused": "paused",
        "fresh": "not_started",
        "empty": "not_started",
    }
    games = {
        "done": _game("done"),
        "paused": _game("paused"),
        "fresh": _game("fresh"),
        "empty": _game("empty", moves=0),
    }
    analyzer = FakeAnalyzer(statuses)
    events = []
    runner = BatchAnalysisRunner(
        load_game=games.get,
        load_status=statuses.get,
        analyze_game=analyzer,
    )

    result = runner.run(_items("done", "paused", "fresh", "empty"), on_event=events.append)

    assert analyzer.calls == [("paused", True), ("fresh", False)]
    assert [(item.game_id, item.outcome) for item in result.items] == [
        ("done", OUTCOME_SKIPPED),
        ("paused", OUTCOME_COMPLETED),
        ("fresh", OUTCOME_COMPLETED),
        ("empty", OUTCOME_SKIPPED),
    ]
    assert result.reason == "completed"
    started = [event for event in events if isinstance(event, GameStarted)]
    assert [(event.game_id, event.action, event.position, event.total) for event in started] == [
        ("paused", INTENT_RESUME, 2, 4),
        ("fresh", INTENT_ANALYZE, 3, 4),
    ]
    progress = [
        (event.current, event.total_moves)
        for event in events
        if isinstance(event, GameProgress) and event.game_id == "paused"
    ]
    assert progress == [(1, 1), (2, 1)]
    assert AnalysisBatch(items=list(result.items)).summary().completed == 2


def test_runner_cancellation_saves_partial_and_leaves_remaining_pending():
    statuses = {"g1": "not_started", "g2": "not_started"}
    games = {"g1": _game("g1"), "g2": _game("g2")}
    analyzer = FakeAnalyzer(statuses, cancel_ids={"g1"})
    runner = BatchAnalysisRunner(games.get, statuses.get, analyzer)

    result = runner.run(_items("g1", "g2"))

    assert analyzer.calls == [("g1", False)]
    assert result.reason == "stopped"
    assert [(item.game_id, item.outcome) for item in result.items] == [
        ("g1", OUTCOME_PAUSED),
        ("g2", OUTCOME_PENDING),
    ]


@pytest.mark.parametrize("fatal", [False, True])
def test_runner_continues_after_failure_unless_engine_is_fatal(fatal):
    statuses = {"g1": "not_started", "g2": "not_started", "g3": "not_started"}
    games = {game_id: _game(game_id) for game_id in statuses}
    error = FakeEngineDown("engine gone") if fatal else ValueError("bad game")
    analyzer = FakeAnalyzer(statuses, fail={"g1": error})
    runner = BatchAnalysisRunner(
        games.get,
        statuses.get,
        analyzer,
        is_fatal=lambda exc: isinstance(exc, FakeEngineDown),
    )

    result = runner.run(_items("g1", "g2", "g3"))

    assert result.reason == ("fatal" if fatal else "completed")
    assert results_by_id(result.items)["g1"] == (OUTCOME_FAILED, "engine gone" if fatal else "bad game")
    if fatal:
        assert analyzer.calls == [("g1", False)]
        assert results_by_id(result.items)["g2"][0] == OUTCOME_PENDING
        assert result.fatal_error == "engine gone"
    else:
        assert analyzer.calls == [("g1", False), ("g2", False), ("g3", False)]
        assert results_by_id(result.items)["g2"][0] == OUTCOME_COMPLETED


@pytest.mark.parametrize(
    "settled_status,expected_outcome,expected_reason",
    [
        ("paused", OUTCOME_PAUSED, "stopped"),
        ("not_started", OUTCOME_FAILED, "completed"),
    ],
)
def test_runner_never_marks_completion_without_a_persisted_completed_game(
    settled_status, expected_outcome, expected_reason
):
    statuses = {"g1": "not_started"}
    games = {"g1": _game("g1")}

    def analyzer(game, _resume, on_progress, _token):
        on_progress(1, len(game.moves))
        statuses["g1"] = settled_status

    runner = BatchAnalysisRunner(games.get, statuses.get, analyzer)
    result = runner.run(_items("g1"))

    assert result.items[0].outcome == expected_outcome
    assert result.reason == expected_reason


def results_by_id(items):
    return {
        item.game_id: (item.outcome, item.error)
        for item in items
    }


def test_runner_picks_up_reordered_pending_items_between_games():
    statuses = {game_id: "not_started" for game_id in ("g1", "g2", "g3")}
    games = {game_id: _game(game_id) for game_id in statuses}
    pending = _items("g1", "g2", "g3")

    def analyze(game, _resume, on_progress, _token):
        on_progress(1, len(game.moves))
        statuses[game.game_id] = "completed"
        if game.game_id == "g1":
            # The user drags g3 above g2 while g1 is being analyzed.
            pending[:] = [
                pending[0],
                AnalysisBatchItem("g3", 2),
                AnalysisBatchItem("g2", 3),
            ]

    analyzer = analyze
    runner = BatchAnalysisRunner(games.get, statuses.get, analyzer)
    result = runner.run(pending, pending_items=lambda: list(pending))

    assert [item.game_id for item in result.items] == ["g1", "g3", "g2"]
    assert [item.outcome for item in result.items] == [
        OUTCOME_COMPLETED,
        OUTCOME_COMPLETED,
        OUTCOME_COMPLETED,
    ]


def test_summary_progress_does_not_count_unstarted_games():
    batch = AnalysisBatch(
        items=[
            AnalysisBatchItem("done", 1, outcome=OUTCOME_COMPLETED),
            AnalysisBatchItem("skipped", 2, outcome=OUTCOME_SKIPPED),
            AnalysisBatchItem("failed", 3, outcome=OUTCOME_FAILED),
            AnalysisBatchItem("never", 4, outcome=OUTCOME_NOT_STARTED),
        ]
    )
    assert batch.summary().processed == 3


def test_reconcile_uses_game_status_and_keeps_batch_completions():
    batch = AnalysisBatch(
        items=[
            AnalysisBatchItem("batch_done", 1, outcome=OUTCOME_COMPLETED),
            AnalysisBatchItem("external_done", 2),
            AnalysisBatchItem("paused", 3, outcome=OUTCOME_PENDING),
            AnalysisBatchItem("retry_done", 4, outcome=OUTCOME_FAILED, error="old"),
            AnalysisBatchItem("missing", 5),
            AnalysisBatchItem("fresh", 6, outcome=OUTCOME_NOT_STARTED),
            AnalysisBatchItem("old_skip", 7, outcome=OUTCOME_SKIPPED),
        ]
    )
    reconciled = reconcile_batch(
        batch,
        {
            "batch_done": "completed",
            "external_done": "completed",
            "paused": "paused",
            "retry_done": "completed",
            "missing": None,
            "fresh": "not_started",
            "old_skip": "completed",
        },
    )

    by_id = {item.game_id: item for item in reconciled.items}
    assert (by_id["batch_done"].outcome, by_id["batch_done"].intent) == (
        OUTCOME_COMPLETED,
        INTENT_ANALYZE,
    )
    assert (by_id["external_done"].outcome, by_id["external_done"].intent) == (
        OUTCOME_SKIPPED,
        INTENT_SKIP,
    )
    assert (by_id["paused"].outcome, by_id["paused"].intent) == (
        OUTCOME_PENDING,
        INTENT_RESUME,
    )
    assert (by_id["retry_done"].outcome, by_id["retry_done"].intent) == (
        OUTCOME_SKIPPED,
        INTENT_SKIP,
    )
    assert by_id["missing"].outcome == OUTCOME_FAILED
    assert (by_id["fresh"].outcome, by_id["fresh"].intent) == (
        OUTCOME_PENDING,
        INTENT_ANALYZE,
    )
    assert by_id["old_skip"].outcome == OUTCOME_SKIPPED
