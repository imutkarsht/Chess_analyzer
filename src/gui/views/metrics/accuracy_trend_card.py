from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

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
        self.content_widget: QWidget | None = None

        self.segmented_control = self._build_segmented_control()
        super().__init__(
            "Accuracy Trend",
            parent=parent,
            max_height=310,
            action_widget=self.segmented_control,
        )

    def _build_segmented_control(self) -> QFrame:
        container = QFrame()
        container.setObjectName("trend_segmented")
        container.setStyleSheet(f"""
            QFrame#trend_segmented {{
                background-color: {Styles.COLOR_SURFACE_LIGHT};
                border-radius: 6px;
                border: none;
            }}
        """)
        layout = QHBoxLayout(container)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)

        self.btn_10 = QPushButton("10G")
        self.btn_20 = QPushButton("20G")
        self.btn_all = QPushButton("All")

        for btn, window in [
            (self.btn_10, "10"),
            (self.btn_20, "20"),
            (self.btn_all, "all"),
        ]:
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedHeight(22)
            btn.clicked.connect(lambda _, w=window: self.set_window(w))
            layout.addWidget(btn)

        self._update_segmented_styles()
        return container

    def _update_segmented_styles(self):
        active_style = f"""
            QPushButton {{
                background-color: {Styles.COLOR_SURFACE_CARD};
                color: {Styles.COLOR_TEXT_PRIMARY};
                font-weight: 600;
                font-size: 11px;
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 4px;
                padding: 1px 7px;
            }}
        """
        inactive_style = f"""
            QPushButton {{
                background-color: transparent;
                color: {Styles.COLOR_TEXT_SECONDARY};
                font-weight: 500;
                font-size: 11px;
                border: 1px solid transparent;
                border-radius: 4px;
                padding: 1px 7px;
            }}
            QPushButton:hover {{
                color: {Styles.COLOR_TEXT_PRIMARY};
                background-color: {Styles.COLOR_SURFACE_LIGHT};
            }}
        """
        self.btn_10.setStyleSheet(active_style if self.current_window == "10" else inactive_style)
        self.btn_20.setStyleSheet(active_style if self.current_window == "20" else inactive_style)
        self.btn_all.setStyleSheet(active_style if self.current_window == "all" else inactive_style)

    def set_window(self, window: str):
        if self.current_window == window:
            return
        self.current_window = window
        self._update_segmented_styles()
        self._render_view()

    def set_stats(self, stats: dict):
        self.stats = stats or {}
        self._render_view()

    def _render_view(self):
        if self.content_widget:
            self.card_layout.removeWidget(self.content_widget)
            self.content_widget.deleteLater()
            self.content_widget = None

        full_history = self.stats.get("accuracy_history", [])

        # History is ordered newest-to-oldest; reverse to plot chronologically left-to-right
        if self.current_window == "10":
            accuracies = full_history[:10][::-1] if full_history else []
        elif self.current_window == "20":
            accuracies = full_history[:20][::-1] if full_history else []
        else:
            accuracies = full_history[::-1] if full_history else []

        self.content_widget = QWidget()
        self.content_widget.setStyleSheet("background: transparent;")
        main_vbox = QVBoxLayout(self.content_widget)
        main_vbox.setContentsMargins(0, 0, 0, 0)
        main_vbox.setSpacing(6)

        if not accuracies:
            empty_lbl = QLabel("No accuracy data available for selected filters.")
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

        stats_strip.addWidget(make_badge("Avg", f"{avg_acc:.1f}%", Styles.COLOR_ACCENT))
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
        if hasattr(self, "segmented_control"):
            self.segmented_control.setStyleSheet(f"""
                QFrame#trend_segmented {{
                    background-color: {Styles.COLOR_SURFACE_LIGHT};
                    border-radius: 6px;
                    border: none;
                }}
            """)
            self._update_segmented_styles()
        if self.stats:
            self._render_view()
