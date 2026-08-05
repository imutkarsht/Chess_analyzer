from PyQt6.QtWidgets import QWidget, QHBoxLayout
from src.gui.views.metrics.base_card import MetricCard
from src.gui.styles import Styles
from src.gui.metrics.charts import create_stacked_bar_figure, fig_to_canvas, create_legend_widget
from src.gui.metrics.workers import TIME_CONTROL_ORDER

class TimeControlCard(MetricCard):
    """Win/draw/loss breakdown per time control bucket."""

    def __init__(self, parent=None):
        super().__init__("Performance by Time Control", parent=parent)
        self.content_widget = None

    def set_stats(self, stats):
        if self.content_widget:
            self.card_layout.removeWidget(self.content_widget)
            self.content_widget.deleteLater()

        tc_stats = stats.get('time_control_stats', {})
        has_data = any(b['total'] > 0 for b in tc_stats.values())

        if not has_data:
            from PyQt6.QtWidgets import QLabel
            from PyQt6.QtCore import Qt
            lbl = QLabel("No time control data")
            lbl.setStyleSheet(f"color: {Styles.COLOR_TEXT_SECONDARY}; font-style: italic;")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.content_widget = lbl
            self.set_content(self.content_widget)
            return

        rows = []
        row_labels = []
        totals = []

        colors = {"wins": Styles.COLOR_BEST, "draws": "#888888", "losses": Styles.COLOR_BLUNDER}

        for bucket in TIME_CONTROL_ORDER:
            item = tc_stats.get(bucket, {})
            total = item.get('total', 0)
            if total <= 0:
                continue
            rows.append([
                (item.get('wins', 0), colors["wins"], "W"),
                (item.get('draws', 0), colors["draws"], "D"),
                (item.get('losses', 0), colors["losses"], "L"),
            ])
            row_labels.append(f"{bucket} ({total})")
            totals.append(total)

        fig = create_stacked_bar_figure(rows, row_labels, figsize=(4, 1.8))
        canvas = fig_to_canvas(fig)

        self.content_widget = QWidget()
        layout = QHBoxLayout(self.content_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(canvas, stretch=3)
        layout.addWidget(create_legend_widget(["Wins", "Draws", "Losses"],
                                              [colors["wins"], colors["draws"], colors["losses"]]),
                         stretch=2)

        self.set_content(self.content_widget)
