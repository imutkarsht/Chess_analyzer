"""
Reusable "AI is writing" placeholder: breathing skeleton rows and a status line.

Extracted from the metrics AI Coach card so the per-game Report shows the same
affordance while its summary is generated, instead of a blocking spinner. The
skeleton never changes size, so swapping it for real text does not jump the
layout.
"""

from __future__ import annotations

from collections.abc import Sequence

from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, QSequentialAnimationGroup, Qt
from PyQt6.QtWidgets import (
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.gui.styles import Styles

# (header bar width, body row width ratios) — a header pill plus prose lines.
Section = tuple[int, Sequence[float]]

DEFAULT_SECTIONS: tuple[Section, ...] = (
    (140, (0.92, 0.68)),
    (160, (0.95, 0.78, 0.48)),
    (135, (0.90, 0.60)),
)

_ROW_HEIGHT = 10
_ROW_RADIUS = 5
_HEADER_HEIGHT = 12
_HEADER_RADIUS = 6


class PulsingSkeleton(QWidget):
    """Breathing placeholder rows, in the style of ChatGPT/Gemini loading states."""

    def __init__(
        self,
        title: str,
        subtitle: str = "",
        sections: tuple[Section, ...] = DEFAULT_SECTIONS,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setObjectName("pulsingSkeleton")
        self.setStyleSheet("background: transparent;")
        self._animation: QSequentialAnimationGroup | None = None
        self._effect: QGraphicsOpacityEffect | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 8, 4, 12)
        layout.setSpacing(14)

        header_row = QHBoxLayout()
        header_row.setSpacing(8)
        header_row.setAlignment(Qt.AlignmentFlag.AlignLeft)

        dot = QLabel("●")
        dot.setStyleSheet(
            f"color: {Styles.COLOR_ACCENT}; font-size: 10px; background: transparent;"
        )
        header_row.addWidget(dot)

        self._title = QLabel(title)
        self._title.setStyleSheet(
            f"color: {Styles.COLOR_TEXT_PRIMARY}; font-size: 13px; font-weight: 600; "
            "background: transparent;"
        )
        header_row.addWidget(self._title)
        header_row.addStretch()
        layout.addLayout(header_row)

        if subtitle:
            self._subtitle = QLabel(subtitle)
            self._subtitle.setWordWrap(True)
            self._subtitle.setStyleSheet(
                f"color: {Styles.COLOR_TEXT_SECONDARY}; font-size: 11px; "
                "background: transparent; padding-left: 16px;"
            )
            layout.addWidget(self._subtitle)

        layout.addSpacing(6)
        for index, (header_width, ratios) in enumerate(sections):
            if index:
                layout.addWidget(self._divider())
            section = QVBoxLayout()
            section.setSpacing(8)
            section.addWidget(
                self._row(fixed_width=header_width, height=_HEADER_HEIGHT, radius=_HEADER_RADIUS)
            )
            for ratio in ratios:
                section.addWidget(self._row(width_ratio=ratio))
            layout.addLayout(section)

        layout.addStretch()

    # ------------------------------------------------------------------
    # Animation
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Begin (or restart) the breathing animation."""
        self.stop()

        self._effect = QGraphicsOpacityEffect(self)
        self._effect.setOpacity(0.28)
        self.setGraphicsEffect(self._effect)

        fade_in = QPropertyAnimation(self._effect, b"opacity")
        fade_in.setDuration(900)
        fade_in.setStartValue(0.28)
        fade_in.setEndValue(0.85)
        fade_in.setEasingCurve(QEasingCurve.Type.InOutSine)

        fade_out = QPropertyAnimation(self._effect, b"opacity")
        fade_out.setDuration(900)
        fade_out.setStartValue(0.85)
        fade_out.setEndValue(0.28)
        fade_out.setEasingCurve(QEasingCurve.Type.InOutSine)

        self._animation = QSequentialAnimationGroup(self)
        self._animation.addAnimation(fade_in)
        self._animation.addAnimation(fade_out)
        self._animation.setLoopCount(-1)
        self._animation.start()

    def stop(self) -> None:
        """Stop the animation and settle back to a readable opacity."""
        animation, self._animation = self._animation, None
        if animation is not None:
            animation.stop()
        if self._effect is not None:
            self._effect.setOpacity(0.85)

    def is_animating(self) -> bool:
        return (
            self._animation is not None
            and self._animation.state() == QSequentialAnimationGroup.State.Running
        )

    # ------------------------------------------------------------------
    # Building blocks
    # ------------------------------------------------------------------

    def _divider(self) -> QFrame:
        divider = QFrame()
        divider.setFixedHeight(1)
        divider.setStyleSheet(f"background-color: {Styles.COLOR_BORDER}; margin: 2px 0;")
        return divider

    def _row(
        self,
        width_ratio: float | None = None,
        fixed_width: int | None = None,
        height: int = _ROW_HEIGHT,
        radius: int = _ROW_RADIUS,
    ) -> QWidget:
        row_widget = QWidget()
        row_widget.setStyleSheet("background: transparent;")
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(0)

        bar = QFrame()
        bar.setFixedHeight(height)
        bar.setStyleSheet(
            f"background-color: {Styles.COLOR_SURFACE_LIGHT}; "
            f"border: 1px solid {Styles.COLOR_BORDER}; "
            f"border-radius: {radius}px;"
        )

        if fixed_width is not None:
            bar.setFixedWidth(fixed_width)
            row_layout.addWidget(bar)
            row_layout.addStretch()
        elif width_ratio is not None:
            weight = max(1, int(width_ratio * 100))
            row_layout.addWidget(bar, weight)
            spacer = QWidget()
            spacer.setStyleSheet("background: transparent;")
            row_layout.addWidget(spacer, max(1, 100 - weight))
        else:
            bar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            row_layout.addWidget(bar)

        return row_widget
