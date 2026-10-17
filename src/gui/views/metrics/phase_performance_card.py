from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

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
        self.content_widget: QWidget | None = None

        self.action_badge = QLabel("3 Game Phases")
        self.action_badge.setStyleSheet(f"""
            background-color: {Styles.COLOR_SURFACE_LIGHT};
            color: {Styles.COLOR_TEXT_SECONDARY};
            font-size: 11px;
            font-weight: 600;
            border: 1px solid {Styles.COLOR_BORDER};
            border-radius: 6px;
            padding: 3px 8px;
        """)

        super().__init__(
            "Phase Performance",
            parent=parent,
            max_height=310,
            action_widget=self.action_badge,
        )

    def set_stats(self, stats: dict):
        self.stats = stats or {}
        self._render_view()

    def _render_view(self):
        if self.content_widget:
            self.card_layout.removeWidget(self.content_widget)
            self.content_widget.deleteLater()
            self.content_widget = None

        phase_data = self.stats.get("phase_stats", {})
        accuracies = phase_data.get("accuracies", {})
        blunders = phase_data.get("blunders", {})

        self.content_widget = QWidget()
        self.content_widget.setStyleSheet("background: transparent;")
        main_vbox = QVBoxLayout(self.content_widget)
        main_vbox.setContentsMargins(0, 0, 0, 0)
        main_vbox.setSpacing(12)

        # Check for valid data
        has_data = any(accuracies.get(p, 0.0) > 0 for p in ("opening", "middlegame", "endgame"))
        if not has_data:
            empty_lbl = QLabel("No phase accuracy data available for selected games.")
            empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_lbl.setStyleSheet(f"""
                color: {Styles.COLOR_TEXT_SECONDARY};
                font-size: 12px;
                padding: 40px 10px;
                background: transparent;
            """)
            main_vbox.addWidget(empty_lbl)
            self.set_content(self.content_widget)
            return

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

            try:
                import qtawesome as qta

                ic_lbl = QLabel()
                ic_lbl.setPixmap(
                    qta.icon(icon_name, color=Styles.COLOR_TEXT_SECONDARY).pixmap(16, 16)
                )
                ic_lbl.setStyleSheet("border: none; background: transparent;")
                t_layout.addWidget(ic_lbl)
            except Exception:
                pass

            top_line.addWidget(tile)
            top_line.addStretch()
            p_layout.addLayout(top_line)

            # Name and Move Range
            name_lbl = QLabel(name)
            name_lbl.setStyleSheet(f"""
                color: {Styles.COLOR_TEXT_PRIMARY};
                font-weight: 700;
                font-size: 14px;
                border: none;
                background: transparent;
                margin-top: 2px;
            """)
            p_layout.addWidget(name_lbl)

            moves_lbl = QLabel(move_range)
            moves_lbl.setStyleSheet(f"""
                color: {Styles.COLOR_TEXT_MUTED};
                font-size: 11px;
                border: none;
                background: transparent;
            """)
            p_layout.addWidget(moves_lbl)

            p_layout.addSpacing(2)

            # Big Hero Accuracy Number (Consistent white text)
            acc_lbl = QLabel(f"{acc:.1f}%" if acc > 0 else "N/A")
            acc_lbl.setStyleSheet(f"""
                color: {Styles.COLOR_TEXT_PRIMARY};
                font-size: 22px;
                font-weight: 800;
                border: none;
                background: transparent;
            """)
            p_layout.addWidget(acc_lbl)

            # Native Progress Bar
            pbar = QProgressBar()
            pbar.setRange(0, 100)
            pbar.setValue(int(acc))
            pbar.setTextVisible(False)
            pbar.setFixedHeight(6)
            pbar.setStyleSheet(f"""
                QProgressBar {{
                    background-color: {Styles.COLOR_SURFACE};
                    border: none;
                    border-radius: 3px;
                }}
                QProgressBar::chunk {{
                    background-color: {bar_color};
                    border-radius: 3px;
                }}
            """)
            p_layout.addWidget(pbar)

            p_layout.addSpacing(4)

            # Blunders Text
            b_text = (
                f"{b_cnt} blunders ({bpg:.1f}/g)"
                if total_games > 1 and b_cnt > 0
                else (f"{b_cnt} blunders" if b_cnt != 1 else "1 blunder")
            )
            b_lbl = QLabel(b_text)
            b_lbl.setStyleSheet(f"""
                color: {Styles.COLOR_TEXT_SECONDARY};
                font-size: 11px;
                font-weight: 500;
                border: none;
                background: transparent;
            """)
            p_layout.addWidget(b_lbl)

            col_row.addWidget(pillar)

        main_vbox.addLayout(col_row, stretch=1)

        self.set_content(self.content_widget)

    def refresh_styles(self):
        super().refresh_styles()
        if hasattr(self, "action_badge"):
            self.action_badge.setStyleSheet(f"""
                background-color: {Styles.COLOR_SURFACE_LIGHT};
                color: {Styles.COLOR_TEXT_SECONDARY};
                font-size: 11px;
                font-weight: 600;
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 6px;
                padding: 3px 8px;
            """)
        if self.stats:
            self._render_view()
