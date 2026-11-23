"""The one-second ETA tick must never touch the database."""

from types import SimpleNamespace

from src.backend.models.analysis_batch import (
    OUTCOME_COMPLETED,
    OUTCOME_PENDING,
    AnalysisBatch,
    AnalysisBatchItem,
    BatchSummary,
)
from src.gui.app.batch_controller import BatchController


class _TimingController(BatchController):
    def __init__(self):
        super().__init__()
        self._batch_summary = BatchSummary(total=3, completed=1, pending=2)
        self._batch_snapshot = AnalysisBatch(
            items=[
                AnalysisBatchItem("done", 1, outcome=OUTCOME_COMPLETED),
                AnalysisBatchItem("next", 2, outcome=OUTCOME_PENDING),
                AnalysisBatchItem("later", 3, outcome=OUTCOME_PENDING),
            ]
        )
        self.host = SimpleNamespace(
            analysis_coordinator=SimpleNamespace(
                batch_running=True, active_position=2
            ),
            history_view=SimpleNamespace(set_batch_timing=self._capture),
        )
        self.ticks = []

    def _capture(self, elapsed, eta):
        self.ticks.append((elapsed, eta))

    def _batch_total_elapsed(self):
        return 10.0

    def _current_game_eta(self):
        return 5.0

    def _current_batch(self):
        raise AssertionError("timer must not query the batch queue")


def test_eta_tick_uses_cached_snapshot_without_database(qapp):
    controller = _TimingController()

    controller._tick_batch_timing()

    assert len(controller.ticks) == 1
    elapsed, eta = controller.ticks[0]
    assert elapsed == 10.0
    assert eta is not None and eta >= 5.0
