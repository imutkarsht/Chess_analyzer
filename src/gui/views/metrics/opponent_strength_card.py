from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame
from PyQt6.QtCore import Qt
from src.gui.views.metrics.base_card import MetricCard
from src.gui.styles import Styles

class OpponentStrengthCard(MetricCard):
    """Aggregate opponent-strength stats, order-independent (works for any game set)."""

    def __init__(self, parent=None):
        super().__init__("Opponent Strength", parent=parent, min_height=400)
        self.content_widget = None

    def set_stats(self, stats):
        if self.content_widget:
            self.card_layout.removeWidget(self.content_widget)
            self.content_widget.deleteLater()

        avg_opp = stats.get('avg_opponent_elo', 0)
        max_opp = stats.get('max_opponent_elo', 0)
        best_win = stats.get('best_win', "N/A")

        self.content_widget = QWidget()
        layout = QVBoxLayout(self.content_widget)
        layout.setSpacing(12)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        def make_tile(label, value, color=Styles.COLOR_TEXT_PRIMARY, sub=""):
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
            if sub:
                lbl_sub = QLabel(sub)
                lbl_sub.setStyleSheet(f"color: {Styles.COLOR_TEXT_MUTED}; font-size: 11px; "
                                      f"{Styles.get_transparent_label_style()}")
                t_layout.addWidget(lbl_sub)
            return tile

        layout.addWidget(make_tile("AVG OPPONENT RATING", f"{avg_opp:.0f}" if avg_opp else "—"))
        layout.addWidget(make_tile("HIGHEST-RATED OPPONENT", f"{max_opp}" if max_opp else "—",
                                   Styles.COLOR_ACCENT))
        layout.addWidget(make_tile("BEST WIN", str(best_win), Styles.COLOR_BEST,
                                   "Strongest opponent defeated"))

        layout.addStretch()
        self.set_content(self.content_widget)
