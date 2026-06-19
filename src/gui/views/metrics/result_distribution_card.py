from src.gui.views.metrics.base_card import MetricCard
from src.gui.styles import Styles

class ResultDistributionCard(MetricCard):
    def __init__(self, parent=None):
        super().__init__("Result Distribution", parent=parent, max_height=310)
        self.content_widget = None

    def set_stats(self, stats):
        if self.content_widget:
            self.card_layout.removeWidget(self.content_widget)
            self.content_widget.deleteLater()
            
        sizes = [stats['wins'], stats['losses'], stats['draws']]
        colors = [Styles.COLOR_ACCENT, '#ca3431', '#888888']
        center_text = f"{stats['win_rate']:.0f}%"
        
        from src.gui.metrics.charts import create_donut_figure, fig_to_canvas
        fig = create_donut_figure(sizes, colors, center_text)
        self.content_widget = fig_to_canvas(fig)
        self.set_content(self.content_widget)
