import os

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from src.gui.styles import Styles
from src.gui.utils.gui_utils import resolve_asset
from src.gui.views.metrics.base_card import MetricCard


class MoveQualityCard(MetricCard):
    def __init__(self, parent=None):
        super().__init__("Move Quality Distribution", parent=parent, max_height=310)
        self.content_widget = None

    def set_stats(self, stats):
        if self.content_widget:
            self.card_layout.removeWidget(self.content_widget)
            self.content_widget.deleteLater()

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
        self.content_widget = QWidget()
        self.content_widget.setStyleSheet("background: transparent;")
        layout = QHBoxLayout(self.content_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(canvas, stretch=3)

        # Custom Legend Sidebar
        legend_widget = QWidget()
        legend_widget.setStyleSheet("background: transparent;")
        legend_layout = QVBoxLayout(legend_widget)
        legend_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        legend_layout.setSpacing(6)

        for k in order:
            v = counts.get(k, 0)
            if v == 0:
                continue

            row = QHBoxLayout()
            row.setSpacing(8)

            icon_file = icon_map.get(k, f"{k.lower()}.svg")
            icon_path = resolve_asset(icon_file)

            if icon_path and os.path.exists(icon_path):
                lbl_icon = QLabel()
                pixmap = QPixmap(icon_path)
                if not pixmap.isNull():
                    pixmap = pixmap.scaled(
                        18,
                        18,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                    lbl_icon.setPixmap(pixmap)
                    lbl_icon.setStyleSheet("border: none; background: transparent;")
                    row.addWidget(lbl_icon)
                else:
                    dot = QLabel("●")
                    dot.setStyleSheet(
                        f"color: {color_map[k]}; font-size: 14px; border: none; background: transparent;"
                    )
                    row.addWidget(dot)
            else:
                dot = QLabel("●")
                dot.setStyleSheet(
                    f"color: {color_map[k]}; font-size: 14px; border: none; background: transparent;"
                )
                row.addWidget(dot)

            lbl_name = QLabel(k)
            lbl_name.setStyleSheet(
                f"color: {Styles.COLOR_TEXT_SECONDARY}; font-size: 12px; font-weight: 500; border: none; background: transparent;"
            )
            row.addWidget(lbl_name)

            row.addStretch()

            pct = (v / total_moves * 100) if total_moves > 0 else 0
            lbl_val = QLabel(f"{v} ({pct:.0f}%)")
            lbl_val.setStyleSheet(
                f"color: {color_map[k]}; font-size: 12px; font-weight: bold; border: none; background: transparent;"
            )
            row.addWidget(lbl_val)

            legend_layout.addLayout(row)

        layout.addWidget(legend_widget, stretch=3)

        self.set_content(self.content_widget)
