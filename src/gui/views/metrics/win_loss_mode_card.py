from PyQt6.QtWidgets import QWidget, QHBoxLayout
from src.gui.views.metrics.base_card import MetricCard
from src.gui.styles import Styles
from src.gui.metrics.charts import create_stacked_bar_figure, fig_to_canvas, create_legend_widget
from src.gui.metrics.workers import MODE_ORDER

MODE_COLORS = {
    "Checkmate": Styles.COLOR_BEST,
    "Resignation": Styles.COLOR_ACCENT,
    "Time": "#e67e22",
    "Abandonment": Styles.COLOR_BLUNDER,
    "Draw": "#888888",
    "Other": "#888888",
}

class WinLossModeCard(MetricCard):
    """Shows how games are won vs lost, split by termination mode."""

    def __init__(self, parent=None):
        super().__init__("How You Win vs How You Lose", parent=parent)
        self.content_widget = None

    def set_stats(self, stats):
        if self.content_widget:
            self.card_layout.removeWidget(self.content_widget)
            self.content_widget.deleteLater()

        win_modes = stats.get('win_modes', {})
        loss_modes = stats.get('loss_modes', {})

        def segments(modes):
            segs = []
            for mode in MODE_ORDER:
                value = modes.get(mode, 0)
                if value > 0:
                    segs.append((value, MODE_COLORS.get(mode, "#888888"), mode))
            return segs

        win_row = segments(win_modes)
        loss_row = segments(loss_modes)

        total_wins = sum(v for v, _, _ in win_row)
        total_losses = sum(v for v, _, _ in loss_row)

        fig = create_stacked_bar_figure(
            [win_row, loss_row],
            ["Wins", "Losses"],
            figsize=(4, 1.8),
            center_text=f"{total_wins} W · {total_losses} L",
        )
        canvas = fig_to_canvas(fig)

        self.content_widget = QWidget()
        layout = QHBoxLayout(self.content_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(canvas, stretch=3)

        legend_labels = []
        legend_colors = []
        legend_values = []
        for mode in MODE_ORDER:
            count = win_modes.get(mode, 0) + loss_modes.get(mode, 0)
            if count > 0:
                legend_labels.append(mode)
                legend_colors.append(MODE_COLORS.get(mode, "#888888"))
                legend_values.append(count)

        if legend_labels:
            layout.addWidget(create_legend_widget(legend_labels, legend_colors, legend_values), stretch=2)

        self.set_content(self.content_widget)
