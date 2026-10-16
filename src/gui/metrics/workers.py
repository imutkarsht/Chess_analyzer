"""
Worker threads for metrics calculations and AI insights.
Thin PyQt6 bridges that delegate all computation to backend services.
"""

from __future__ import annotations

from typing import Any

from PyQt6.QtCore import QThread, pyqtSignal

from src.backend.analysis.metrics_aggregator import MetricsAggregator
from src.utils.logger import logger


class InsightWorker(QThread):
    """Worker thread for generating AI insights."""

    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, service: Any, stats_text: str):
        super().__init__()
        self.service = service
        self.stats_text = stats_text

    def run(self):
        logger.info("InsightWorker: generating coach insights...")
        try:
            insight = self.service.generate_coach_insights(self.stats_text)
            logger.info("InsightWorker: coach insights generated successfully")
            self.finished.emit(insight)
        except Exception as e:
            logger.error("InsightWorker failed: %s", e, exc_info=True)
            self.error.emit(str(e))


class StatsWorker(QThread):
    """Worker thread bridging MetricsAggregator to PyQt signals."""

    finished = pyqtSignal(dict)

    def __init__(
        self,
        games: list[dict[str, Any]],
        usernames: list[str],
        color_filter: str = "All Colors",
        format_filter: str = "All Formats",
        source_filter: str = "All Sources",
        date_filter: str = "All Time",
    ):
        super().__init__()
        self.games = games
        self.usernames = usernames
        self.color_filter = color_filter
        self.format_filter = format_filter
        self.source_filter = source_filter
        self.date_filter = date_filter

    def run(self):
        logger.debug(
            "StatsWorker: calculating stats for %d games (filters: %s, %s, %s, %s)",
            len(self.games),
            self.color_filter,
            self.format_filter,
            self.source_filter,
            self.date_filter,
        )
        try:
            stats = self._calculate_stats()
            logger.debug(
                "StatsWorker: stats calculated successfully (%d games matched)",
                stats.get("total", 0),
            )
            self.finished.emit(stats)
        except Exception as e:
            logger.error("StatsWorker failed to calculate stats: %s", e, exc_info=True)
            self.finished.emit({})

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

    def _calculate_stats(self) -> dict[str, Any]:
        """Compatibility shim delegating to MetricsAggregator."""
        return MetricsAggregator.calculate_stats(
            games=self.games,
            usernames=self.usernames,
            color_filter=self.color_filter,
            format_filter=self.format_filter,
            source_filter=self.source_filter,
            date_filter=self.date_filter,
        )
