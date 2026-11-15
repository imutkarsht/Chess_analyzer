# SPDX-License-Identifier: GPL-3.0-only
"""Compact, move-synchronized think-time chart for game analysis."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QMouseEvent, QPainter, QPen
from PyQt6.QtWidgets import QWidget

from src.backend.analysis.metrics.game_time_management import (
    has_clock_data,
    is_disproportionate,
    is_time_trouble,
)
from src.backend.storage.models import MoveAnalysis
from src.gui.styles import Styles


class ThinkTimeChart(QWidget):
    """Render one bar per ply and navigate when a bar is clicked."""

    move_selected = pyqtSignal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._moves: list[MoveAnalysis] = []
        self._starting_clock: float | None = None
        self._current_move: int | None = None
        self.setMinimumHeight(72)
        self.setMaximumHeight(96)
        self.setMouseTracking(True)
        self.setAccessibleName("Think Time chart")

    @property
    def moves(self) -> list[MoveAnalysis]:
        return self._moves

    @property
    def current_move(self) -> int | None:
        return self._current_move

    def set_moves(
        self,
        moves: list[MoveAnalysis] | None,
        starting_clock: float | None = None,
    ) -> None:
        self._moves = list(moves or [])
        self._starting_clock = starting_clock
        self._current_move = None
        self.setVisible(self.has_clock_data)
        self.update()

    @property
    def has_clock_data(self) -> bool:
        return has_clock_data(self._moves)

    def set_current_move(self, index: int | None) -> None:
        self._current_move = (
            index if index is not None and 0 <= index < len(self._moves) else None
        )
        self.update()

    def move_is_time_trouble(self, move: MoveAnalysis) -> bool:
        return is_time_trouble(move)

    def move_is_disproportionate(self, move: MoveAnalysis) -> bool:
        return is_disproportionate(move, self._starting_clock)

    def refresh_styles(self) -> None:
        self.update()

    def paintEvent(self, _event) -> None:
        if not self.has_clock_data:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(8, 8, -8, -18)
        count = len(self._moves)
        if count == 0 or rect.width() <= 0 or rect.height() <= 0:
            return

        times = [max(0.0, move.time_spent or 0.0) for move in self._moves]
        maximum = max(times, default=0.0) or 1.0
        slot = rect.width() / count
        bar_width = max(1.0, slot * 0.7)
        for index, (move, seconds) in enumerate(zip(self._moves, times, strict=True)):
            color = (
                Styles.COLOR_BLUNDER
                if self.move_is_time_trouble(move) or self.move_is_disproportionate(move)
                else Styles.COLOR_ACCENT
            )
            height = rect.height() * seconds / maximum
            x = rect.left() + index * slot + (slot - bar_width) / 2
            y = rect.bottom() - height
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color)
            painter.drawRoundedRect(int(x), int(y), int(bar_width), int(height), 2, 2)

            if index == self._current_move:
                painter.setPen(QPen(Styles.COLOR_TEXT_PRIMARY, 1.5))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawLine(
                    int(x + bar_width / 2),
                    rect.top(),
                    int(x + bar_width / 2),
                    rect.bottom(),
                )

        painter.setPen(Styles.COLOR_TEXT_SECONDARY)
        label_step = max(1, count // 8)
        for index in range(0, count, label_step):
            x = rect.left() + (index + 0.5) * slot
            painter.drawText(int(x - 8), rect.bottom() + 14, str(index + 1))

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton or not self._moves:
            return
        rect = self.rect().adjusted(8, 8, -8, -18)
        if rect.width() <= 0:
            return
        position = min(max(event.position().x() - rect.left(), 0.0), rect.width())
        index = min(int(position / rect.width() * len(self._moves)), len(self._moves) - 1)
        self.move_selected.emit(index)
        event.accept()
