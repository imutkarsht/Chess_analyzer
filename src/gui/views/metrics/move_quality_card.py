import matplotlib
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel, QSizePolicy
from PyQt6.QtCore import Qt
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from src.gui.views.metrics.base_card import MetricCard
from src.gui.styles import Styles
from src.gui.utils.gui_utils import load_icon_pixmap

QUALITY_ICONS = {
    "Good": "good",
    "Inaccuracy": "inaccuracy",
    "Mistake": "mistake",
    "Blunder": "blunder",
    "Miss": "missed_win",
    "Book": "book",
}

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
            "Good": Styles.COLOR_BEST,
            "Inaccuracy": Styles.COLOR_INACCURACY,
            "Mistake": Styles.COLOR_MISTAKE,
            "Blunder": Styles.COLOR_BLUNDER,
            "Miss": Styles.COLOR_MISS,
            "Book": Styles.COLOR_BOOK,
        }
        
        order = ["Good", "Inaccuracy", "Mistake", "Blunder", "Miss", "Book"]
        
        for k in order:
            v = counts.get(k, 0)
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
        
        order = ["Good", "Inaccuracy", "Mistake", "Blunder", "Miss", "Book"]
        total_moves = sum(counts.values())
        
        for k in order:
            v = counts.get(k, 0)
            if v == 0 and total_moves > 0:
                continue 
            
            row = QHBoxLayout()
            row.setSpacing(10)
            
            pixmap = load_icon_pixmap(QUALITY_ICONS.get(k, k.lower()), 24)
            if not pixmap.isNull():
                lbl_icon = QLabel()
                lbl_icon.setPixmap(pixmap)
                lbl_icon.setStyleSheet("border: none; background: transparent;")
                row.addWidget(lbl_icon)
            else:
                dot = QLabel("●")
                dot.setStyleSheet(f"color: {color_map[k]}; font-size: 20px; {Styles.get_transparent_label_style()}")
                row.addWidget(dot)
            
            stats_layout = QVBoxLayout()
            stats_layout.setSpacing(0)
            
            lbl_name = QLabel(k)
            lbl_name.setStyleSheet(f"color: {Styles.COLOR_TEXT_SECONDARY}; font-size: 13px; font-weight: 500; {Styles.get_transparent_label_style()}")
            
            pct = (v / total_moves * 100) if total_moves > 0 else 0
            lbl_val = QLabel(f"{v} ({pct:.0f}%)")
            lbl_val.setStyleSheet(f"color: {color_map[k]}; font-size: 14px; font-weight: bold; {Styles.get_transparent_label_style()}")
            
            stats_layout.addWidget(lbl_name)
            stats_layout.addWidget(lbl_val)
            
            row.addLayout(stats_layout)
            row.addStretch()
            legend_layout.addLayout(row)

        legend_layout.addStretch()
        layout.addWidget(legend_widget, stretch=2)
            
        self.set_content(self.content_widget)
