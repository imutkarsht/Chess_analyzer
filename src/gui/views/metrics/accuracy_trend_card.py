from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
)

from src.gui.components import SegmentedControl
from src.gui.metrics.charts import create_accuracy_trend_figure, fig_to_canvas
from src.gui.styles import Styles
from src.gui.views.metrics.base_card import MetricCard


class AccuracyTrendCard(MetricCard):
    """
    Modern accuracy trend card showing game-by-game accuracy,
    rolling moving average trendline, baseline accuracy, and peak/momentum indicators.
    """

    def __init__(self, parent=None):
        self.stats: dict = {}
        self.current_window = "20"  # "10", "20", "all"

        self.segmented_control = SegmentedControl(
            options=[("10G", "10"), ("20G", "20"), ("All", "all")],
            value=self.current_window,
        )
        self.segmented_control.valueChanged.connect(self.set_window)
        super().__init__(
            "Accuracy Trend",
            parent=parent,
            max_height=310,
            action_widget=self.segmented_control,
        )

        # Compatibility aliases for existing callers/tests.
        self.btn_10 = self.segmented_control.button("10")
        self.btn_20 = self.segmented_control.button("20")
        self.btn_all = self.segmented_control.button("all")

    def set_window(self, window: str):
        if self.current_window == window:
            return
        self.current_window = window
        self.segmented_control.set_value(window, emit=False)
        self._render_view()

    def set_stats(self, stats: dict):
        self.stats = stats or {}
        self._render_view()

    def _render_view(self):
        full_history = self.stats.get("accuracy_history", [])

        # History is ordered newest-to-oldest; reverse to plot chronologically left-to-right
        if self.current_window == "10":
            accuracies = full_history[:10][::-1] if full_history else []
        elif self.current_window == "20":
            accuracies = full_history[:20][::-1] if full_history else []
        else:
            accuracies = full_history[::-1] if full_history else []

        if not accuracies:
            self.show_empty("No accuracy data available for selected filters.")
            return

        main_vbox = self.new_content(spacing=6).layout()

        # 1. Quick Stats Strip
        stats_strip = QHBoxLayout()
        stats_strip.setContentsMargins(0, 0, 0, 2)
        stats_strip.setSpacing(8)

        n = len(accuracies)
        avg_acc = sum(accuracies) / n
        peak_acc = max(accuracies)
        low_acc = min(accuracies)
        baseline = self.stats.get("avg_accuracy", avg_acc)

        # Compute momentum / short-term direction
        if n >= 4:
            half = n // 2
            prev_half_avg = sum(accuracies[:half]) / half
            rec_half_avg = sum(accuracies[half:]) / (n - half)
            momentum = rec_half_avg - prev_half_avg
        else:
            momentum = avg_acc - baseline

        # Badges
        def make_badge(label_text: str, value_text: str, val_color: str) -> QFrame:
            frame = QFrame()
            frame.setStyleSheet(f"""
                QFrame {{
                    background-color: {Styles.COLOR_SURFACE_LIGHT};
                    border: 1px solid {Styles.COLOR_BORDER};
                    border-radius: 6px;
                    padding: 2px 6px;
                }}
            """)
            layout = QHBoxLayout(frame)
            layout.setContentsMargins(6, 2, 6, 2)
            layout.setSpacing(4)

            lbl = QLabel(label_text)
            lbl.setStyleSheet(
                f"color: {Styles.COLOR_TEXT_SECONDARY}; font-size: 11px; font-weight: 500; border: none; background: transparent;"
            )
            layout.addWidget(lbl)

            val = QLabel(value_text)
            val.setStyleSheet(
                f"color: {val_color}; font-size: 11px; font-weight: 700; border: none; background: transparent;"
            )
            layout.addWidget(val)
            return frame

        stats_strip.addWidget(make_badge("Avg", f"{avg_acc:.1f}%", Styles.COLOR_TEXT_PRIMARY))
        stats_strip.addWidget(make_badge("Peak", f"{peak_acc:.1f}%", Styles.COLOR_BEST))
        stats_strip.addWidget(make_badge("Low", f"{low_acc:.1f}%", Styles.COLOR_TEXT_SECONDARY))

        # Momentum badge
        if momentum >= 0.5:
            mom_text = f"+{momentum:.1f}%"
            mom_color = Styles.COLOR_BEST
            mom_icon_name = "fa5s.arrow-up"
        elif momentum <= -0.5:
            mom_text = f"{momentum:.1f}%"
            mom_color = Styles.COLOR_BLUNDER
            mom_icon_name = "fa5s.arrow-down"
        else:
            mom_text = "Stable"
            mom_color = Styles.COLOR_TEXT_SECONDARY
            mom_icon_name = "fa5s.minus"

        mom_frame = QFrame()
        mom_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {Styles.COLOR_SURFACE_LIGHT};
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 6px;
                padding: 2px 6px;
            }}
        """)
        mom_layout = QHBoxLayout(mom_frame)
        mom_layout.setContentsMargins(6, 2, 6, 2)
        mom_layout.setSpacing(4)

        try:
            import qtawesome as qta

            icon_lbl = QLabel()
            icon_lbl.setPixmap(qta.icon(mom_icon_name, color=mom_color).pixmap(10, 10))
            icon_lbl.setStyleSheet("border: none; background: transparent;")
            mom_layout.addWidget(icon_lbl)
        except Exception:
            pass

        mom_val = QLabel(mom_text)
        mom_val.setStyleSheet(
            f"color: {mom_color}; font-size: 11px; font-weight: 700; border: none; background: transparent;"
        )
        mom_layout.addWidget(mom_val)

        stats_strip.addWidget(mom_frame)
        stats_strip.addStretch()

        main_vbox.addLayout(stats_strip)

        # 2. Line Chart Canvas
        fig = create_accuracy_trend_figure(
            accuracies,
            figsize=(4.2, 1.8),
            baseline_acc=baseline,
            text_color=Styles.COLOR_TEXT_PRIMARY,
        )
        canvas = fig_to_canvas(fig)
        main_vbox.addWidget(canvas, stretch=1)

        self.set_content(self.content_widget)

    def refresh_styles(self):
        super().refresh_styles()
        if self.stats:
            self._render_view()
