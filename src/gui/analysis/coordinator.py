# SPDX-License-Identifier: GPL-3.0-only
"""App-wide analysis ownership.

Only one engine analysis may run at a time. This small state holder is the
single authority for single-game analysis, batch analysis, live-engine use,
and active-game deletion. MainWindow pushes derived lock state into the views
so they remain presentation-only.
"""

from __future__ import annotations

from src.backend.models.analysis_batch import (
    BATCH_COMPLETED,
    BATCH_FAILED,
    BATCH_PAUSED,
    BATCH_RUNNING,
)

MODE_IDLE = "idle"
MODE_SINGLE = "single"
MODE_BATCH = "batch"


class AnalysisCoordinator:
    def __init__(self):
        self._mode = MODE_IDLE
        self._single_game_id: str | None = None
        self._batch_state: str | None = None
        self._active_game_id: str | None = None
        self._active_position = 0
        self._batch_total = 0
        self._queued_game_ids: set[str] = set()

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def batch_state(self) -> str | None:
        return self._batch_state

    @property
    def single_game_id(self) -> str | None:
        return self._single_game_id

    @property
    def active_game_id(self) -> str | None:
        return self._active_game_id

    @property
    def active_position(self) -> int:
        return self._active_position

    @property
    def batch_total(self) -> int:
        return self._batch_total

    @property
    def queued_game_ids(self) -> frozenset[str]:
        return frozenset(self._queued_game_ids)

    @property
    def batch_running(self) -> bool:
        return self._batch_state == BATCH_RUNNING

    @property
    def batch_paused(self) -> bool:
        return self._batch_state == BATCH_PAUSED

    def can_start_single(self) -> bool:
        return self._mode != MODE_SINGLE and not self.batch_running

    def can_start_batch(self) -> bool:
        return self._mode == MODE_IDLE and not self.batch_running

    def can_use_live_engine(self) -> bool:
        return not self.batch_running

    def can_delete_game(self, game_id: str) -> bool:
        return not (self.batch_running and game_id == self._active_game_id)

    def begin_single(self, game_id: str | None = None) -> bool:
        if not self.can_start_single():
            return False
        self._mode = MODE_SINGLE
        self._single_game_id = game_id
        return True

    def end_single(self) -> None:
        self._mode = MODE_IDLE
        self._single_game_id = None

    def begin_batch(self, game_ids: list[str], total: int | None = None) -> bool:
        if not self.can_start_batch():
            return False
        self._mode = MODE_BATCH
        self._batch_state = BATCH_RUNNING
        self._active_game_id = None
        self._active_position = 0
        self._batch_total = int(total) if total is not None else len(game_ids)
        self._queued_game_ids = set(game_ids)
        return True

    def restore_batch(
        self,
        state: str,
        total: int = 0,
        queued_game_ids: set[str] | None = None,
    ) -> None:
        """Restore a persisted queue without claiming the engine."""
        self._mode = MODE_IDLE
        self._batch_state = state
        self._active_game_id = None
        self._active_position = 0
        self._batch_total = int(total)
        self._queued_game_ids = set(queued_game_ids or ())

    def set_batch_runtime(
        self,
        active_game_id: str | None,
        position: int,
        total: int,
        queued_game_ids: set[str] | None = None,
    ) -> None:
        self._active_game_id = active_game_id
        self._active_position = position
        self._batch_total = total
        if active_game_id is not None and self._batch_state is None:
            self._batch_state = BATCH_RUNNING
        if queued_game_ids is not None:
            self._queued_game_ids = set(queued_game_ids)

    def set_batch_state(self, state: str) -> None:
        self._batch_state = state
        if state in (BATCH_PAUSED, BATCH_COMPLETED, BATCH_FAILED):
            self._mode = MODE_IDLE
            self._active_game_id = None
            self._active_position = 0
            if state != BATCH_PAUSED:
                self._queued_game_ids.clear()

    def end_batch(self, state: str) -> None:
        self.set_batch_state(state)
        self._mode = MODE_IDLE
        self._active_game_id = None
        self._active_position = 0

    def reset(self) -> None:
        self._mode = MODE_IDLE
        self._single_game_id = None
        self._batch_state = None
        self._active_game_id = None
        self._active_position = 0
        self._batch_total = 0
        self._queued_game_ids.clear()
