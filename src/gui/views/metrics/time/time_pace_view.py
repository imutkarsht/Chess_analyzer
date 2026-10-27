"""Move Pace page for the Time & Clock Analytics card."""

from __future__ import annotations

from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from src.gui.styles import Styles
from src.gui.utils.gui_utils import clear_layout
from src.gui.views.metrics.time.panels import NoClockBanner, StatPanel


class PaceView(QWidget):
    """Thinking time across phases and decision quality."""

    PHASES = (
        ("Opening", "opening", "fa5s.chess-pawn", "Moves 1–15"),
        ("Middlegame", "middlegame", "fa5s.chess-knight", "Moves 16–35"),
        ("Endgame", "endgame", "fa5s.chess-king", "Moves 36+"),
    )

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(12)
        self._time_data: dict = {}
        self._has_clock = False
        self._dirty = True

    def set_data(self, time_data: dict, has_clock: bool) -> None:
        self._time_data = time_data or {}
        self._has_clock = has_clock
        self._dirty = True

    def mark_dirty(self) -> None:
        self._dirty = True

    def ensure_rendered(self) -> None:
        if not self._dirty:
            return
        self._render()
        self._dirty = False

    def _render(self) -> None:
        clear_layout(self._layout)

        if not self._has_clock:
            self._layout.addWidget(
                NoClockBanner("Move pace analysis requires per-move [%clk] tags.")
            )
            return

        phase_pace = self._time_data.get("phase_pace", {})
        pillars_row = QHBoxLayout()
        pillars_row.setSpacing(10)
        for title, key, icon_name, move_range in self.PHASES:
            info = phase_pace.get(key, {})
            avg_t = info.get("avg_time", 0.0)
            moves = info.get("moves_count", 0)
            pillars_row.addWidget(
                StatPanel(
                    object_name="pace_pillar",
                    title=title,
                    value=f"{avg_t:.1f}s",
                    description=f"{moves} moves • {move_range}",
                    icon_name=icon_name,
                    background=Styles.COLOR_SURFACE_LIGHT,
                    border_color=Styles.COLOR_BORDER,
                    radius=8,
                    padding="8px 10px",
                    title_size=13,
                    value_size=24,
                    content_margins=(6, 4, 6, 4),
                    spacing=3,
                )
            )
        self._layout.addLayout(pillars_row)
        self._layout.addWidget(self._build_decision_quality())

    def _build_decision_quality(self) -> QFrame:
        quality_pace = self._time_data.get("quality_pace", {})
        best_info = quality_pace.get("best", {})
        blunder_info = quality_pace.get("blunder", {})

        best_t = best_info.get("avg_time", 0.0)
        best_m = best_info.get("moves_count", 0)
        blund_t = blunder_info.get("avg_time", 0.0)
        blund_m = blunder_info.get("moves_count", 0)

        card = QFrame()
        card.setObjectName("dq_card")
        card.setStyleSheet(f"""
            QFrame#dq_card {{
                background-color: {Styles.COLOR_SURFACE_LIGHT};
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 8px;
                padding: 10px 12px;
            }}
        """)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(8)

        title = QLabel("Decision Quality vs Thinking Time")
        title.setStyleSheet(
            f"color: {Styles.COLOR_TEXT_PRIMARY}; font-weight: 700; "
            "font-size: 12px; border: none;"
        )
        layout.addWidget(title)

        row = QHBoxLayout()
        row.setSpacing(12)
        row.addWidget(
            StatPanel(
                object_name="best_box",
                title="Best & Brilliant Moves",
                value=f"{best_t:.1f}s",
                description=f"{best_m} precision moves • avg/move",
                title_color=Styles.COLOR_BEST,
                title_size=11,
                title_weight=600,
                value_size=20,
                description_color=Styles.COLOR_TEXT_MUTED,
                background=Styles.COLOR_SURFACE,
                border_color=Styles.COLOR_BORDER,
                radius=6,
                padding="0px",
                content_margins=(12, 8, 12, 8),
                spacing=3,
            )
        )
        row.addWidget(
            StatPanel(
                object_name="blund_box",
                title="Blunders & Mistakes",
                value=f"{blund_t:.1f}s",
                description=f"{blund_m} tactical errors • avg/move",
                title_color=Styles.COLOR_BLUNDER,
                title_size=11,
                title_weight=600,
                value_size=20,
                description_color=Styles.COLOR_TEXT_MUTED,
                background=Styles.COLOR_SURFACE,
                border_color=Styles.COLOR_BORDER,
                radius=6,
                padding="0px",
                content_margins=(12, 8, 12, 8),
                spacing=3,
            )
        )
        layout.addLayout(row)

        if best_t > 0 and blund_t > 0:
            ratio = blund_t / best_t
            if ratio > 1.2:
                insight_text = (
                    f"You spend {ratio:.1f}x longer calculating on blunder positions, "
                    "indicating calculation traps in tricky positions."
                )
            elif ratio < 0.8:
                inv_ratio = 1.0 / ratio
                insight_text = (
                    f"You play blunders {inv_ratio:.1f}x faster than your best moves, "
                    "suggesting premature decisions or impulsive play."
                )
            else:
                insight_text = (
                    "Your thinking time is evenly distributed between best moves and errors."
                )

            insight = QLabel(insight_text)
            insight.setStyleSheet(
                f"color: {Styles.COLOR_TEXT_SECONDARY}; font-size: 11px; "
                f"border-top: 1px solid {Styles.COLOR_BORDER}; padding-top: 6px;"
            )
            insight.setWordWrap(True)
            layout.addWidget(insight)

        return card
