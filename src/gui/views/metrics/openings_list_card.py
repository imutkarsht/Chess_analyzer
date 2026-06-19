from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QScrollArea, QProgressBar
from PyQt6.QtCore import Qt
from src.gui.views.metrics.base_card import MetricCard
from src.gui.styles import Styles

class OpeningsListCard(MetricCard):
    def __init__(self, parent=None):
        super().__init__("Top Openings", parent=parent, min_height=400)
        self.content_widget = None

    def set_stats(self, stats):
        if self.content_widget:
            self.card_layout.removeWidget(self.content_widget)
            self.content_widget.deleteLater()
            
        openings = stats.get('openings', {})
        opening_wins = stats.get('opening_wins', {})
        sorted_ops = sorted(openings.items(), key=lambda x: x[1], reverse=True)
        
        self.content_widget = QWidget()
        self.content_widget.setMinimumHeight(0)
        layout = QVBoxLayout(self.content_widget)
        layout.setSpacing(8)
        layout.setContentsMargins(5, 5, 5, 5)
        
        header_frame = QFrame()
        header_frame.setStyleSheet(f"background-color: {Styles.COLOR_SURFACE_LIGHT}; border-radius: 4px;")
        header = QHBoxLayout(header_frame)
        header.setContentsMargins(10, 5, 10, 5)
        header.addWidget(QLabel("Opening"), stretch=3)
        header.addWidget(QLabel("Games"), stretch=1)
        header.addWidget(QLabel("Win Rate"), stretch=2)
        layout.addWidget(header_frame)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background: transparent; border: none;")
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setSpacing(4)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        
        for name, count in sorted_ops:
            wins = opening_wins.get(name, 0)
            win_rate = (wins / count * 100) if count > 0 else 0
            
            row_frame = QFrame()
            row_frame.setStyleSheet(f"""
                QFrame {{
                    background-color: transparent;
                    border-radius: 4px;
                }}
                QFrame:hover {{
                    background-color: {Styles.COLOR_SURFACE_LIGHT};
                }}
            """)
            row = QHBoxLayout(row_frame)
            row.setContentsMargins(10, 8, 10, 8)
            
            lbl_name = QLabel(name)
            lbl_name.setStyleSheet(f"color: {Styles.COLOR_TEXT_PRIMARY}; font-weight: 500;")
            row.addWidget(lbl_name, stretch=3)
            
            lbl_count = QLabel(str(count))
            lbl_count.setStyleSheet(f"color: {Styles.COLOR_TEXT_SECONDARY};")
            row.addWidget(lbl_count, stretch=1)
            
            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setValue(int(win_rate))
            bar.setTextVisible(False)
            bar.setFixedHeight(6)
            bar.setStyleSheet(f"""
                QProgressBar {{
                    border: none;
                    background-color: {Styles.COLOR_SURFACE_LIGHT};
                    border-radius: 3px;
                }}
                QProgressBar::chunk {{
                    background-color: {Styles.COLOR_ACCENT};
                    border-radius: 3px;
                }}
            """)
            
            rate_layout = QHBoxLayout()
            rate_layout.setSpacing(8)
            rate_layout.addWidget(bar, stretch=1)
            rate_lbl = QLabel(f"{win_rate:.0f}%")
            rate_lbl.setStyleSheet(f"color: {Styles.COLOR_TEXT_SECONDARY}; font-size: 11px;")
            rate_layout.addWidget(rate_lbl)
            
            row.addLayout(rate_layout, stretch=2)
            scroll_layout.addWidget(row_frame)
            
        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)
        
        if not sorted_ops:
            layout.addWidget(QLabel("No openings data found in loaded games."), alignment=Qt.AlignmentFlag.AlignCenter)
            
        self.set_content(self.content_widget)
