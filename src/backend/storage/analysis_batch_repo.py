# SPDX-License-Identifier: GPL-3.0-only
"""Persistence for the single batch-analysis queue.

The repository stores only queue intent and outcome. Game analysis state is
always read back from the ``games`` table, which keeps a paused batch in sync
with games analyzed individually.
"""

from __future__ import annotations

import sqlite3
import time

from src.backend.models.analysis_batch import (
    BATCH_PAUSED,
    BATCH_RUNNING,
    AnalysisBatch,
    AnalysisBatchItem,
)
from src.backend.storage.db_connection import get_db_connection


class AnalysisBatchRepo:
    """Create, load, and update the one persisted analysis queue."""

    def __init__(self, db_path: str):
        self.db_path = db_path

    def _get_connection(self):
        return get_db_connection(self.db_path)

    def save(self, batch: AnalysisBatch) -> AnalysisBatch:
        """Replace the queue with ``batch`` (a new batch starts fresh)."""
        now = time.time()
        created_at = batch.created_at or now
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM analysis_batch_items")
            cursor.execute("DELETE FROM analysis_batches")
            cursor.execute(
                "INSERT INTO analysis_batches "
                "(id, state, created_at, updated_at, elapsed_seconds) "
                "VALUES (1, ?, ?, ?, ?)",
                (batch.state, created_at, now, max(0.0, batch.elapsed_seconds)),
            )
            cursor.executemany(
                "INSERT INTO analysis_batch_items "
                "(batch_id, position, game_id, intent, outcome, error) "
                "VALUES (1, ?, ?, ?, ?, ?)",
                [
                    (
                        item.position,
                        item.game_id,
                        item.intent,
                        item.outcome,
                        item.error,
                    )
                    for item in batch.items
                ],
            )
            conn.commit()
        return AnalysisBatch(
            batch_id=1,
            state=batch.state,
            created_at=created_at,
            updated_at=now,
            elapsed_seconds=max(0.0, batch.elapsed_seconds),
            items=list(batch.items),
        )

    def load(self) -> AnalysisBatch | None:
        """Return the persisted queue, or ``None`` when there is no batch."""
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, state, created_at, updated_at, elapsed_seconds "
                "FROM analysis_batches WHERE id = 1"
            )
            row = cursor.fetchone()
            if row is None:
                return None
            cursor.execute(
                "SELECT game_id, position, intent, outcome, error "
                "FROM analysis_batch_items WHERE batch_id = 1 "
                "ORDER BY position ASC"
            )
            items = [
                AnalysisBatchItem(
                    game_id=item["game_id"],
                    position=int(item["position"]),
                    intent=item["intent"],
                    outcome=item["outcome"],
                    error=item["error"],
                )
                for item in cursor.fetchall()
            ]
        return AnalysisBatch(
            batch_id=int(row["id"]),
            state=row["state"],
            created_at=float(row["created_at"] or 0.0),
            updated_at=float(row["updated_at"] or 0.0),
            elapsed_seconds=float(row["elapsed_seconds"] or 0.0),
            items=items,
        )

    def set_state(self, state: str) -> None:
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE analysis_batches SET state = ?, updated_at = ? WHERE id = 1",
                (state, time.time()),
            )
            conn.commit()

    def set_elapsed_seconds(self, seconds: float) -> None:
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE analysis_batches SET elapsed_seconds = ? WHERE id = 1",
                (max(0.0, float(seconds)),),
            )
            conn.commit()

    def save_items(self, items: list[AnalysisBatchItem]) -> None:
        """Replace item outcomes/order after a reconciliation pass."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM analysis_batch_items")
            cursor.executemany(
                "INSERT INTO analysis_batch_items "
                "(batch_id, position, game_id, intent, outcome, error) "
                "VALUES (1, ?, ?, ?, ?, ?)",
                [
                    (
                        item.position,
                        item.game_id,
                        item.intent,
                        item.outcome,
                        item.error,
                    )
                    for item in items
                ],
            )
            cursor.execute(
                "UPDATE analysis_batches SET updated_at = ? WHERE id = 1",
                (time.time(),),
            )
            conn.commit()

    def update_items(self, items: list[AnalysisBatchItem]) -> None:
        """Update outcomes only; never reinsert a row removed by the user."""
        if not items:
            return
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany(
                "UPDATE analysis_batch_items SET outcome = ?, error = ? "
                "WHERE batch_id = 1 AND game_id = ?",
                [
                    (item.outcome, item.error, item.game_id)
                    for item in items
                ],
            )
            cursor.execute(
                "UPDATE analysis_batches SET updated_at = ? WHERE id = 1",
                (time.time(),),
            )
            conn.commit()

    def set_item_outcome(
        self, game_id: str, outcome: str, error: str | None = None
    ) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE analysis_batch_items SET outcome = ?, error = ? "
                "WHERE batch_id = 1 AND game_id = ?",
                (outcome, error, game_id),
            )
            cursor.execute(
                "UPDATE analysis_batches SET updated_at = ? WHERE id = 1",
                (time.time(),),
            )
            conn.commit()

    def reorder_pending(
        self, game_ids: list[str], active_game_id: str | None = None
    ) -> bool:
        """Assign the queue's pending positions to ``game_ids`` order.

        The active game and terminal items keep their positions; only the
        "Up next" pending rows move. Returns False when the supplied set no
        longer matches the persisted queue (for example, after a delete).
        """
        ordered = [game_id for game_id in game_ids if game_id]
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT game_id, position FROM analysis_batch_items "
                "WHERE outcome = 'pending' ORDER BY position"
            )
            rows = cursor.fetchall()
            movable = [
                (game_id, position)
                for game_id, position in rows
                if game_id != active_game_id
            ]
            slots = [position for _game_id, position in movable]
            if len(ordered) != len(slots) or set(ordered) != {
                game_id for game_id, _position in movable
            }:
                return False
            for game_id, position in zip(ordered, slots, strict=True):
                cursor.execute(
                    "UPDATE analysis_batch_items SET position = ? "
                    "WHERE batch_id = 1 AND game_id = ?",
                    (position, game_id),
                )
            cursor.execute(
                "UPDATE analysis_batches SET updated_at = ? WHERE id = 1",
                (time.time(),),
            )
            conn.commit()
        return True

    def remove_item(self, game_id: str) -> None:
        with self._get_connection() as conn:
            conn.execute(
                "DELETE FROM analysis_batch_items WHERE game_id = ?", (game_id,)
            )
            conn.commit()

    def delete(self) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM analysis_batch_items")
            cursor.execute("DELETE FROM analysis_batches")
            conn.commit()

    def pause_if_running(self) -> bool:
        """Recover a batch left ``running`` by a crash or forced exit."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE analysis_batches SET state = ?, updated_at = ? "
                "WHERE id = 1 AND state = ?",
                (BATCH_PAUSED, time.time(), BATCH_RUNNING),
            )
            changed = cursor.rowcount > 0
            conn.commit()
        return changed
