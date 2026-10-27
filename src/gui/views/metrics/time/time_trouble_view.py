"""Time Trouble page for the Time & Clock Analytics card."""

from __future__ import annotations

import math

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from src.gui.styles import Styles
from src.gui.utils.gui_utils import clear_layout
from src.gui.views.metrics.time.panels import NoClockBanner, StatPanel


class TroubleView(QWidget):
    """Error rates under time pressure versus normal clock."""

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
                NoClockBanner(
                    "Time trouble analytics require per-move [%clk] tags."
                )
            )
            return

        trouble = self._time_data.get("time_trouble", {})
        normal_moves = trouble.get("normal_moves", 0)
        normal_blunders = trouble.get("normal_blunders", 0)
        normal_pct = trouble.get("normal_blunder_pct", 0.0)
        trouble_moves = trouble.get("trouble_moves", 0)
        trouble_blunders = trouble.get("trouble_blunders", 0)
        trouble_pct = trouble.get("trouble_blunder_pct", 0.0)
        panic_mult = trouble.get("panic_multiplier", 1.0)
        timeouts = trouble.get("total_time_losses", 0)

        comparison = QHBoxLayout()
        comparison.setSpacing(10)
        comparison.addWidget(
            StatPanel(
                object_name="nc_card",
                title="Normal Clock",
                threshold=">15s Bullet, >30s Blitz",
                value=f"{normal_pct:.1f}%",
                description=f"{normal_blunders} errors across {normal_moves} moves",
                icon_name="fa5s.shield-alt",
                icon_color=Styles.COLOR_RESULT_WIN,
                background=Styles.COLOR_SURFACE_LIGHT,
                border_color=Styles.COLOR_BORDER,
                radius=8,
                padding="10px",
                title_size=12,
                value_size=24,
                content_margins=(6, 4, 6, 4),
                spacing=4,
            )
        )
        comparison.addWidget(
            StatPanel(
                object_name="tt_card",
                title="Time Trouble",
                threshold="≤15s Bullet, ≤30s Blitz",
                value=f"{trouble_pct:.1f}%",
                description=(
                    f"{trouble_blunders} errors across {trouble_moves} scramble moves"
                ),
                icon_name="fa5s.tachometer-alt",
                icon_color=Styles.COLOR_BLUNDER,
                background=Styles.COLOR_SURFACE_LIGHT,
                border_color=(
                    Styles.COLOR_BLUNDER if panic_mult > 1.2 else Styles.COLOR_BORDER
                ),
                value_color=(
                    Styles.COLOR_BLUNDER if panic_mult > 1.2 else Styles.COLOR_BEST
                ),
                radius=8,
                padding="10px",
                title_size=12,
                value_size=24,
                content_margins=(6, 4, 6, 4),
                spacing=4,
            )
        )
        self._layout.addLayout(comparison)
        self._layout.addWidget(
            self._build_panic_banner(
                panic_mult=panic_mult,
                trouble_pct=trouble_pct,
                normal_pct=normal_pct,
                trouble_moves=trouble_moves,
                timeouts=timeouts,
            )
        )

    def _build_panic_banner(
        self,
        *,
        panic_mult: float,
        trouble_pct: float,
        normal_pct: float,
        trouble_moves: int,
        timeouts: int,
    ) -> QFrame:
        banner = QFrame()
        banner.setStyleSheet(
            f"""
            background-color: {Styles.COLOR_SURFACE_LIGHT};
            border: 1px solid {Styles.COLOR_BORDER};
            border-radius: 8px;
            padding: 10px 12px;
            """
        )
        layout = QHBoxLayout(banner)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(12)

        info = QVBoxLayout()
        info.setSpacing(2)

        if math.isinf(panic_mult):
            banner_title = "High Blunder Rate Under Time Pressure"
            banner_desc = (
                f"Your tactical errors increase under low clock "
                f"({trouble_pct:.1f}% vs {normal_pct:.1f}%).\n"
                "Focus on pace in the opening and middlegame to preserve time reserves."
            )
            title_color = Styles.COLOR_BLUNDER
        elif panic_mult > 1.2:
            banner_title = f"{panic_mult:.1f}x Blunder Rate Under Time Pressure"
            banner_desc = (
                f"Your tactical errors increase under low clock "
                f"({trouble_pct:.1f}% vs {normal_pct:.1f}%).\n"
                "Focus on pace in the opening and middlegame to preserve time reserves."
            )
            title_color = Styles.COLOR_BLUNDER
        elif panic_mult <= 0.8 and trouble_moves > 0:
            banner_title = "Disciplined in Time Scrambles"
            banner_desc = (
                f"Your error rate remains lower in time trouble ({trouble_pct:.1f}%) "
                f"than in regular play ({normal_pct:.1f}%).\n"
                "You rely successfully on fast tactical intuition when pressed for time."
            )
            title_color = Styles.COLOR_RESULT_WIN
        else:
            banner_title = "Stable Under Clock Pressure"
            banner_desc = (
                "Your error rate remains consistent regardless of clock situation. "
                "You maintain good stability."
            )
            title_color = Styles.COLOR_TEXT_PRIMARY

        title = QLabel(banner_title)
        title.setStyleSheet(
            f"color: {title_color}; font-weight: 700; font-size: 12px; border: none;"
        )
        info.addWidget(title)

        desc = QLabel(banner_desc)
        desc.setStyleSheet(
            f"color: {Styles.COLOR_TEXT_SECONDARY}; font-size: 11px; border: none;"
        )
        desc.setWordWrap(True)
        info.addWidget(desc)
        layout.addLayout(info, stretch=1)

        pill = QFrame()
        pill.setObjectName("to_pill")
        pill.setStyleSheet(f"""
            QFrame#to_pill {{
                background-color: {Styles.COLOR_SURFACE};
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 6px;
            }}
        """)
        pill_layout = QVBoxLayout(pill)
        pill_layout.setContentsMargins(12, 6, 12, 6)
        pill_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        count = QLabel(str(timeouts))
        count_color = (
            Styles.COLOR_BLUNDER if timeouts > 0 else Styles.COLOR_TEXT_PRIMARY
        )
        count.setStyleSheet(
            f"color: {count_color}; font-size: 16px; font-weight: 800; border: none;"
        )
        count.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pill_layout.addWidget(count)

        label = QLabel("Timeouts")
        label.setStyleSheet(
            f"color: {Styles.COLOR_TEXT_MUTED}; font-size: 9px; "
            "font-weight: 600; border: none;"
        )
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pill_layout.addWidget(label)

        layout.addWidget(pill)
        return banner
