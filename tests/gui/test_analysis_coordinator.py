"""Gating rules for the app-wide analysis coordinator."""

from src.backend.models.analysis_batch import BATCH_COMPLETED, BATCH_PAUSED
from src.gui.analysis.coordinator import AnalysisCoordinator


def test_coordinator_gates_single_batch_live_and_delete():
    coordinator = AnalysisCoordinator()
    assert coordinator.can_start_single()
    assert coordinator.can_start_batch()
    assert coordinator.can_use_live_engine()

    assert coordinator.begin_batch(["g1", "g2"], total=2)
    assert coordinator.mode == "batch"
    assert not coordinator.can_start_single()
    assert not coordinator.can_start_batch()
    assert not coordinator.can_use_live_engine()

    coordinator.set_batch_runtime("g1", 1, 2, queued_game_ids={"g1", "g2"})
    assert not coordinator.can_delete_game("g1")
    assert coordinator.can_delete_game("g2")

    coordinator.set_batch_state(BATCH_PAUSED)
    assert coordinator.mode == "idle"
    assert coordinator.can_start_single()
    assert coordinator.can_start_batch()
    assert coordinator.can_use_live_engine()
    assert coordinator.begin_single("g3")
    assert not coordinator.can_start_batch()
    coordinator.end_single()

    coordinator.end_batch(BATCH_COMPLETED)
    assert coordinator.mode == "idle"
    assert coordinator.batch_running is False
