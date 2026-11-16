"""Qt adapter tests for batch worker signals and persisted queue state."""

import threading

import pytest

from src.backend.models.analysis_batch import (
    BATCH_CANCELLED,
    BATCH_COMPLETED,
    BATCH_PAUSED,
    OUTCOME_COMPLETED,
    OUTCOME_NOT_STARTED,
    OUTCOME_PAUSED,
    OUTCOME_PENDING,
    OUTCOME_SKIPPED,
    AnalysisBatch,
    AnalysisBatchItem,
)
from src.backend.storage.game_history import GameHistoryManager
from src.backend.storage.models import GameAnalysis, GameMetadata, MoveAnalysis
from src.gui.analysis.batch_analysis_worker import BatchAnalysisWorker


def _game(game_id: str, status: str) -> GameAnalysis:
    move = MoveAnalysis(
        move_number=1,
        ply=1,
        san="e4",
        uci="e2e4",
        fen_before="start",
        classification="Best" if status == "completed" else "",
    )
    summary = {"analysis_status": status} if status != "not_started" else {}
    return GameAnalysis(
        game_id=game_id,
        metadata=GameMetadata(white="White", black="Black"),
        moves=[move],
        summary=summary,
        pgn_content="1. e4 *",
    )


def _save_games(manager: GameHistoryManager, statuses: dict[str, str]) -> None:
    for game_id, status in statuses.items():
        game = _game(game_id, status)
        manager.save_game(game, game.pgn_content, force_overwrite=True)


class SavingAnalyzer:
    def __init__(self, manager):
        self.manager = manager
        self.calls = []

    def analyze_game(self, game, callback=None, cancel_token=None, resume=True):
        self.calls.append((game.game_id, resume))
        callback(1, len(game.moves))
        callback(len(game.moves) + 1, len(game.moves))
        game.summary = {
            "analysis_status": "completed",
            "analyzed_moves": len(game.moves),
            "total_moves": len(game.moves),
        }
        self.manager.save_game(game, game.pgn_content, force_overwrite=True)


class BlockingAnalyzer:
    def __init__(self, manager):
        self.manager = manager
        self.started = threading.Event()
        self.cancel_seen = threading.Event()
        self.calls = []

    def analyze_game(self, game, callback=None, cancel_token=None, resume=True):
        self.calls.append((game.game_id, resume))
        callback(1, len(game.moves))
        game.summary = {
            "analysis_status": "paused",
            "analyzed_moves": 0,
            "total_moves": len(game.moves),
        }
        self.manager.save_game(game, game.pgn_content, force_overwrite=True)
        self.started.set()
        self.cancel_seen.wait(5)

    def cancel(self):
        self.cancel_seen.set()


def _batch(manager, *game_ids):
    batch = AnalysisBatch(
        items=[
            AnalysisBatchItem(game_id=game_id, position=index)
            for index, game_id in enumerate(game_ids, start=1)
        ]
    )
    manager.save_analysis_batch(batch)
    return batch


def test_worker_runs_sequentially_and_skips_completed_games(tmp_path):
    manager = GameHistoryManager(str(tmp_path / "batch-worker.db"))
    _save_games(
        manager,
        {"fresh": "not_started", "done": "completed", "second": "not_started"},
    )
    analyzer = SavingAnalyzer(manager)
    worker = BatchAnalysisWorker(analyzer, _batch(manager, "fresh", "done", "second"), manager)
    outcomes = []
    started = []
    summaries = []
    worker.game_started.connect(lambda *args: started.append(args[:2]))
    worker.game_outcome.connect(lambda *args: outcomes.append(args[:2]))
    worker.batch_finished.connect(summaries.append)

    worker.run()

    assert analyzer.calls == [("fresh", False), ("second", False)]
    assert started == [("fresh", 1), ("second", 3)]
    assert outcomes == [
        ("fresh", OUTCOME_COMPLETED),
        ("done", OUTCOME_SKIPPED),
        ("second", OUTCOME_COMPLETED),
    ]
    assert summaries[0].completed == 2
    assert manager.get_analysis_batch().state == BATCH_COMPLETED
    assert [item.outcome for item in manager.get_analysis_batch().items] == [
        OUTCOME_COMPLETED,
        OUTCOME_SKIPPED,
        OUTCOME_COMPLETED,
    ]


@pytest.mark.parametrize(
    "action,terminal,expected_state,remaining_outcome,expected_paused,expected_remaining",
    [
        ("pause", "batch_paused", BATCH_PAUSED, OUTCOME_PENDING, 1, 0),
        ("cancel", "batch_cancelled", BATCH_CANCELLED, OUTCOME_NOT_STARTED, 1, 1),
    ],
)
def test_worker_pause_and_cancel_persist_partial_results(
    qtbot,
    qapp,
    tmp_path,
    action,
    terminal,
    expected_state,
    remaining_outcome,
    expected_paused,
    expected_remaining,
):
    manager = GameHistoryManager(str(tmp_path / f"batch-{action}.db"))
    _save_games(manager, {"g1": "not_started", "g2": "not_started"})
    analyzer = BlockingAnalyzer(manager)
    worker = BatchAnalysisWorker(analyzer, _batch(manager, "g1", "g2"), manager)

    with qtbot.waitSignal(worker.game_started, timeout=3000):
        worker.start()

    with qtbot.waitSignal(getattr(worker, terminal), timeout=3000) as blocker:
        getattr(worker, action)()
    worker.wait(3000)

    summary = blocker.args[0]
    assert summary.paused == expected_paused
    assert summary.not_started == expected_remaining
    stored = manager.get_analysis_batch()
    assert stored.state == expected_state
    assert stored.items[0].outcome == OUTCOME_PAUSED
    assert stored.items[1].outcome == remaining_outcome
