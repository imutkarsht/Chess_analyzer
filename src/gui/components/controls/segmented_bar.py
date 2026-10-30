"""Shared proportional multi-segment bar for dashboard cards."""

from __future__ import annotations

from collections.abc import Iterable

from PyQt6.QtWidgets import QFrame, QHBoxLayout, QWidget

from src.gui.styles import Styles


class SegmentedBar(QFrame):
    """A fixed-height track split into proportional colored segments.

    Each segment is ``(stretch, color, tooltip)``. Callers pass the same
    stretch values they previously gave to ``addWidget(stretch=...)``; the
    default segment radius matches the rounded 6px card bars. Cards rebuild
    the bar when ``MetricCard.refresh_styles`` re-renders their content.
    """

    def __init__(
        self,
        segments: Iterable[tuple[int, str, str | None]] = (),
        *,
        height: int = 6,
        radius: int = 3,
        segment_radius: int = 2,
        spacing: int = 1,
        track_color: str | None = Styles.COLOR_SURFACE,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("SegmentedBar")
        self._radius = radius
        self._segment_radius = segment_radius
        self._track_color = track_color

        self.setFixedHeight(height)
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(spacing)

        for segment in segments:
            self._add_segment(segment)
        self.refresh_styles()

    def _add_segment(self, segment: tuple[int, str, str | None]) -> None:
        stretch, color, tooltip = segment
        widget = QFrame()
        widget.setFixedHeight(self.height())
        widget.setStyleSheet(
            f"background-color: {color}; border-radius: {self._segment_radius}px; "
            "border: none;"
        )
        if tooltip:
            widget.setToolTip(tooltip)
        self._layout.addWidget(widget, max(1, int(stretch)))

    def refresh_styles(self) -> None:
        background = self._track_color or "transparent"
        self.setStyleSheet(
            f"""
            QFrame#SegmentedBar {{
                background-color: {background};
                border-radius: {self._radius}px;
                border: none;
            }}
            """
        )
