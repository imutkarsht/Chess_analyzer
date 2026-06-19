import os
import matplotlib
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel, QSizePolicy
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from src.gui.views.metrics.base_card import MetricCard
from src.gui.styles import Styles
from src.gui.utils.gui_utils import resolve_asset

class MoveQualityCard(MetricCard):
    def __init__(self, parent=None):
        super().__init__("Move Quality Distribution", parent=parent, max_height=310)
        self.content_widget = None

    def set_stats(self, stats):
        if self.content_widget:
            self.card_layout.removeWidget(self.content_widget)
            self.content_widget.deleteLater()

        counts = stats.get('quality_counts', {})
        
        fig = Figure(figsize=(4, 3), dpi=100, facecolor=Styles.COLOR_SURFACE)
        ax = fig.add_subplot(111)
        ax.set_facecolor(Styles.COLOR_SURFACE)
        
        labels = []
        sizes = []
        colors = []
        color_map = {
            "Best": Styles.COLOR_BEST, 
            "Inaccuracy": Styles.COLOR_INACCURACY, 
            "Mistake": Styles.COLOR_MISTAKE, 
            "Blunder": Styles.COLOR_BLUNDER
        }
        
        for k, v in counts.items():
            if v > 0:
                labels.append(k)
                sizes.append(v)
                colors.append(color_map.get(k, '#888'))
                
        if sizes:
            wedges, texts = ax.pie(sizes, labels=None, colors=colors, startangle=90)
            centre_circle = matplotlib.patches.Circle((0,0), 0.70, fc=Styles.COLOR_SURFACE)
            fig.gca().add_artist(centre_circle)
        else:
            ax.text(0, 0, "No moves", ha='center', va='center', color=Styles.COLOR_TEXT_SECONDARY)
            
        canvas = FigureCanvasQTAgg(fig)
        canvas.setStyleSheet("background: transparent;")
        canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        # Container for Chart + Legend
        self.content_widget = QWidget()
        layout = QHBoxLayout(self.content_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(canvas, stretch=3)
        
        # Custom Legend Sidebar
        legend_widget = QWidget()
        legend_layout = QVBoxLayout(legend_widget)
        legend_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        legend_layout.setSpacing(12)
        
        order = ["Best", "Inaccuracy", "Mistake", "Blunder"]
        total_moves = sum(counts.values())
        
        for k in order:
            v = counts.get(k, 0)
            if v == 0 and total_moves > 0:
                continue 
            
            row = QHBoxLayout()
            row.setSpacing(10)
            
            icon_name = k.lower() 
            if icon_name == "best":
                icon_name = "best_v2"
            
            icon_path = resolve_asset(f"{icon_name}.svg")
            if not icon_path:
                icon_path = resolve_asset(f"{icon_name}.png")
            
            if icon_path and os.path.exists(icon_path):
                lbl_icon = QLabel()
                pixmap = QPixmap(icon_path)
                if not pixmap.isNull():
                    pixmap = pixmap.scaled(24, 24, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                    lbl_icon.setPixmap(pixmap)
                    lbl_icon.setStyleSheet("border: none; background: transparent;")
                    row.addWidget(lbl_icon)
                else:
                    dot = QLabel("●") 
                    dot.setStyleSheet(f"color: {color_map[k]}; font-size: 20px; border: none; background: transparent;")
                    row.addWidget(dot) 
            else:
                dot = QLabel("●") 
                dot.setStyleSheet(f"color: {color_map[k]}; font-size: 20px; border: none; background: transparent;")
                row.addWidget(dot)
            
            stats_layout = QVBoxLayout()
            stats_layout.setSpacing(0)
            
            lbl_name = QLabel(k)
            lbl_name.setStyleSheet(f"color: {Styles.COLOR_TEXT_SECONDARY}; font-size: 13px; font-weight: 500; border: none; background: transparent;")
            
            pct = (v / total_moves * 100) if total_moves > 0 else 0
            lbl_val = QLabel(f"{v} ({pct:.0f}%)")
            lbl_val.setStyleSheet(f"color: {color_map[k]}; font-size: 14px; font-weight: bold; border: none; background: transparent;")
            
            stats_layout.addWidget(lbl_name)
            stats_layout.addWidget(lbl_val)
            
            row.addLayout(stats_layout)
            row.addStretch()
            legend_layout.addLayout(row)

        legend_layout.addStretch()
        layout.addWidget(legend_widget, stretch=2)
            
        self.set_content(self.content_widget)
