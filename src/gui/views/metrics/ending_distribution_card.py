from PyQt6.QtWidgets import QWidget, QHBoxLayout
from src.gui.views.metrics.base_card import MetricCard
from src.gui.styles import Styles

class EndingDistributionCard(MetricCard):
    def __init__(self, parent=None):
        super().__init__("Ending Distribution", parent=parent, max_height=310)
        self.content_widget = None

    def set_stats(self, stats):
        if self.content_widget:
            self.card_layout.removeWidget(self.content_widget)
            self.content_widget.deleteLater()
            
        counts = stats.get('term_counts', {})
        
        type_colors = {
            "Checkmate": Styles.COLOR_BEST,
            "Resignation": Styles.COLOR_ACCENT,
            "Time": "#e67e22",
            "Abandon": Styles.COLOR_BLUNDER,
            "Draw": "#888888"
        }
        
        labels, sizes, colors = [], [], []
        for k in ["Checkmate", "Resignation", "Time", "Abandon", "Draw"]:
            v = counts.get(k, 0)
            if v > 0:
                labels.append(k)
                sizes.append(v)
                colors.append(type_colors.get(k, '#888'))
        
        from src.gui.metrics.charts import create_donut_figure, fig_to_canvas, create_legend_widget
        center_text = str(sum(sizes)) if sizes else ""
        fig = create_donut_figure(sizes, colors, center_text)
        canvas = fig_to_canvas(fig)
        
        self.content_widget = QWidget()
        layout = QHBoxLayout(self.content_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(canvas, stretch=3)
        layout.addWidget(create_legend_widget(labels, colors, sizes), stretch=2)
        
        self.set_content(self.content_widget)
