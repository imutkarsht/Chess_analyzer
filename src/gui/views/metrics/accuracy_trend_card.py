from src.gui.views.metrics.base_card import MetricCard

class AccuracyTrendCard(MetricCard):
    def __init__(self, parent=None):
        super().__init__("Accuracy Trend", parent=parent)
        self.content_widget = None

    def set_stats(self, stats):
        if self.content_widget:
            self.card_layout.removeWidget(self.content_widget)
            self.content_widget.deleteLater()
            
        full_history = stats.get('accuracy_history', [])
        accuracies = full_history[:20][::-1] if full_history else []
        
        from src.gui.metrics.charts import create_line_chart_figure, fig_to_canvas
        fig = create_line_chart_figure(accuracies, figsize=(5, 3))
        self.content_widget = fig_to_canvas(fig)
        self.set_content(self.content_widget)
