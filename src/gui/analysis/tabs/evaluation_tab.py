# SPDX-License-Identifier: GPL-3.0-only
"""Evaluation tab: evaluation graph, engine-line toggles, and displayed lines."""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QSizePolicy, QVBoxLayout, QWidget

from src.gui.components import Checkbox, GraphWidget
from src.gui.engine_lines import EngineLinesConfig, EngineLinesWidget
from src.utils.config import ConfigManager


class EvaluationTab(QWidget):
    """Plots the game evaluation and hosts the engine-line controls."""

    cache_toggled = pyqtSignal(bool)
    # (FEN the lines belong to, first move UCI) — opens board variation mode.
    variation_requested = pyqtSignal(str, str)

    def __init__(self) -> None:
        super().__init__()
        self.setStyleSheet("background: transparent;")
        self.config_manager = ConfigManager()
        self.graph_widget: GraphWidget | None = None
        self._lines_fen: str | None = None

        self.eval_layout = QVBoxLayout(self)
        self.eval_layout.setContentsMargins(5, 5, 5, 5)

        # Matplotlib is imported lazily with the first game, keeping it off the
        # first-launch path.
        self.graph_placeholder = QWidget()
        self.eval_layout.addWidget(self.graph_placeholder, stretch=2)

        toggles_layout = QHBoxLayout()
        toggles_layout.setContentsMargins(0, 6, 0, 6)
        toggles_layout.setSpacing(10)

        self.toggle_checkbox = Checkbox("Engine Lines")
        self.toggle_checkbox.setChecked(self.config_manager.engine_lines_enabled)
        toggles_layout.addWidget(self.toggle_checkbox)

        self.cache_checkbox = Checkbox("Use Cache")
        self.cache_checkbox.setChecked(self.config_manager.use_cache)
        self.cache_checkbox.toggled.connect(self.cache_toggled.emit)
        toggles_layout.addWidget(self.cache_checkbox)
        toggles_layout.addStretch()
        self.eval_layout.addLayout(toggles_layout)

        self.lines_widget = EngineLinesWidget(
            EngineLinesConfig(empty_text="No engine lines yet")
        )
        self.lines_widget.line_clicked.connect(self._on_line_clicked)
        self.eval_layout.addWidget(self.lines_widget, stretch=0)
        # Keep the graph, toggles and lines stacked; without a trailing stretch
        # the box layout spreads the leftover height as gaps between them.
        self.eval_layout.addStretch(1)

    def ensure_graph(self) -> None:
        """Create the Matplotlib-backed graph on first game load."""
        if self.graph_widget is not None:
            return

        graph = GraphWidget()
        graph.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.eval_layout.insertWidget(0, graph, stretch=2)
        self.graph_placeholder.hide()
        self.graph_widget = graph

    def render(self, game) -> None:
        self.ensure_graph()
        self.graph_widget.plot_game(game)

    def clear(self) -> None:
        self._lines_fen = None
        self.lines_widget.clear()

    def update_lines(self, lines, fen: str | None = None) -> None:
        """Render White-perspective engine lines for the board position."""
        self._lines_fen = fen
        self.lines_widget.set_lines(lines)

    def _on_line_clicked(self, uci: str) -> None:
        """Enter variation mode at the position the displayed lines belong to."""
        if not self._lines_fen or not uci:
            return
        self.variation_requested.emit(self._lines_fen, uci)

    def refresh_styles(self) -> None:
        if self.graph_widget is not None:
            self.graph_widget.refresh_styles()
        self.toggle_checkbox.refresh_styles()
        self.cache_checkbox.refresh_styles()
        self.lines_widget.refresh_styles()


__all__ = ["EvaluationTab"]
