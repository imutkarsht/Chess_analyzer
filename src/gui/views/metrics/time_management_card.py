from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame
from PyQt6.QtCore import Qt
from src.gui.views.metrics.base_card import MetricCard
from src.gui.styles import Styles

class TimeManagementCard(MetricCard):
    """Time usage insights from per-move clock data."""

    def __init__(self, parent=None):
        super().__init__("Time Management", parent=parent)
        self.content_widget = None

    @staticmethod
    def _format_seconds(seconds):
        seconds = max(0, int(round(seconds)))
        minutes, secs = divmod(seconds, 60)
        if minutes > 0:
            return f"{minutes}m {secs:02d}s"
        return f"{secs}s"

    def set_stats(self, stats):
        if self.content_widget:
            self.card_layout.removeWidget(self.content_widget)
            self.content_widget.deleteLater()

        self.content_widget = QWidget()
        layout = QVBoxLayout(self.content_widget)
        layout.setSpacing(16)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        avg_think = stats.get('avg_think_time', 0)
        pressure_pct = stats.get('time_pressure_pct', 0)
        comfortable_pct = max(0.0, 100.0 - pressure_pct)

        # Two stat tiles
        tiles_row = QHBoxLayout()
        tiles_row.setSpacing(12)

        def make_tile(label, value, color):
            tile = QFrame()
            tile.setStyleSheet(f"""
                QFrame {{
                    background-color: {Styles.COLOR_SURFACE_LIGHT};
                    border-radius: 10px;
                    border: none;
                }}
            """)
            t_layout = QVBoxLayout(tile)
            t_layout.setContentsMargins(14, 12, 14, 12)
            t_layout.setSpacing(2)

            lbl_label = QLabel(label)
            lbl_label.setStyleSheet(f"color: {Styles.COLOR_TEXT_MUTED}; font-size: 11px; "
                                    f"font-weight: 600; {Styles.get_transparent_label_style()}")
            lbl_value = QLabel(value)
            lbl_value.setStyleSheet(f"color: {color}; font-size: 22px; font-weight: 700; "
                                    f"{Styles.get_transparent_label_style()}")
            t_layout.addWidget(lbl_label)
            t_layout.addWidget(lbl_value)
            return tile

        tiles_row.addWidget(make_tile("AVG THINK TIME / MOVE", self._format_seconds(avg_think),
                                      Styles.COLOR_TEXT_PRIMARY), stretch=1)
        tiles_row.addWidget(make_tile("MOVES IN TIME PRESSURE (<30s)", f"{pressure_pct:.0f}%",
                                      Styles.COLOR_ENGINE_BUSY), stretch=1)
        layout.addLayout(tiles_row)

        # Pressure bar
        bar_label_row = QHBoxLayout()
        lbl_bar_title = QLabel("Time Pressure Split")
        lbl_bar_title.setStyleSheet(f"color: {Styles.COLOR_TEXT_SECONDARY}; font-size: 12px; font-weight: 500; "
                                    f"{Styles.get_transparent_label_style()}")
        bar_label_row.addWidget(lbl_bar_title)
        bar_label_row.addStretch()
        layout.addLayout(bar_label_row)

        bar_container = QFrame()
        bar_container.setFixedHeight(18)
        bar_container.setStyleSheet(f"background-color: {Styles.COLOR_SURFACE_LIGHT}; "
                                    f"border-radius: 9px; border: none;")
        bar_layout = QHBoxLayout(bar_container)
        bar_layout.setContentsMargins(0, 0, 0, 0)
        bar_layout.setSpacing(1)

        def add_segment(pct, color):
            if pct > 0:
                seg = QFrame()
                seg.setStyleSheet(f"background-color: {color}; border: none;")
                seg.setToolTip(f"{pct:.0f}%")
                bar_layout.addWidget(seg, stretch=int(pct * 10) if pct * 10 >= 1 else 1)

        add_segment(comfortable_pct, Styles.COLOR_BEST)
        add_segment(pressure_pct, Styles.COLOR_BLUNDER)
        layout.addWidget(bar_container)

        pills = QHBoxLayout()
        pills.setSpacing(12)
        lbl_ok = QLabel(f"{comfortable_pct:.0f}% comfortable")
        lbl_ok.setStyleSheet(f"color: {Styles.COLOR_BEST}; font-size: 11px; font-weight: 600; "
                             f"{Styles.get_transparent_label_style()}")
        lbl_press = QLabel(f"{pressure_pct:.0f}% under pressure")
        lbl_press.setStyleSheet(f"color: {Styles.COLOR_BLUNDER}; font-size: 11px; font-weight: 600; "
                                f"{Styles.get_transparent_label_style()}")
        pills.addWidget(lbl_ok)
        pills.addWidget(lbl_press)
        pills.addStretch()
        layout.addLayout(pills)

        layout.addStretch()
        self.set_content(self.content_widget)
