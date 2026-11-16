"""Persistence tests for the single persisted batch-analysis queue."""

from src.backend.models.analysis_batch import (
    BATCH_PAUSED,
    BATCH_RUNNING,
    INTENT_RESUME,
    OUTCOME_COMPLETED,
    OUTCOME_PENDING,
    AnalysisBatch,
    AnalysisBatchItem,
)
from src.backend.storage.game_history import GameHistoryManager


def _game_row(game_id: str) -> dict:
    return {
        "id": game_id,
        "white": "Alice",
        "black": "Bob",
        "result": "1-0",
        "date": "2026.01.01",
        "event": "Rapid",
        "pgn": "1. e4 e5 2. Nf3 Nc6 1-0",
        "timestamp": 1_700_000_000,
    }


def _batch(*game_ids: str) -> AnalysisBatch:
    return AnalysisBatch(
        items=[
            AnalysisBatchItem(game_id=game_id, position=index)
            for index, game_id in enumerate(game_ids, start=1)
        ]
    )


def test_batch_round_trip_replaces_queue_and_persists_outcomes(tmp_path):
    manager = GameHistoryManager(str(tmp_path / "batch.db"))
    first = manager.save_analysis_batch(_batch("g1", "g2"))
    assert first.batch_id == 1

    manager.set_analysis_batch_state(BATCH_PAUSED)
    manager.set_analysis_batch_item_outcome("g1", OUTCOME_COMPLETED)
    manager.set_analysis_batch_elapsed(42.5)
    loaded = manager.get_analysis_batch()
    assert loaded.state == BATCH_PAUSED
    assert loaded.elapsed_seconds == 42.5
    assert [(item.game_id, item.outcome) for item in loaded.items] == [
        ("g1", OUTCOME_COMPLETED),
        ("g2", OUTCOME_PENDING),
    ]

    # A new batch replaces the previous queue instead of creating a second one.
    manager.save_analysis_batch(
        AnalysisBatch(
            items=[
                AnalysisBatchItem(
                    game_id="g3",
                    position=1,
                    intent=INTENT_RESUME,
                )
            ]
        )
    )
    replaced = manager.get_analysis_batch()
    assert [item.game_id for item in replaced.items] == ["g3"]

    # Crash recovery only demotes a batch that was actually running.
    assert manager.pause_interrupted_analysis_batch() is True
    assert manager.get_analysis_batch().state == BATCH_PAUSED
    assert manager.pause_interrupted_analysis_batch() is False


def test_reorder_pending_keeps_active_and_terminal_positions(tmp_path):
    manager = GameHistoryManager(str(tmp_path / "batch-order.db"))
    manager.save_analysis_batch(
        AnalysisBatch(
            items=[
                AnalysisBatchItem("active", 1),
                AnalysisBatchItem("next_a", 2),
                AnalysisBatchItem("done", 3, outcome=OUTCOME_COMPLETED),
                AnalysisBatchItem("next_b", 4),
            ]
        )
    )

    assert manager.reorder_analysis_batch_items(
        ["next_b", "next_a"], active_game_id="active"
    )
    positions = {
        item.game_id: item.position for item in manager.get_analysis_batch().items
    }
    assert positions == {
        "active": 1,
        "next_b": 2,
        "done": 3,
        "next_a": 4,
    }
    assert manager.reorder_analysis_batch_items(
        ["next_a"], active_game_id="active"
    ) is False


def test_delete_and_clear_prune_the_queue(tmp_path):
    manager = GameHistoryManager(str(tmp_path / "batch-delete.db"))
    manager.save_games_bulk([_game_row("g1"), _game_row("g2")])
    manager.save_analysis_batch(
        AnalysisBatch(
            state=BATCH_RUNNING,
            items=[
                AnalysisBatchItem(game_id="g1", position=1),
                AnalysisBatchItem(game_id="g2", position=2),
            ],
        )
    )

    manager.delete_game("g1")
    remaining = manager.get_analysis_batch()
    assert [item.game_id for item in remaining.items] == ["g2"]

    manager.clear_history()
    assert manager.get_analysis_batch() is None
    assert manager.game_exists("g2") is False
