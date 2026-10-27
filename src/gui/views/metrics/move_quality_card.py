import os

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QHBoxLayout, QSizePolicy

from src.gui.components import LegendList
from src.gui.styles import Styles
from src.gui.utils.gui_utils import resolve_asset
from src.gui.views.metrics.base_card import MetricCard


class MoveQualityCard(MetricCard):
    def __init__(self, parent=None):
        super().__init__("Move Quality Distribution", parent=parent, max_height=310)

    def set_stats(self, stats):
        counts = stats.get("detailed_quality_counts") or stats.get("quality_counts", {})

        order = [
            "Brilliant",
            "Great",
            "Best",
            "Excellent",
            "Good",
            "Book",
            "Inaccuracy",
            "Mistake",
            "Miss",
            "Blunder",
        ]

        color_map = {
            "Brilliant": Styles.COLOR_BRILLIANT,
            "Great": Styles.COLOR_GREAT,
            "Best": Styles.COLOR_BEST,
            "Excellent": Styles.COLOR_BEST,
            "Good": Styles.COLOR_GOOD,
            "Book": "#d5a47e",
            "Inaccuracy": Styles.COLOR_INACCURACY,
            "Mistake": Styles.COLOR_MISTAKE,
            "Miss": Styles.COLOR_MISS,
            "Blunder": Styles.COLOR_BLUNDER,
        }

        icon_map = {
            "Brilliant": "brilliant.svg",
            "Great": "great_find.svg",
            "Best": "best_v2.svg",
            "Excellent": "excellent.svg",
            "Good": "good.svg",
            "Book": "book.svg",
            "Inaccuracy": "inaccuracy.svg",
            "Mistake": "mistake.svg",
            "Miss": "missed_win.svg",
            "Blunder": "blunder.svg",
        }

        labels = []
        sizes = []
        colors = []
        for k in order:
            v = counts.get(k, 0)
            if v > 0:
                labels.append(k)
                sizes.append(v)
                colors.append(color_map.get(k, "#888888"))

        total_moves = sum(sizes)

        fig = Figure(figsize=(3.5, 3.0), dpi=100, facecolor="none")
        fig.subplots_adjust(left=0.05, right=0.95, top=0.95, bottom=0.05)
        ax = fig.add_subplot(111)
        ax.set_facecolor("none")

        if sizes:
            wedges, texts = ax.pie(
                sizes,
                labels=None,
                colors=colors,
                startangle=90,
                wedgeprops=dict(width=0.32, edgecolor="none"),
            )
            ax.text(
                0,
                0,
                str(total_moves),
                ha="center",
                va="center",
                fontsize=18,
                color=Styles.COLOR_TEXT_PRIMARY,
                weight="bold",
            )
        else:
            ax.text(
                0,
                0,
                "No moves",
                ha="center",
                va="center",
                fontsize=12,
                color=Styles.COLOR_TEXT_SECONDARY,
            )

        ax.set_aspect("equal")

        canvas = FigureCanvasQTAgg(fig)
        canvas.setStyleSheet("background: transparent;")
        canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # Container for Chart + Legend
        chart_row = self.new_content().layout()
        layout = QHBoxLayout()
        chart_row.addLayout(layout)
        layout.addWidget(canvas, stretch=3)

        # Custom Legend Sidebar
        legend = LegendList(spacing=6)

        for k in order:
            v = counts.get(k, 0)
            if v == 0:
                continue

            icon_file = icon_map.get(k, f"{k.lower()}.svg")
            icon_path = resolve_asset(icon_file)
            pixmap = None

            if icon_path and os.path.exists(icon_path):
                candidate = QPixmap(icon_path)
                if not candidate.isNull():
                    pixmap = candidate.scaled(
                        18,
                        18,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )

            pct = (v / total_moves * 100) if total_moves > 0 else 0
            legend.add_row(
                k,
                f"{v} ({pct:.0f}%)",
                color_map[k],
                pixmap,
            )

        layout.addWidget(legend, stretch=3)

        self.set_content(self.content_widget)
