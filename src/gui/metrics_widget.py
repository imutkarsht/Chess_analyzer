from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QTabWidget, QFrame, QScrollArea)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
import matplotlib
matplotlib.use('QtAgg')
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
from typing import List, Dict, Any
from .styles import Styles

class MetricsWidget(QWidget):
    def __init__(self, games: List[Any]):
        super().__init__()
        self.games = games
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Title
        title = QLabel("Analysis Metrics")
        title.setStyleSheet(f"font-size: 24px; font-weight: bold; color: {Styles.COLOR_TEXT_PRIMARY}; margin-bottom: 10px;")
        layout.addWidget(title)
        
        # Tabs
        tabs = QTabWidget()
        tabs.addTab(self.create_overview_tab(), "Overview")
        tabs.addTab(self.create_quality_tab(), "Move Quality")
        tabs.addTab(self.create_openings_tab(), "Openings")
        layout.addWidget(tabs)

    def create_overview_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Calculate stats
        total_games = len(self.games)
        white_wins = 0
        black_wins = 0
        draws = 0
        total_accuracy = 0
        games_with_acc = 0
        
        for game in self.games:
            res = game.metadata.result
            if res == "1-0": white_wins += 1
            elif res == "0-1": black_wins += 1
            else: draws += 1
            
            # Check summary for accuracy
            # GameAnalysis objects from history might have summary dict
            summary = getattr(game, "summary", {})
            if summary:
                # Average of white and black accuracy
                w_acc = summary.get("white", {}).get("accuracy", 0)
                b_acc = summary.get("black", {}).get("accuracy", 0)
                if w_acc > 0 or b_acc > 0:
                    total_accuracy += (w_acc + b_acc) / 2
                    games_with_acc += 1
        
        avg_accuracy = total_accuracy / games_with_acc if games_with_acc > 0 else 0
        
        # Display Stats
        stats_layout = QHBoxLayout()
        
        self._add_stat_card(stats_layout, "Total Games", str(total_games))
        self._add_stat_card(stats_layout, "Avg Accuracy", f"{avg_accuracy:.1f}%")
        self._add_stat_card(stats_layout, "White Wins", f"{white_wins} ({white_wins/total_games*100:.1f}%)" if total_games else "0")
        self._add_stat_card(stats_layout, "Black Wins", f"{black_wins} ({black_wins/total_games*100:.1f}%)" if total_games else "0")
        self._add_stat_card(stats_layout, "Draws", f"{draws} ({draws/total_games*100:.1f}%)" if total_games else "0")
        
        layout.addLayout(stats_layout)
        layout.addStretch()
        return widget

    def _add_stat_card(self, layout, title, value):
        card = QFrame()
        card.setStyleSheet(f"background-color: {Styles.COLOR_SURFACE}; border-radius: 8px; padding: 15px;")
        card_layout = QVBoxLayout(card)
        
        lbl_title = QLabel(title)
        lbl_title.setStyleSheet(f"color: {Styles.COLOR_TEXT_SECONDARY}; font-size: 14px;")
        card_layout.addWidget(lbl_title)
        
        lbl_value = QLabel(value)
        lbl_value.setStyleSheet(f"color: {Styles.COLOR_TEXT_PRIMARY}; font-size: 24px; font-weight: bold;")
        card_layout.addWidget(lbl_value)
        
        layout.addWidget(card)

    def create_quality_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Aggregate move types
        move_counts = {
            "Brilliant": 0, "Great": 0, "Best": 0, "Excellent": 0, 
            "Good": 0, "Inaccuracy": 0, "Mistake": 0, "Blunder": 0
        }
        
        for game in self.games:
            summary = getattr(game, "summary", {})
            if summary:
                for side in ["white", "black"]:
                    s_data = summary.get(side, {})
                    for key in move_counts:
                        move_counts[key] += s_data.get(key, 0)
                        
        # Filter out zero counts
        labels = []
        sizes = []
        colors = []
        
        color_map = {
            "Brilliant": "#1baca6", "Great": "#5c8bb0", "Best": "#96bc4b", 
            "Excellent": "#96bc4b", "Good": "#96bc4b", "Inaccuracy": "#f0c15c", 
            "Mistake": "#e6912c", "Blunder": "#ca3431"
        }
        
        for key, value in move_counts.items():
            if value > 0:
                labels.append(key)
                sizes.append(value)
                colors.append(color_map.get(key, "#888888"))
        
        if not sizes:
            layout.addWidget(QLabel("No move data available."))
            return widget
            
        # Create Pie Chart
        fig = Figure(figsize=(5, 4), dpi=100, facecolor=Styles.COLOR_BACKGROUND)
        ax = fig.add_subplot(111)
        ax.set_facecolor(Styles.COLOR_BACKGROUND)
        
        wedges, texts, autotexts = ax.pie(sizes, labels=labels, autopct='%1.1f%%', 
                                          startangle=90, colors=colors, textprops=dict(color="white"))
        
        ax.axis('equal')  # Equal aspect ratio ensures that pie is drawn as a circle.
        
        canvas = FigureCanvasQTAgg(fig)
        layout.addWidget(canvas)
        
        return widget

    def create_openings_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Count openings
        openings = {}
        for game in self.games:
            op = game.metadata.opening
            if op and op != "Unknown Opening":
                # Group by main name (split by :, ,, or |)
                main_name = op.split(":")[0].split(",")[0].split("|")[0].strip()
                
                # Further cleanup for common variations
                if " Declined" in main_name:
                    main_name = main_name.replace(" Declined", "")
                if " Accepted" in main_name:
                    main_name = main_name.replace(" Accepted", "")
                    
                openings[main_name] = openings.get(main_name, 0) + 1
                
        # Sort by count
        sorted_openings = sorted(openings.items(), key=lambda x: x[1], reverse=True)[:10] # Top 10
        
        if not sorted_openings:
            layout.addWidget(QLabel("No opening data available."))
            return widget
            
        names = [x[0] for x in sorted_openings]
        counts = [x[1] for x in sorted_openings]
        
        # Create Bar Chart
        fig = Figure(figsize=(8, 5), dpi=100, facecolor=Styles.COLOR_BACKGROUND)
        ax = fig.add_subplot(111)
        ax.set_facecolor(Styles.COLOR_BACKGROUND)
        
        bars = ax.barh(names, counts, color=Styles.COLOR_ACCENT)
        ax.invert_yaxis() # Labels read top-to-bottom
        
        ax.tick_params(axis='x', colors='white')
        ax.tick_params(axis='y', colors='white')
        ax.spines['bottom'].set_color('white')
        ax.spines['top'].set_color('none')
        ax.spines['left'].set_color('white')
        ax.spines['right'].set_color('none')
        
        canvas = FigureCanvasQTAgg(fig)
        layout.addWidget(canvas)
        
        return widget
