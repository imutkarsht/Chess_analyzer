import os

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
)

from src.gui.components import LegendList, SegmentedControl
from src.gui.metrics.charts import create_donut_figure, fig_to_canvas
from src.gui.styles import Styles
from src.gui.utils.gui_utils import resolve_asset
from src.gui.views.metrics.base_card import MetricCard


class EndingDistributionCard(MetricCard):
    def __init__(self, parent=None):
        self.current_mode = "all"  # "all", "won", "lost", "drawn"
        self.stats = {}

        self.segmented_control = SegmentedControl(
            options=[("All", "all"), ("Won", "won"), ("Lost", "lost"), ("Drawn", "drawn")],
            value=self.current_mode,
        )
        self.segmented_control.valueChanged.connect(self.set_mode)
        super().__init__(
            "Ending Distribution",
            parent=parent,
            max_height=310,
            action_widget=self.segmented_control,
        )

        # Compatibility aliases for existing callers/tests.
        self.btn_all = self.segmented_control.button("all")
        self.btn_won = self.segmented_control.button("won")
        self.btn_lost = self.segmented_control.button("lost")
        self.btn_drawn = self.segmented_control.button("drawn")

    def set_mode(self, mode: str):
        if self.current_mode == mode:
            return
        self.current_mode = mode
        self.segmented_control.set_value(mode, emit=False)
        self._render_view()

    def _render_view(self):
        if self.current_mode == "won":
            counts = self.stats.get("win_term_counts", {})
            keys = ["Checkmate", "Resignation", "Time", "Abandon"]
            center_suffix = "Won"
        elif self.current_mode == "lost":
            counts = self.stats.get("loss_term_counts", {})
            keys = ["Checkmate", "Resignation", "Time", "Abandon"]
            center_suffix = "Lost"
        elif self.current_mode == "drawn":
            counts = self.stats.get("draw_term_counts", {})
            keys = [
                "3-Fold Repetition",
                "Agreement",
                "Stalemate",
                "Insufficient vs Timeout",
                "Insufficient Material",
                "50-Move Rule",
            ]
            center_suffix = "Drawn"
        else:
            counts = self.stats.get("term_counts", {})
            keys = ["Checkmate", "Resignation", "Time", "Draw", "Abandon"]
            center_suffix = ""

        type_colors = {
            "Checkmate": Styles.COLOR_BEST,
            "Resignation": Styles.COLOR_ACCENT,
            "Time": "#e67e22",
            "Abandon": Styles.COLOR_BLUNDER,
            "Draw": "#888888",
            "3-Fold Repetition": "#3498db",
            "Agreement": "#1abc9c",
            "Stalemate": "#9b59b6",
            "Insufficient vs Timeout": "#e67e22",
            "Insufficient Material": "#f1c40f",
            "50-Move Rule": "#95a5a6",
        }

        icon_map = {
            "Checkmate": "checkmate.svg",
            "Resignation": "resign.svg",
            "Time": "timeout.svg",
            "Abandon": "resign.svg",
            "Draw": "draw_black.svg",
            "Insufficient vs Timeout": "timeout.svg",
        }

        qta_icon_map = {
            "3-Fold Repetition": "fa6s.repeat",
            "Agreement": "fa6s.handshake",
            "Stalemate": "fa6s.chess-king",
            "Insufficient Material": "fa6s.scale-balanced",
            "50-Move Rule": "fa6s.flag",
        }

        labels, sizes, colors = [], [], []
        for k in keys:
            v = counts.get(k, 0)
            if v > 0:
                labels.append(k)
                sizes.append(v)
                colors.append(type_colors.get(k, "#888888"))

        total_endings = sum(sizes)
        center_text = f"{total_endings}\n{center_suffix}".strip() if total_endings > 0 else ""

        fig = create_donut_figure(
            sizes,
            colors,
            center_text,
            figsize=(3.5, 3.0),
            text_color=Styles.COLOR_TEXT_PRIMARY,
        )
        canvas = fig_to_canvas(fig)

        main_vbox = self.new_content(spacing=6).layout()

        chart_row = QHBoxLayout()
        chart_row.setContentsMargins(0, 0, 0, 0)
        chart_row.addWidget(canvas, stretch=3)

        # Legend Sidebar
        legend = LegendList(spacing=6)

        if total_endings == 0:
            mode_label = (
                f"No {self.current_mode} games recorded"
                if self.current_mode != "all"
                else "No games recorded"
            )
            legend.add_empty(mode_label, italic=True)
        else:
            for k in keys:
                v = counts.get(k, 0)
                if v == 0:
                    continue

                icon_file = icon_map.get(k)
                icon_path = resolve_asset(icon_file) if icon_file else None
                pixmap = None

                if icon_path and os.path.exists(icon_path):
                    pm = QPixmap(icon_path)
                    if not pm.isNull():
                        pixmap = pm.scaled(
                            18,
                            18,
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation,
                        )
                elif k in qta_icon_map:
                    try:
                        import qtawesome as qta

                        pixmap = qta.icon(
                            qta_icon_map[k], color=type_colors.get(k, "#ffffff")
                        ).pixmap(16, 16)
                    except Exception:
                        pixmap = None

                pct = (v / total_endings * 100) if total_endings > 0 else 0
                legend.add_row(
                    k,
                    f"{v} ({pct:.0f}%)",
                    type_colors.get(k, "#888888"),
                    pixmap,
                )

        chart_row.addWidget(legend, stretch=3)
        main_vbox.addLayout(chart_row)

        # Clock Alert if losses on time >= 25% and at least 3 losses (relevant for All and Lost views)
        if self.current_mode in ("all", "lost"):
            time_loss_pct = self.stats.get("time_loss_pct", 0.0)
            losses = self.stats.get("losses", 0)
            if time_loss_pct >= 25.0 and losses >= 3:
                alert_lbl = QLabel(f"Clock Alert: {time_loss_pct:.0f}% of losses on time")
                alert_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                alert_lbl.setStyleSheet("""
                    background-color: rgba(230, 126, 34, 0.15);
                    color: #e67e22;
                    border-radius: 4px;
                    padding: 3px 8px;
                    font-size: 11px;
                    font-weight: 600;
                    border: none;
                """)
                main_vbox.addWidget(alert_lbl)

        self.set_content(self.content_widget)
