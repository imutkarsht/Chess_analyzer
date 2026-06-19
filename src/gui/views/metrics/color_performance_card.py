from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame
from PyQt6.QtCore import Qt
from src.gui.views.metrics.base_card import MetricCard
from src.gui.styles import Styles

class ColorPerformanceCard(MetricCard):
    def __init__(self, parent=None):
        super().__init__("Performance by Color", parent=parent)
        self.content_widget = None

    def set_stats(self, stats):
        if self.content_widget:
            self.card_layout.removeWidget(self.content_widget)
            self.content_widget.deleteLater()
            
        color_stats = stats.get('color_stats', {'white': {'total': 0, 'wins': 0, 'losses': 0, 'draws': 0},
                                                'black': {'total': 0, 'wins': 0, 'losses': 0, 'draws': 0}})
        
        self.content_widget = QWidget()
        layout = QVBoxLayout(self.content_widget)
        layout.setSpacing(20)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        def create_bar(label, stats_item):
            total = stats_item['total']
            if total == 0:
                wins_pct = draws_pct = losses_pct = 0
            else:
                wins_pct = stats_item['wins'] / total * 100
                draws_pct = stats_item['draws'] / total * 100
                losses_pct = stats_item['losses'] / total * 100
            
            wrapper = QWidget()
            w_layout = QVBoxLayout(wrapper)
            w_layout.setSpacing(6)
            w_layout.setContentsMargins(0, 0, 0, 0)
            
            lbl_row = QHBoxLayout()
            lbl = QLabel(label)
            lbl.setStyleSheet(f"color: {Styles.COLOR_TEXT_PRIMARY}; font-weight: 600; font-size: 14px; border: none; background: transparent;")
            lbl_row.addWidget(lbl)
            lbl_row.addStretch()
            val = QLabel(f"{total} Games")
            val.setStyleSheet(f"color: {Styles.COLOR_TEXT_SECONDARY}; font-size: 12px; border: none; background: transparent;")
            lbl_row.addWidget(val)
            w_layout.addLayout(lbl_row)
            
            bar_container = QFrame()
            bar_container.setFixedHeight(24)
            bar_container.setStyleSheet(f"background-color: {Styles.COLOR_SURFACE_LIGHT}; border-radius: 12px; border: none;")
            bar_layout = QHBoxLayout(bar_container)
            bar_layout.setContentsMargins(0, 0, 0, 0)
            bar_layout.setSpacing(1)
            
            def add_segment(pct, color):
                if pct > 0:
                    seg = QFrame()
                    seg.setStyleSheet(f"background-color: {color}; border: none; border-radius: 0px;")
                    bar_layout.addWidget(seg, stretch=int(pct*10))
            
            add_segment(wins_pct, Styles.COLOR_BEST)
            add_segment(draws_pct, "#888888")
            add_segment(losses_pct, Styles.COLOR_BLUNDER)
            
            if total == 0:
                empty = QFrame()
                empty.setStyleSheet("background: transparent; border: none;")
                bar_layout.addWidget(empty)
                
            w_layout.addWidget(bar_container)
            
            stat_row = QHBoxLayout()
            stat_row.setSpacing(12)
            
            def add_pill(txt, color):
                l = QLabel(txt)
                l.setStyleSheet(f"color: {color}; font-size: 11px; font-weight: 600; border: none; background: transparent;")
                stat_row.addWidget(l)
                
            add_pill(f"{wins_pct:.0f}% W", Styles.COLOR_BEST)
            add_pill(f"{draws_pct:.0f}% D", "#888888")
            add_pill(f"{losses_pct:.0f}% L", Styles.COLOR_BLUNDER)
            stat_row.addStretch()
            
            w_layout.addLayout(stat_row)
            return wrapper

        layout.addWidget(create_bar("White", color_stats['white']))
        layout.addWidget(create_bar("Black", color_stats['black']))
        layout.addStretch()
        
        self.set_content(self.content_widget)
