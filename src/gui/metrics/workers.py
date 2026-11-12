"""
Worker threads for metrics calculations and AI insights.
Thin PyQt6 bridges that delegate all computation to backend services.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PyQt6.QtCore import QThread, pyqtSignal

from src.backend.analysis.metrics_aggregator import MetricsAggregator
from src.utils.logger import logger


class InsightWorker(QThread):
    """Worker thread for generating AI insights."""

    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    done = pyqtSignal()

    def __init__(self, service: Any, stats_text: str):
        super().__init__()
        self.service = service
        self.stats_text = stats_text
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True
        self.requestInterruption()

    def run(self):
        logger.info("InsightWorker: generating coach insights...")
        try:
            insight = self.service.generate_coach_insights(self.stats_text)
            if self._cancelled or self.isInterruptionRequested():
                return
            logger.info("InsightWorker: coach insights generated successfully")
            self.finished.emit(insight)
        except Exception as e:
            logger.error("InsightWorker failed: %s", e, exc_info=True)
            if not self._cancelled:
                self.error.emit(str(e))
        finally:
            self.done.emit()


class StatsWorker(QThread):
    """Worker thread bridging MetricsAggregator to PyQt signals.

    The worker can either receive an in-memory list (tests/small callers) or a
    loader callable that queries the database inside ``run``. The loader path
    keeps SQLite I/O off the GUI thread.
    """

    finished = pyqtSignal(dict)
    done = pyqtSignal()

    def __init__(
        self,
        games: list[dict[str, Any]] | None,
        usernames: list[str],
        color_filter: str = "All Colors",
        format_filter: str = "All Formats",
        source_filter: str = "All Sources",
        date_filter: str = "All Time",
        loader: Callable[[], list[dict[str, Any]]] | None = None,
    ):
        super().__init__()
        self.games = games or []
        self.usernames = usernames
        self.color_filter = color_filter
        self.format_filter = format_filter
        self.source_filter = source_filter
        self.date_filter = date_filter
        self.loader = loader
        self._cancelled = False

    def cancel(self) -> None:
        """Ask the worker to discard its result without blocking the GUI."""
        self._cancelled = True
        self.requestInterruption()

    def _is_cancelled(self) -> bool:
        return self._cancelled or self.isInterruptionRequested()

    def run(self):
        try:
            games = self.loader() if self.loader is not None else self.games
            if self._is_cancelled():
                return
            logger.debug(
                "StatsWorker: calculating stats for %d games (filters: %s, %s, %s, %s)",
                len(games),
                self.color_filter,
                self.format_filter,
                self.source_filter,
                self.date_filter,
            )
            stats = self._calculate_stats(games)
            if stats is None or self._is_cancelled():
                return
            logger.debug(
                "StatsWorker: stats calculated successfully (%d games matched)",
                stats.get("total", 0),
            )
            self.finished.emit(stats)
        except Exception as e:
            logger.error("StatsWorker failed to calculate stats: %s", e, exc_info=True)
            if not self._is_cancelled():
                self.finished.emit({})
        finally:
            self.done.emit()

    def _get_user_color(self, game: dict[str, Any]) -> str:
        """Compatibility shim delegating to MetricsAggregator."""
        return MetricsAggregator.get_user_color(game, self.usernames)

    def _matches_filters(self, game: dict[str, Any], user_color: str) -> bool:
        """Compatibility shim delegating to MetricsAggregator."""
        return MetricsAggregator.matches_filters(
            game,
            user_color,
            color_filter=self.color_filter,
            format_filter=self.format_filter,
            source_filter=self.source_filter,
            date_filter=self.date_filter,
        )

    def _calculate_stats(
        self, games: list[dict[str, Any]] | None = None
    ) -> dict[str, Any] | None:
        """Compatibility shim delegating to MetricsAggregator."""
        return MetricsAggregator.calculate_stats(
            games=self.games if games is None else games,
            usernames=self.usernames,
            color_filter=self.color_filter,
            format_filter=self.format_filter,
            source_filter=self.source_filter,
            date_filter=self.date_filter,
            should_cancel=self._is_cancelled,
        )
