from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QFrame, QScrollArea, QPushButton, QGridLayout)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
import matplotlib
matplotlib.use('QtAgg')
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
import json
from .styles import Styles
from ..utils.logger import logger

class StatCard(QFrame):
    def __init__(self, title, value, subtitle=None, color=None):
        super().__init__()
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {Styles.COLOR_SURFACE};
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 8px;
                padding: 15px;
            }}
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        
        lbl_title = QLabel(title)
        lbl_title.setStyleSheet(f"color: {Styles.COLOR_TEXT_PRIMARY}; font-size: 14px;")
        layout.addWidget(lbl_title)
        
        lbl_value = QLabel(value)
        lbl_value.setStyleSheet(f"color: {color if color else Styles.COLOR_TEXT_PRIMARY}; font-size: 28px; font-weight: bold;")
        layout.addWidget(lbl_value)
        
        if subtitle:
            lbl_sub = QLabel(subtitle)
            lbl_sub.setStyleSheet(f"color: {Styles.COLOR_TEXT_SECONDARY}; font-size: 12px;")
            layout.addWidget(lbl_sub)

class MetricsWidget(QWidget):
    def __init__(self, config_manager, history_manager):
        super().__init__()
        self.config_manager = config_manager
        self.history_manager = history_manager
        self.usernames = []
        self.games_data = []
        
        self.setup_ui()
        self.refresh()

    def setup_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(20, 20, 20, 20)
        self.main_layout.setSpacing(20)
        
        # Header
        header_layout = QHBoxLayout()
        title = QLabel("Performance Dashboard")
        title.setStyleSheet(f"font-size: 24px; font-weight: bold; color: {Styles.COLOR_TEXT_PRIMARY};")
        header_layout.addWidget(title)
        
        header_layout.addStretch()
        
        self.btn_refresh = QPushButton("Refresh")
        self.btn_refresh.setStyleSheet(Styles.get_control_button_style())
        self.btn_refresh.clicked.connect(self.refresh)
        header_layout.addWidget(self.btn_refresh)
        
        self.main_layout.addLayout(header_layout)
        
        # Content Area (Stacked or cleared)
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.addWidget(self.content_widget)

    def refresh(self, _=None):
        # Clear content
        self._clear_layout(self.content_layout)
        
        # Get usernames
        chesscom = self.config_manager.get("chesscom_username", "")
        lichess = self.config_manager.get("lichess_username", "")
        self.usernames = [u for u in [chesscom, lichess] if u]
        
        if not self.usernames:
            self.show_setup_required()
            return
            
        # Fetch games
        self.games_data = self.history_manager.get_games_for_users(self.usernames)
        
        if not self.games_data:
            self.show_no_data()
            return
            
        self.show_dashboard()

    def show_setup_required(self):
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(20)
        
        lbl = QLabel("Setup Required")
        lbl.setStyleSheet(f"font-size: 24px; font-weight: bold; color: {Styles.COLOR_TEXT_PRIMARY};")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl)
        
        msg = QLabel("Please configure your Chess.com or Lichess.org username in Settings to view your stats.")
        msg.setStyleSheet(f"font-size: 16px; color: {Styles.COLOR_TEXT_SECONDARY};")
        msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(msg)
        
        btn = QPushButton("Go to Settings")
        btn.setStyleSheet(Styles.get_button_style())
        btn.setFixedWidth(200)
        btn.clicked.connect(self.go_to_settings)
        layout.addWidget(btn, alignment=Qt.AlignmentFlag.AlignCenter)
        
        self.content_layout.addWidget(container)

    def show_no_data(self):
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(20)
        
        lbl = QLabel("No Games Found")
        lbl.setStyleSheet(f"font-size: 24px; font-weight: bold; color: {Styles.COLOR_TEXT_PRIMARY};")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl)
        
        msg = QLabel(f"No analyzed games found for users: {', '.join(self.usernames)}.\nAnalyze some games to see your stats!")
        msg.setStyleSheet(f"font-size: 16px; color: {Styles.COLOR_TEXT_SECONDARY};")
        msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(msg)
        
        self.content_layout.addWidget(container)

    def show_dashboard(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        
        dashboard = QWidget()
        dashboard.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(dashboard)
        layout.setSpacing(20)
        
        # 1. Key Metrics Row
        metrics_layout = QHBoxLayout()
        metrics_layout.setSpacing(15)
        
        stats = self._calculate_stats()
        
        metrics_layout.addWidget(StatCard("Total Games", str(stats['total'])))
        metrics_layout.addWidget(StatCard("Win Rate", f"{stats['win_rate']:.1f}%", f"{stats['wins']} Wins", Styles.COLOR_ACCENT))
        metrics_layout.addWidget(StatCard("Avg Accuracy", f"{stats['avg_accuracy']:.1f}%", "Across all games"))
        metrics_layout.addWidget(StatCard("Best Win", stats['best_win'], "Highest rated opponent"))
        
        layout.addLayout(metrics_layout)
        
        # 2. Charts Row
        charts_layout = QHBoxLayout()
        charts_layout.setSpacing(15)
        
        # Win/Loss Pie
        pie_card = QFrame()
        pie_card.setStyleSheet(f"background-color: {Styles.COLOR_SURFACE}; border-radius: 8px; padding: 10px; border: 1px solid {Styles.COLOR_BORDER};")
        pie_layout = QVBoxLayout(pie_card)
        pie_layout.addWidget(QLabel("Game Results"))
        pie_layout.addWidget(self._create_result_pie(stats))
        charts_layout.addWidget(pie_card)
        
        # Accuracy Trend
        trend_card = QFrame()
        trend_card.setStyleSheet(f"background-color: {Styles.COLOR_SURFACE}; border-radius: 8px; padding: 10px; border: 1px solid {Styles.COLOR_BORDER};")
        trend_layout = QVBoxLayout(trend_card)
        trend_layout.addWidget(QLabel("Accuracy Trend (Last 20 Games)"))
        trend_layout.addWidget(self._create_accuracy_chart())
        charts_layout.addWidget(trend_card, stretch=1)
        
        layout.addLayout(charts_layout)
        
        # 3. Insights Row
        insights_layout = QHBoxLayout()
        insights_layout.setSpacing(15)
        
        # Top Openings
        opening_card = QFrame()
        opening_card.setStyleSheet(f"background-color: {Styles.COLOR_SURFACE}; border-radius: 8px; padding: 10px; border: 1px solid {Styles.COLOR_BORDER};")
        op_layout = QVBoxLayout(opening_card)
        op_layout.addWidget(QLabel("Top Openings"))
        op_layout.addWidget(self._create_openings_chart())
        insights_layout.addWidget(opening_card)
        
        # Move Quality
        quality_card = QFrame()
        quality_card.setStyleSheet(f"background-color: {Styles.COLOR_SURFACE}; border-radius: 8px; padding: 10px; border: 1px solid {Styles.COLOR_BORDER};")
        q_layout = QVBoxLayout(quality_card)
        q_layout.addWidget(QLabel("Move Quality Distribution"))
        q_layout.addWidget(self._create_quality_chart())
        insights_layout.addWidget(quality_card)
        
        layout.addLayout(insights_layout)
        
        scroll.setWidget(dashboard)
        self.content_layout.addWidget(scroll)

    def _calculate_stats(self):
        total = len(self.games_data)
        wins = 0
        draws = 0
        losses = 0
        total_acc = 0
        acc_count = 0
        best_win_rating = 0
        
        for game in self.games_data:
            # Determine user's color
            white = game['white'].lower()
            black = game['black'].lower()
            user_color = None
            
            if white in [u.lower() for u in self.usernames]:
                user_color = 'white'
            elif black in [u.lower() for u in self.usernames]:
                user_color = 'black'
                
            if not user_color:
                continue
                
            # Result
            res = game['result']
            if res == '1-0':
                if user_color == 'white': wins += 1
                else: losses += 1
            elif res == '0-1':
                if user_color == 'black': wins += 1
                else: losses += 1
            else:
                draws += 1
                
            # Accuracy
            if game['summary_json']:
                try:
                    summary = json.loads(game['summary_json'])
                    acc = summary.get(user_color, {}).get('accuracy', 0)
                    if acc > 0:
                        total_acc += acc
                        acc_count += 1
                except:
                    pass
            
        return {
            'total': total,
            'wins': wins,
            'losses': losses,
            'draws': draws,
            'win_rate': (wins / total * 100) if total else 0,
            'avg_accuracy': (total_acc / acc_count) if acc_count else 0,
            'best_win': "N/A" # Placeholder
        }

    def _create_result_pie(self, stats):
        fig = Figure(figsize=(3, 3), dpi=100, facecolor=Styles.COLOR_SURFACE)
        ax = fig.add_subplot(111)
        ax.set_facecolor(Styles.COLOR_SURFACE)
        
        labels = ['Wins', 'Losses', 'Draws']
        sizes = [stats['wins'], stats['losses'], stats['draws']]
        colors = [Styles.COLOR_ACCENT, '#ca3431', '#888888']
        
        # Filter zeros
        final_labels = []
        final_sizes = []
        final_colors = []
        for i, size in enumerate(sizes):
            if size > 0:
                final_labels.append(labels[i])
                final_sizes.append(size)
                final_colors.append(colors[i])
        
        if final_sizes:
            wedges, texts, autotexts = ax.pie(final_sizes, labels=final_labels, autopct='%1.1f%%', 
                                              startangle=90, colors=final_colors, 
                                              textprops=dict(color=Styles.COLOR_TEXT_PRIMARY))
        
        canvas = FigureCanvasQTAgg(fig)
        canvas.setStyleSheet("background: transparent;")
        return canvas

    def _create_accuracy_chart(self):
        fig = Figure(figsize=(5, 3), dpi=100, facecolor=Styles.COLOR_SURFACE)
        ax = fig.add_subplot(111)
        ax.set_facecolor(Styles.COLOR_SURFACE)
        
        # Get last 20 accuracies
        accuracies = []
        for game in self.games_data[:20][::-1]: # Reverse to show chronological
            try:
                if game['summary_json']:
                    summary = json.loads(game['summary_json'])
                    # Determine color again... simplified
                    white = game['white'].lower()
                    user_color = 'white' if white in [u.lower() for u in self.usernames] else 'black'
                    acc = summary.get(user_color, {}).get('accuracy', 0)
                    if acc > 0:
                        accuracies.append(acc)
            except:
                pass
                
        if accuracies:
            ax.plot(accuracies, color=Styles.COLOR_ACCENT, marker='o')
            ax.set_ylim(0, 100)
            ax.grid(True, color='#444', linestyle='--', alpha=0.5)
            
        ax.tick_params(colors=Styles.COLOR_TEXT_SECONDARY)
        for spine in ax.spines.values():
            spine.set_color(Styles.COLOR_BORDER)
            
        canvas = FigureCanvasQTAgg(fig)
        return canvas

    def _create_openings_chart(self):
        # Similar to before but using self.games_data
        openings = {}
        for game in self.games_data:
            pgn = game['pgn']
            if 'Opening "' in pgn:
                import re
                match = re.search(r'\[Opening "([^"]+)"\]', pgn)
                if match:
                    op = match.group(1)
                    main_name = op.split(":")[0].split(",")[0].strip()
                    openings[main_name] = openings.get(main_name, 0) + 1
                    
        sorted_ops = sorted(openings.items(), key=lambda x: x[1], reverse=True)[:5]
        
        fig = Figure(figsize=(5, 4), dpi=100, facecolor=Styles.COLOR_SURFACE)
        ax = fig.add_subplot(111)
        ax.set_facecolor(Styles.COLOR_SURFACE)
        
        if sorted_ops:
            names = [x[0] for x in sorted_ops]
            counts = [x[1] for x in sorted_ops]
            y_pos = range(len(names))
            ax.barh(y_pos, counts, color=Styles.COLOR_ACCENT)
            ax.set_yticks(y_pos)
            ax.set_yticklabels(names)
            ax.invert_yaxis()
            
        ax.tick_params(colors=Styles.COLOR_TEXT_SECONDARY)
        for spine in ax.spines.values():
            spine.set_visible(False)
            
        fig.tight_layout()
        canvas = FigureCanvasQTAgg(fig)
        return canvas

    def _create_quality_chart(self):
        # Aggregate move qualities
        counts = {"Brilliant": 0, "Great": 0, "Best": 0, "Mistake": 0, "Blunder": 0}
        
        for game in self.games_data:
            try:
                if game['summary_json']:
                    summary = json.loads(game['summary_json'])
                    white = game['white'].lower()
                    user_color = 'white' if white in [u.lower() for u in self.usernames] else 'black'
                    
                    s_data = summary.get(user_color, {})
                    for key in counts:
                        counts[key] += s_data.get(key, 0)
            except:
                pass
                
        fig = Figure(figsize=(4, 3), dpi=100, facecolor=Styles.COLOR_SURFACE)
        ax = fig.add_subplot(111)
        ax.set_facecolor(Styles.COLOR_SURFACE)
        
        labels = []
        sizes = []
        colors = []
        color_map = {"Brilliant": "#1baca6", "Great": "#5c8bb0", "Best": "#96bc4b", "Mistake": "#e6912c", "Blunder": "#ca3431"}
        
        for k, v in counts.items():
            if v > 0:
                labels.append(k)
                sizes.append(v)
                colors.append(color_map.get(k, '#888'))
                
        if sizes:
            ax.pie(sizes, labels=labels, autopct='%1.1f%%', colors=colors, textprops=dict(color=Styles.COLOR_TEXT_SECONDARY))
            
        canvas = FigureCanvasQTAgg(fig)
        return canvas

    def _clear_layout(self, layout):
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def go_to_settings(self):
        # Find main window and switch tab
        window = self.window()
        if hasattr(window, "sidebar"):
            window.sidebar.set_active(2) # Settings index
        if hasattr(window, "stack"):
            window.stack.setCurrentIndex(2)
