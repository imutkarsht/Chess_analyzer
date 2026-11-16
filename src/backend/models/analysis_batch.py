# SPDX-License-Identifier: GPL-3.0-only
"""Shared models for the persisted batch-analysis queue.

Batch items store intent and outcome only. The game row remains the source of
truth for whether a game is complete, paused, or unanalyzed, so an analysis
performed outside the batch is reconciled rather than duplicated.
"""

from __future__ import annotations

from dataclasses import dataclass, field

BATCH_RUNNING = "running"
BATCH_PAUSED = "paused"
BATCH_COMPLETED = "completed"
BATCH_CANCELLED = "cancelled"
BATCH_FAILED = "failed"
BATCH_STATES = frozenset(
    {BATCH_RUNNING, BATCH_PAUSED, BATCH_COMPLETED, BATCH_CANCELLED, BATCH_FAILED}
)

INTENT_ANALYZE = "analyze"
INTENT_RESUME = "resume"
INTENT_SKIP = "skip"
ITEM_INTENTS = frozenset({INTENT_ANALYZE, INTENT_RESUME, INTENT_SKIP})

OUTCOME_PENDING = "pending"
OUTCOME_PAUSED = "paused"
OUTCOME_COMPLETED = "completed"
OUTCOME_SKIPPED = "skipped"
OUTCOME_FAILED = "failed"
OUTCOME_NOT_STARTED = "not_started"
ITEM_OUTCOMES = frozenset(
    {
        OUTCOME_PENDING,
        OUTCOME_PAUSED,
        OUTCOME_COMPLETED,
        OUTCOME_SKIPPED,
        OUTCOME_FAILED,
        OUTCOME_NOT_STARTED,
    }
)
TERMINAL_OUTCOMES = frozenset(
    {
        OUTCOME_COMPLETED,
        OUTCOME_SKIPPED,
        OUTCOME_FAILED,
        OUTCOME_NOT_STARTED,
    }
)

GAME_STATUS_NOT_STARTED = "not_started"
GAME_STATUS_UNANALYZED = "unanalyzed"
GAME_STATUS_PAUSED = "paused"
GAME_STATUS_COMPLETED = "completed"
# ``unanalyzed`` is the legacy/import spelling; both mean no analysis yet.
BATCHABLE_GAME_STATUSES: tuple[str, ...] = (
    GAME_STATUS_NOT_STARTED,
    GAME_STATUS_UNANALYZED,
    GAME_STATUS_PAUSED,
)


@dataclass(frozen=True)
class AnalysisBatchItem:
    """One selected game's place and result inside the queue."""

    game_id: str
    position: int
    intent: str = INTENT_ANALYZE
    outcome: str = OUTCOME_PENDING
    error: str | None = None

    def with_outcome(self, outcome: str, error: str | None = None) -> AnalysisBatchItem:
        return AnalysisBatchItem(
            game_id=self.game_id,
            position=self.position,
            intent=self.intent,
            outcome=outcome,
            error=error,
        )

    def with_intent(self, intent: str) -> AnalysisBatchItem:
        return AnalysisBatchItem(
            game_id=self.game_id,
            position=self.position,
            intent=intent,
            outcome=self.outcome,
            error=self.error,
        )

    @property
    def is_pending(self) -> bool:
        return self.outcome == OUTCOME_PENDING

    @property
    def is_terminal(self) -> bool:
        return self.outcome in TERMINAL_OUTCOMES


@dataclass(frozen=True)
class BatchSummary:
    """User-facing counts for the queue card and completion summary."""

    total: int = 0
    completed: int = 0
    skipped: int = 0
    failed: int = 0
    not_started: int = 0
    paused: int = 0
    pending: int = 0

    @property
    def processed(self) -> int:
        """Items the batch no longer has to run (pending excluded)."""
        return max(0, self.total - self.pending)


@dataclass
class AnalysisBatch:
    """The single persisted queue row plus its ordered items."""

    batch_id: int = 1
    state: str = BATCH_RUNNING
    created_at: float = 0.0
    updated_at: float = 0.0
    elapsed_seconds: float = 0.0
    items: list[AnalysisBatchItem] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.items)

    def summary(self) -> BatchSummary:
        counts = {
            OUTCOME_COMPLETED: 0,
            OUTCOME_SKIPPED: 0,
            OUTCOME_FAILED: 0,
            OUTCOME_NOT_STARTED: 0,
            OUTCOME_PAUSED: 0,
            OUTCOME_PENDING: 0,
        }
        for item in self.items:
            if item.outcome in counts:
                counts[item.outcome] += 1
        return BatchSummary(total=len(self.items), **counts)

    def pending_items(self) -> list[AnalysisBatchItem]:
        return [item for item in self.items if item.outcome == OUTCOME_PENDING]

    def actionable_items(self) -> list[AnalysisBatchItem]:
        """Items a resume may still run (paused partials and queued work)."""
        return [
            item
            for item in self.items
            if item.outcome in (OUTCOME_PENDING, OUTCOME_PAUSED)
        ]

    def item(self, game_id: str) -> AnalysisBatchItem | None:
        for item in self.items:
            if item.game_id == game_id:
                return item
        return None

    def with_item(self, replacement: AnalysisBatchItem) -> AnalysisBatch:
        items = [
            replacement if item.game_id == replacement.game_id else item
            for item in self.items
        ]
        return AnalysisBatch(
            batch_id=self.batch_id,
            state=self.state,
            created_at=self.created_at,
            updated_at=self.updated_at,
            elapsed_seconds=self.elapsed_seconds,
            items=items,
        )

    def replace_items(self, items: list[AnalysisBatchItem]) -> AnalysisBatch:
        return AnalysisBatch(
            batch_id=self.batch_id,
            state=self.state,
            created_at=self.created_at,
            updated_at=self.updated_at,
            elapsed_seconds=self.elapsed_seconds,
            items=list(items),
        )


@dataclass(frozen=True)
class GameStarted:
    """Runner event emitted when a game's engine work begins."""

    game_id: str
    position: int
    total: int
    action: str
    label: str
    total_moves: int


@dataclass(frozen=True)
class GameProgress:
    """Runner event for the active game's move progress."""

    game_id: str
    current: int
    total_moves: int


@dataclass(frozen=True)
class GameOutcomeEvent:
    """Runner event emitted after one item reaches its final outcome."""

    item: AnalysisBatchItem


BatchEvent = GameStarted | GameProgress | GameOutcomeEvent


@dataclass(frozen=True)
class BatchRunResult:
    """Final state of one runner pass.

    ``reason`` is ``completed`` (all items resolved), ``stopped`` (pause or
    cancel token), or ``fatal`` (engine unavailable, stop the queue).
    """

    reason: str
    items: tuple[AnalysisBatchItem, ...]
    fatal_error: str | None = None
