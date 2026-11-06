from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QVBoxLayout,
)

from src.gui.components import IconLabel, Label, MiniBar, StatusBadge, TextRole, TextTone
from src.gui.styles import Styles
from src.gui.views.metrics.base_card import MetricCard


class PhasePerformanceCard(MetricCard):
    """
    Card displaying chess performance broken down by game phase:
    Opening (moves 1–15), Middlegame (moves 16–35), and Endgame (moves 36+).
    Features 3 executive pillar tiles with accuracy %, blunder rates, and phase comparison,
    aligned pixel-for-pixel with AccuracyTrendCard.
    """

    def __init__(self, parent=None):
        self.stats: dict = {}

        self.action_badge = StatusBadge("3 Game Phases", tone="neutral")

        super().__init__(
            "Phase Performance",
            parent=parent,
            max_height=310,
            action_widget=self.action_badge,
        )

    def _render_view(self):
        phase_data = self.stats.get("phase_stats", {})
        accuracies = phase_data.get("accuracies", {})
        blunders = phase_data.get("blunders", {})

        # Check for valid data
        has_data = any(accuracies.get(p, 0.0) > 0 for p in ("opening", "middlegame", "endgame"))
        if not has_data:
            self.show_empty("No phase accuracy data available for selected games.")
            return

        main_vbox = self.new_content(spacing=12).layout()

        phases = [
            ("Opening", "opening", "fa5s.chess-pawn", "Moves 1–15"),
            ("Middlegame", "middlegame", "fa5s.chess-knight", "Moves 16–35"),
            ("Endgame", "endgame", "fa5s.chess-king", "Moves 36+"),
        ]

        total_games = self.stats.get("total", 0)

        # 3 Pillar Columns Layout
        col_row = QHBoxLayout()
        col_row.setContentsMargins(0, 0, 0, 0)
        col_row.setSpacing(12)

        for name, key, icon_name, move_range in phases:
            acc = accuracies.get(key, 0.0)
            b_cnt = blunders.get(key, 0)
            bpg = (b_cnt / total_games) if total_games > 0 else 0.0

            # Progress bar color based on chess accuracy standards (never accent)
            if acc >= 80.0:
                bar_color = Styles.COLOR_BEST
            elif acc >= 70.0:
                bar_color = Styles.COLOR_GOOD
            elif acc >= 55.0:
                bar_color = Styles.COLOR_INACCURACY
            else:
                bar_color = Styles.COLOR_BLUNDER

            pillar = QFrame()
            pillar.setObjectName("phase_pillar")
            pillar.setStyleSheet(f"""
                QFrame#phase_pillar {{
                    background-color: {Styles.COLOR_SURFACE_LIGHT};
                    border: 1px solid {Styles.COLOR_BORDER};
                    border-radius: 10px;
                }}
            """)
            p_layout = QVBoxLayout(pillar)
            p_layout.setContentsMargins(14, 14, 14, 14)
            p_layout.setSpacing(8)

            # Top Line: Monochrome Icon badge
            top_line = QHBoxLayout()
            top_line.setContentsMargins(0, 0, 0, 0)

            tile = QFrame()
            tile.setFixedSize(30, 30)
            tile.setStyleSheet(f"""
                background-color: {Styles.COLOR_SURFACE};
                border-radius: 6px;
                border: 1px solid {Styles.COLOR_BORDER};
            """)
            t_layout = QVBoxLayout(tile)
            t_layout.setContentsMargins(0, 0, 0, 0)
            t_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

            t_layout.addWidget(
                IconLabel(icon_name, size=16, tone=TextTone.SECONDARY)
            )

            top_line.addWidget(tile)
            top_line.addStretch()
            p_layout.addLayout(top_line)

            # Name and Move Range
            name_lbl = Label(name, role=TextRole.BODY, weight=700)
            p_layout.addWidget(name_lbl)

            moves_lbl = Label(
                move_range,
                role=TextRole.MICRO,
                tone=TextTone.MUTED,
            )
            p_layout.addWidget(moves_lbl)

            p_layout.addSpacing(2)

            # Big Hero Accuracy Number (Consistent white text)
            acc_lbl = Label(
                f"{acc:.1f}%" if acc > 0 else "N/A",
                role=TextRole.STAT,
                size=22,
                weight=800,
            )
            p_layout.addWidget(acc_lbl)

            # Native Progress Bar
            p_layout.addWidget(
                MiniBar(int(acc), bar_color, height=6, radius=3)
            )

            p_layout.addSpacing(4)

            # Blunders Text
            b_text = (
                f"{b_cnt} blunders ({bpg:.1f}/g)"
                if total_games > 1 and b_cnt > 0
                else (f"{b_cnt} blunders" if b_cnt != 1 else "1 blunder")
            )
            b_lbl = Label(
                b_text,
                role=TextRole.MICRO,
                weight=500,
                tone=TextTone.SECONDARY,
            )
            p_layout.addWidget(b_lbl)

            col_row.addWidget(pillar)

        main_vbox.addLayout(col_row, stretch=1)

        self.set_content(self.content_widget)
