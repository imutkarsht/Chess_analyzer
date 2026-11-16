# SPDX-License-Identifier: GPL-3.0-only
"""Pure-Python sequential batch-analysis runner.

The GUI worker supplies the game loader, status loader, and analyzer callable;
this module owns queue order, skip/resume decisions, cancellation, failure
policy, and the final per-item outcomes. It has no Qt imports, so the whole
workflow is testable with small fakes and no Stockfish process.
"""

from __future__ import annotations

import threading
from collections.abc import Callable

from src.backend.models.analysis_batch import (
    GAME_STATUS_COMPLETED,
    GAME_STATUS_PAUSED,
    INTENT_ANALYZE,
    INTENT_RESUME,
    INTENT_SKIP,
    OUTCOME_COMPLETED,
    OUTCOME_FAILED,
    OUTCOME_PAUSED,
    OUTCOME_PENDING,
    OUTCOME_SKIPPED,
    AnalysisBatch,
    AnalysisBatchItem,
    BatchEvent,
    BatchRunResult,
    GameOutcomeEvent,
    GameProgress,
    GameStarted,
)
from src.backend.storage.models import GameAnalysis
from src.utils.logger import logger

GameLoader = Callable[[str], GameAnalysis | None]
StatusLoader = Callable[[str], str | None]
AnalyzeCallable = Callable[
    [GameAnalysis, bool, Callable[[int, int], None], threading.Event], None
]
EventObserver = Callable[[BatchEvent], None]
FatalClassifier = Callable[[BaseException], bool]


def normalize_game_status(status: str | None) -> str:
    """Normalize the stored filter column to the three decisions we need."""
    value = str(status or "").strip().lower()
    if value == GAME_STATUS_COMPLETED:
        return GAME_STATUS_COMPLETED
    if value == GAME_STATUS_PAUSED:
        return GAME_STATUS_PAUSED
    return "not_started"


def reconcile_batch(
    batch: AnalysisBatch, statuses: dict[str, str | None]
) -> AnalysisBatch:
    """Sync queue intent/outcome with the persisted game records.

    Completed games are skipped unless the batch already recorded them as
    completed. A paused game resumes from its first unanalyzed ply, and a
    still-unanalyzed game is analyzed from scratch. Failed and not-started
    items become retryable when the user explicitly resumes the queue.
    """
    reconciled: list[AnalysisBatchItem] = []
    for item in batch.items:
        if item.outcome in (OUTCOME_COMPLETED, OUTCOME_SKIPPED):
            reconciled.append(item)
            continue

        status = statuses.get(item.game_id)
        if status is None:
            reconciled.append(
                item.with_outcome(OUTCOME_FAILED, "Game no longer exists.")
            )
            continue

        normalized = normalize_game_status(status)
        if normalized == GAME_STATUS_COMPLETED:
            reconciled.append(item.with_outcome(OUTCOME_SKIPPED).with_intent(INTENT_SKIP))
        elif normalized == GAME_STATUS_PAUSED:
            reconciled.append(item.with_outcome(OUTCOME_PENDING).with_intent(INTENT_RESUME))
        else:
            reconciled.append(item.with_outcome(OUTCOME_PENDING).with_intent(INTENT_ANALYZE))
    return batch.replace_items(reconciled)


class BatchAnalysisRunner:
    """Run one batch queue sequentially through the injected analyzer."""

    def __init__(
        self,
        load_game: GameLoader,
        load_status: StatusLoader,
        analyze_game: AnalyzeCallable,
        is_fatal: FatalClassifier | None = None,
    ):
        self._load_game = load_game
        self._load_status = load_status
        self._analyze_game = analyze_game
        self._is_fatal = is_fatal or (lambda _error: False)

    def run(
        self,
        items: list[AnalysisBatchItem],
        cancel_token: threading.Event | None = None,
        on_event: EventObserver | None = None,
    ) -> BatchRunResult:
        token = cancel_token or threading.Event()
        observer = on_event or (lambda _event: None)
        results: dict[str, AnalysisBatchItem] = {
            item.game_id: item for item in items
        }
        order = [item.game_id for item in items]

        for position, item in enumerate(items, start=1):
            if item.outcome in (OUTCOME_COMPLETED, OUTCOME_SKIPPED):
                continue
            if token.is_set():
                break

            game = self._load_game(item.game_id)
            if game is None:
                failed = item.with_outcome(
                    OUTCOME_FAILED, "Game no longer exists."
                )
                results[item.game_id] = failed
                observer(GameOutcomeEvent(failed))
                continue

            status = normalize_game_status(self._load_status(item.game_id))
            if status == GAME_STATUS_COMPLETED:
                skipped = item.with_outcome(OUTCOME_SKIPPED).with_intent(INTENT_SKIP)
                results[item.game_id] = skipped
                observer(GameOutcomeEvent(skipped))
                continue
            if not game.moves:
                skipped = item.with_outcome(
                    OUTCOME_SKIPPED, "No moves to analyze."
                )
                results[item.game_id] = skipped
                observer(GameOutcomeEvent(skipped))
                continue

            resume = status == GAME_STATUS_PAUSED
            action = INTENT_RESUME if resume else INTENT_ANALYZE
            observer(
                GameStarted(
                    game_id=item.game_id,
                    position=position,
                    total=len(items),
                    action=action,
                    label=_game_label(game, position),
                    total_moves=len(game.moves),
                )
            )

            final_seen = False

            def on_progress(current: int, total: int, game_id=item.game_id) -> None:
                nonlocal final_seen
                if final_seen:
                    return
                if current > total:
                    final_seen = True
                observer(GameProgress(game_id=game_id, current=current, total_moves=total))

            try:
                self._analyze_game(game, resume, on_progress, token)
            except Exception as error:  # noqa: BLE001 - classified below
                if token.is_set():
                    outcome = self._cancelled_outcome(item, error)
                elif self._is_fatal(error):
                    failed = item.with_outcome(OUTCOME_FAILED, str(error))
                    results[item.game_id] = failed
                    observer(GameOutcomeEvent(failed))
                    logger.error(
                        "Batch analysis stopped: engine unavailable for game %s: %s",
                        item.game_id,
                        error,
                        exc_info=True,
                    )
                    return BatchRunResult(
                        reason="fatal",
                        items=self._result_items(order, results),
                        fatal_error=str(error),
                    )
                else:
                    failed = item.with_outcome(OUTCOME_FAILED, str(error))
                    results[item.game_id] = failed
                    observer(GameOutcomeEvent(failed))
                    logger.error(
                        "Batch analysis failed for game %s: %s",
                        item.game_id,
                        error,
                        exc_info=True,
                    )
                    continue
            else:
                outcome = self._post_analysis_outcome(item)

            results[item.game_id] = outcome
            observer(GameOutcomeEvent(outcome))

            if outcome.outcome == OUTCOME_PAUSED:
                logger.info("Batch analysis paused at game %s", item.game_id)
                break
            if token.is_set():
                break

        reason = "completed"
        if token.is_set() or any(
            item.outcome == OUTCOME_PAUSED for item in results.values()
        ):
            reason = "stopped"
        return BatchRunResult(
            reason=reason, items=self._result_items(order, results)
        )

    def _cancelled_outcome(
        self, item: AnalysisBatchItem, error: BaseException
    ) -> AnalysisBatchItem:
        """Trust the persisted status after a stop, keeping partial work."""
        status = normalize_game_status(self._load_status(item.game_id))
        if status == GAME_STATUS_COMPLETED:
            return item.with_outcome(OUTCOME_COMPLETED)
        return item.with_outcome(OUTCOME_PAUSED, str(error) or None)

    def _post_analysis_outcome(self, item: AnalysisBatchItem) -> AnalysisBatchItem:
        """Only report completion when the game row says it is complete."""
        status = normalize_game_status(self._load_status(item.game_id))
        if status == GAME_STATUS_COMPLETED:
            return item.with_outcome(OUTCOME_COMPLETED)
        if status == GAME_STATUS_PAUSED:
            return item.with_outcome(OUTCOME_PAUSED)
        return item.with_outcome(
            OUTCOME_FAILED, "Analysis finished without a completed save."
        )

    @staticmethod
    def _result_items(
        order: list[str], results: dict[str, AnalysisBatchItem]
    ) -> tuple[AnalysisBatchItem, ...]:
        merged = list(results.values())
        # Keep the queue's creation order even when some items were skipped.
        by_id = {item.game_id: item for item in merged}
        return tuple(by_id[game_id] for game_id in order if game_id in by_id)


def _game_label(game: GameAnalysis, position: int) -> str:
    white = str(getattr(game.metadata, "white", "") or "").strip()
    black = str(getattr(game.metadata, "black", "") or "").strip()
    if white or black:
        return f"{white or '?'} vs {black or '?'}"
    return f"Game {position}"
