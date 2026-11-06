# SPDX-License-Identifier: GPL-3.0-only
"""Engine evaluation pill used by the shared engine-lines panel."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QWidget

from src.gui.styles import Styles

if TYPE_CHECKING:  # pragma: no cover - typing only
    from src.backend.analysis.engine_line import EngineLine


class EngineScoreBadge(QLabel):
    """Score pill whose fill follows the live engine evaluation.

    The colours are deliberately not a :class:`TextTone`: they interpolate
    between the white/black piece colours, so they belong to the engine-line
    presentation instead of the semantic text palette.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._line: EngineLine | None = None
        self._apply()

    def set_line(self, line: EngineLine) -> None:
        self._line = line
        self.setText(line.score_text)
        self._apply()

    def clear(self) -> None:
        self._line = None
        super().clear()
        self._apply()

    def refresh_styles(self) -> None:
        self._apply()

    def _apply(self) -> None:
        if self._line is None:
            self.setStyleSheet(
                Styles.get_eval_badge_style(
                    Styles.COLOR_SURFACE_LIGHT,
                    Styles.COLOR_TEXT_PRIMARY,
                )
            )
            return
        self.setStyleSheet(Styles.get_engine_score_badge_style(self._line))
