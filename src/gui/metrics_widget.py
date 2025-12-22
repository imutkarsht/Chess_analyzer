import os
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QFrame, QScrollArea, QPushButton, QGridLayout, QProgressBar, QSizePolicy)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QPixmap, QIcon
import matplotlib
matplotlib.use('QtAgg')
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
import json
from .styles import Styles
from .gui_utils import clear_layout, resolve_asset, get_user_color  # Use shared utilities
from ..utils.logger import logger
from ..backend.gemini_service import GeminiService
import re

class InsightWorker(QThread):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, service, stats_text):
        super().__init__()
        self.service = service
        self.stats_text = stats_text

    def run(self):
        try:
            insight = self.service.generate_coach_insights(self.stats_text)
            self.finished.emit(insight)
        except Exception as e:
            self.error.emit(str(e))

class StatsWorker(QThread):
    finished = pyqtSignal(dict)
    
    def __init__(self, games, usernames):
        super().__init__()
        self.games = games
        self.usernames = usernames
        
    def run(self):
        try:
            stats = self._calculate_stats()
            self.finished.emit(stats)
        except Exception as e:
            # Handle empty stats or error
            self.finished.emit({})
        
    def _get_user_color(self, game):
        white = game['white'].lower()
        if white in [u.lower() for u in self.usernames]:
            return 'white'
        return 'black'

    def _calculate_stats(self):
        total = len(self.games)
        wins = 0
        draws = 0
        losses = 0
        total_acc = 0
        acc_count = 0
        best_win_rating = 0
        
        term_counts = {"Checkmate": 0, "Resignation": 0, "Time": 0, "Abandon": 0, "Draw": 0}
        quality_counts = {"Best": 0, "Inaccuracy": 0, "Mistake": 0, "Blunder": 0}
        accuracy_history = []
        openings = {}
        opening_wins = {}
        
        # New: Color Stats
        color_stats = {
            'white': {'wins': 0, 'draws': 0, 'losses': 0, 'total': 0},
            'black': {'wins': 0, 'draws': 0, 'losses': 0, 'total': 0}
        }

        for game in self.games:
            user_color = self._get_user_color(game)
            if not user_color: continue
            
            res = game['result']
            
            # Update Color Totals
            color_stats[user_color]['total'] += 1
            
            # 1. Result
            if res == '1-0':
                if user_color == 'white': 
                    wins += 1
                    color_stats['white']['wins'] += 1
                else: 
                    losses += 1
                    color_stats['black']['losses'] += 1
            elif res == '0-1':
                if user_color == 'black': 
                    wins += 1
                    color_stats['black']['wins'] += 1
                else: 
                    losses += 1
                    color_stats['white']['losses'] += 1
            else:
                draws += 1
                color_stats[user_color]['draws'] += 1
                
            # 2. Termination
            term = (game.get("termination") or "").lower()
            if res == "1/2-1/2":
                term_counts["Draw"] += 1
            elif "time" in term:
                term_counts["Time"] += 1
            elif "resign" in term:
                term_counts["Resignation"] += 1
            elif "abandon" in term:
                term_counts["Abandon"] += 1
            elif "mate" in term:
                term_counts["Checkmate"] += 1
            else:
                pgn = game.get("pgn", "")
                if "#" in pgn: term_counts["Checkmate"] += 1
                else: term_counts["Resignation"] += 1

            # 3. Accuracy / Quality
            game_acc = 0
            if game.get('summary_json'):
                try:
                    summary = json.loads(game['summary_json'])
                    s_data = summary.get(user_color, {})
                    
                    acc = s_data.get('accuracy', 0)
                    if acc > 0:
                        total_acc += acc
                        acc_count += 1
                        game_acc = acc
                        
                    quality_counts["Best"] += s_data.get("Best", 0) + s_data.get("Brilliant", 0) + s_data.get("Great", 0)
                    quality_counts["Inaccuracy"] += s_data.get("Inaccuracy", 0)
                    quality_counts["Mistake"] += s_data.get("Mistake", 0)
                    quality_counts["Blunder"] += s_data.get("Blunder", 0)
                except:
                    pass
            
            if game_acc > 0:
                accuracy_history.append(game_acc)
            
            # 4. Best Win
            is_win = False
            opponent_elo = 0
            if (res == '1-0' and user_color == 'white') or (res == '0-1' and user_color == 'black'):
                is_win = True
                opp_key = 'black_elo' if user_color == 'white' else 'white_elo'
                try: opponent_elo = int(game.get(opp_key, 0))
                except: opponent_elo = 0
            if is_win and opponent_elo > best_win_rating:
                best_win_rating = opponent_elo
                
            # 5. Openings
            op_name = game.get("opening")
            if not op_name:
                pgn = game.get('pgn', "")
                if 'Opening "' in pgn:
                    match = re.search(r'\[Opening "([^"]+)"\]', pgn)
                    if match: op_name = match.group(1)
            
            if op_name:
                main_name = op_name.split(":")[0].split(",")[0].strip()
                openings[main_name] = openings.get(main_name, 0) + 1
                if is_win:
                    opening_wins[main_name] = opening_wins.get(main_name, 0) + 1

        return {
            'total': total,
            'wins': wins,
            'losses': losses,
            'draws': draws,
            'win_rate': (wins / total * 100) if total else 0,
            'avg_accuracy': (total_acc / acc_count) if acc_count else 0,
            'best_win': str(best_win_rating) if best_win_rating > 0 else "N/A",
            'term_counts': term_counts,
            'quality_counts': quality_counts,
            'accuracy_history': accuracy_history,
            'openings': openings,
            'opening_wins': opening_wins,
            'color_stats': color_stats
        }

class StatCard(QFrame):
    def __init__(self, title, value, subtitle=None, icon=None, color=None):
        super().__init__()
        # Distinct border/bg for a cleaner "dashboard" look
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {Styles.COLOR_SURFACE};
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 12px;
            }}
            QFrame:hover {{
                border: 1px solid {Styles.COLOR_ACCENT};
                background-color: {Styles.COLOR_SURFACE_LIGHT};
            }}
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)
        
        # Header (Title + Icon)
        header_layout = QHBoxLayout()
        
        lbl_title = QLabel(title)
        lbl_title.setStyleSheet(f"color: {Styles.COLOR_TEXT_SECONDARY}; font-size: 14px; font-weight: 600; border: none; background: transparent;")
        header_layout.addWidget(lbl_title)
        
        if icon:
            # Use module-level helper
            # Check SVG first if name doesn't specify ext
            if not icon.endswith(('.png', '.svg')):
                # Try both
                icon_path = resolve_asset(f"{icon}.svg")
                if not icon_path:
                    icon_path = resolve_asset(f"{icon}.png")
            else:
                icon_path = resolve_asset(icon)
            
            if icon_path and os.path.exists(icon_path):
                lbl_icon = QLabel()
                pixmap = QPixmap(icon_path)
                if not pixmap.isNull():
                    # Increased icon size for better visibility
                    pixmap = pixmap.scaled(48, 48, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                    lbl_icon.setPixmap(pixmap)
                    lbl_icon.setStyleSheet("border: none; background: transparent;")
                    header_layout.addStretch()
                    header_layout.addWidget(lbl_icon)
                else:
                     # Fallback text
                    lbl = QLabel(icon)
                    lbl.setStyleSheet(f"color: {Styles.COLOR_ACCENT}; font-size: 16px; border: none; background: transparent;")
                    header_layout.addStretch()
                    header_layout.addWidget(lbl)
            else:
                lbl_icon = QLabel(icon) # Fallback
                lbl_icon.setStyleSheet(f"color: {Styles.COLOR_ACCENT}; font-size: 16px; border: none; background: transparent;")
                header_layout.addStretch()
                header_layout.addWidget(lbl_icon)
        else:
            header_layout.addStretch()
            
        layout.addLayout(header_layout)
        
        # Value
        lbl_value = QLabel(value)
        value_color = color if color else Styles.COLOR_TEXT_PRIMARY
        # Larger font for impact
        lbl_value.setStyleSheet(f"color: {value_color}; font-size: 36px; font-weight: bold; border: none; background: transparent;")
        layout.addWidget(lbl_value)
        
        # Subtitle
        if subtitle:
            lbl_sub = QLabel(subtitle)
            # Slightly lighter text
            lbl_sub.setStyleSheet(f"color: {Styles.COLOR_TEXT_SECONDARY}; font-size: 12px; border: none; background: transparent;")
            lbl_sub.setWordWrap(True)
            layout.addWidget(lbl_sub)


class MetricsWidget(QWidget):
    def __init__(self, config_manager, history_manager):
        super().__init__()
        self.config_manager = config_manager
        self.history_manager = history_manager
        self.usernames = []
        self.games_data = []
        self.gemini_service = GeminiService(config_manager.get("gemini_api_key")) # Try config, fallback to env in service
        
        self.setup_ui()
        self.refresh()

    def _get_user_color(self, game):
        """Returns 'white' or 'black' based on which player matches configured usernames."""
        white = game['white'].lower()
        if white in [u.lower() for u in self.usernames]:
            return 'white'
        return 'black'

    def _create_icon_label(self, icon_name, size=24, fallback_color=None):
        """Creates a QLabel with icon, with fallback to colored dot."""
        # Try SVG first, then PNG
        icon_path = resolve_asset(f"{icon_name}.svg")
        if not icon_path:
            icon_path = resolve_asset(f"{icon_name}.png")
        
        lbl = QLabel()
        if icon_path and os.path.exists(icon_path):
            pixmap = QPixmap(icon_path)
            if not pixmap.isNull():
                pixmap = pixmap.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                lbl.setPixmap(pixmap)
                lbl.setStyleSheet("border: none; background: transparent;")
                return lbl
        # Fallback to colored dot
        lbl.setText("●")
        color = fallback_color or Styles.COLOR_ACCENT
        lbl.setStyleSheet(f"color: {color}; font-size: {size}px; border: none; background: transparent;")
        return lbl

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
        
        # Content Area
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.addWidget(self.content_widget)

    def refresh(self, _=None):
        clear_layout(self.content_layout)
        
        chesscom = self.config_manager.get("chesscom_username", "")
        lichess = self.config_manager.get("lichess_username", "")
        self.usernames = [u for u in [chesscom, lichess] if u]
        
        if not self.usernames:
            self.show_setup_required()
            return
            
        self.games_data = self.history_manager.get_games_for_users(self.usernames)
        
        if not self.games_data:
            self.show_no_data()
            return
            
        # Show Loading
        loading_widget = QWidget()
        l_layout = QVBoxLayout(loading_widget)
        l_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        spinner = QProgressBar()
        spinner.setRange(0, 0) # Infinite loading
        spinner.setFixedWidth(200)
        spinner.setStyleSheet(f"""
            QProgressBar {{
                border: 2px solid {Styles.COLOR_BORDER};
                border-radius: 5px;
                background-color: {Styles.COLOR_SURFACE};
            }}
            QProgressBar::chunk {{
                background-color: {Styles.COLOR_ACCENT};
            }}
        """)
        l_layout.addWidget(spinner)
        
        lbl = QLabel("Calculating Statistics...")
        lbl.setStyleSheet(f"color: {Styles.COLOR_TEXT_PRIMARY}; font-size: 16px; margin-top: 10px;")
        l_layout.addWidget(lbl)
        
        self.content_layout.addWidget(loading_widget)
        
        # Start Worker
        self.stats_worker = StatsWorker(self.games_data, self.usernames)
        self.stats_worker.finished.connect(self.on_stats_ready)
        self.stats_worker.start()

    def on_stats_ready(self, stats):
        clear_layout(self.content_layout)
        self.show_dashboard(stats)

    def show_setup_required(self):
        self._show_message_view("Setup Required", 
            "Please configure your Chess.com or Lichess.org username in Settings to view your stats.",
            "Go to Settings", self.go_to_settings)

    def show_no_data(self):
        self._show_message_view("No Games Found",
            f"No analyzed games found for users: {', '.join(self.usernames)}.\nAnalyze some games to see your stats!",
            None, None)

    def _show_message_view(self, title_text, msg_text, btn_text, btn_callback):
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(20)
        
        lbl = QLabel(title_text)
        lbl.setStyleSheet(f"font-size: 24px; font-weight: bold; color: {Styles.COLOR_TEXT_PRIMARY};")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl)
        
        msg = QLabel(msg_text)
        msg.setStyleSheet(f"font-size: 16px; color: {Styles.COLOR_TEXT_SECONDARY};")
        msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(msg)
        
        if btn_text and btn_callback:
            btn = QPushButton(btn_text)
            btn.setStyleSheet(Styles.get_button_style())
            btn.setFixedWidth(200)
            btn.clicked.connect(btn_callback)
            layout.addWidget(btn, alignment=Qt.AlignmentFlag.AlignCenter)
        
        self.content_layout.addWidget(container)

    def _fig_to_label(self, fig):
        """Converts a matplotlib figure to a QPixmap and returns a QLabel."""
        canvas = FigureCanvasQTAgg(fig)
        canvas.draw()
        
        # Render to pixmap
        width, height = int(fig.get_figwidth() * fig.get_dpi()), int(fig.get_figheight() * fig.get_dpi())
        pixmap = QPixmap(width, height)
        pixmap.fill(Qt.GlobalColor.transparent)
        
        painter = pyqtSignal = None # Wait, don't need imports here
        from PyQt6.QtGui import QPainter
        
        painter = QPainter(pixmap)
                
        buf = canvas.buffer_rgba()
        from PyQt6.QtGui import QImage
        qimg = QImage(buf, width, height, QImage.Format.Format_ARGB32)
        
        pixmap = QPixmap.fromImage(qimg)
        
        lbl = QLabel()
        lbl.setPixmap(pixmap)
        lbl.setStyleSheet("background: transparent; border: none;")
        return lbl

    def show_dashboard(self, stats):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        
        dashboard = QWidget()
        dashboard.setStyleSheet("background: transparent;")
        
        # USE GRID LAYOUT
        layout = QGridLayout(dashboard)
        layout.setSpacing(20)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # 1. Key Metrics Row (Row 0)
        # Stats are passed in
        
        layout.addWidget(StatCard("Total Games", str(stats['total']), "Tracked this week", icon="games"), 0, 0)
        layout.addWidget(StatCard("Win Rate", f"{stats['win_rate']:.1f}%", f"Vs last {stats['total']} games", icon="win_rate", color=Styles.COLOR_ACCENT), 0, 1)
        layout.addWidget(StatCard("Avg Accuracy", f"{stats['avg_accuracy']:.1f}%", "Based on engine eval.", icon="accuracy"), 0, 2)
        layout.addWidget(StatCard("Best Win", str(stats['best_win']), "Keep playing!", icon="best_win"), 0, 3)
        
        # 2. Charts Row (Row 1)
        # Result Distribution
        layout.addWidget(self._create_card("Result Distribution", self._create_result_donut(stats), 1), 1, 0)
        # Ending Distribution
        layout.addWidget(self._create_card("Ending Distribution", self._create_termination_donut(stats['term_counts']), 1), 1, 1)
        # Move Quality
        layout.addWidget(self._create_card("Move Quality Distribution", self._create_quality_donut(stats['quality_counts']), 1), 1, 2, 1, 2) # Span 2 cols
        
        # 3. Trends & Openings (Row 2)
        # Accuracy Trend - Split Width (2 cols)
        layout.addWidget(self._create_card("Accuracy Trend", self._create_accuracy_chart(stats['accuracy_history']), 2), 2, 0, 1, 2)
        
        # Color Performance - Split Width (2 cols)
        layout.addWidget(self._create_card("Performance by Color", self._create_color_chart(stats['color_stats']), 1), 2, 2, 1, 2)
        
        # 4. Bottom Row (Row 3)
        # Top Openings
        layout.addWidget(self._create_card("Top Openings", self._create_openings_list(stats['openings'], stats['opening_wins']), 1), 3, 0, 1, 2)
        
        # Insights
        btn_refresh_insights = QPushButton("↻")
        btn_refresh_insights.setFixedSize(32, 32)
        btn_refresh_insights.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_refresh_insights.setToolTip("Refresh AI Insights")
        btn_refresh_insights.setStyleSheet(f"""
            QPushButton {{
                background-color: {Styles.COLOR_ACCENT};
                color: {Styles.COLOR_TEXT_PRIMARY};
                border-radius: 16px;
                border: none;
                font-size: 18px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {Styles.COLOR_ACCENT_HOVER};
            }}
        """)
        btn_refresh_insights.clicked.connect(lambda: self._generate_insights(stats))
        
        layout.addWidget(self._create_card("AI Coach Insights", self._create_insights_panel(), 1, action_widget=btn_refresh_insights), 3, 2, 1, 2) 
        
        # Row stretches
        layout.setRowStretch(4, 1) # Push up
        
        scroll.setWidget(dashboard)
        self.content_layout.addWidget(scroll)

    def _create_card(self, title, widget, stretch=0, action_widget=None):
        # Professional Dashboard Card
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {Styles.COLOR_SURFACE};
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 12px;
            }}
            QFrame:hover {{
                border: 1px solid {Styles.COLOR_ACCENT};
            }}
        """)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        if title:
            header_layout = QHBoxLayout()
            lbl = QLabel(title)
            # Distinct title style matching StatCard
            lbl.setStyleSheet(f"color: {Styles.COLOR_TEXT_SECONDARY}; font-size: 14px; font-weight: 600; border: none; background: transparent;")
            header_layout.addWidget(lbl)
            
            header_layout.addStretch()
            
            if action_widget:
                header_layout.addWidget(action_widget)
                
            layout.addLayout(header_layout)
            
        layout.addWidget(widget)
        return card



    def _create_result_donut(self, stats):
        fig = Figure(figsize=(3, 3), dpi=100, facecolor=Styles.COLOR_SURFACE)
        ax = fig.add_subplot(111)
        ax.set_facecolor(Styles.COLOR_SURFACE)
        
        labels = ['Wins', 'Losses', 'Draws']
        sizes = [stats['wins'], stats['losses'], stats['draws']]
        colors = [Styles.COLOR_ACCENT, '#ca3431', '#888888']
        
        # Filter zeros
        final_sizes = []
        final_colors = []
        for i, size in enumerate(sizes):
            if size > 0:
                final_sizes.append(size)
                final_colors.append(colors[i])
        
        if final_sizes:
            wedges, texts, autotexts = ax.pie(final_sizes, labels=None, autopct='%1.0f%%', 
                                              startangle=90, colors=final_colors, pctdistance=0.85,
                                              textprops=dict(color=Styles.COLOR_TEXT_PRIMARY))
            
            # Draw circle for donut
            centre_circle = matplotlib.patches.Circle((0,0),0.70,fc=Styles.COLOR_SURFACE)
            fig.gca().add_artist(centre_circle)
            
            # Add text in center
            ax.text(0, 0, f"{stats['win_rate']:.0f}%", ha='center', va='center', fontsize=12, color=Styles.COLOR_TEXT_PRIMARY, weight='bold')
            
        else:
             ax.text(0, 0, "No Data", ha='center', va='center', color=Styles.COLOR_TEXT_SECONDARY)

        canvas = FigureCanvasQTAgg(fig)
        canvas.setStyleSheet("background: transparent;")
        return canvas

    def _create_termination_donut(self, counts):
        # Counts passed in dictionary
        # {"Checkmate": 0, "Resignation": 0, "Time": 0, "Abandon": 0, "Draw": 0} 

        fig = Figure(figsize=(3, 3), dpi=100, facecolor=Styles.COLOR_SURFACE)
        ax = fig.add_subplot(111)
        ax.set_facecolor(Styles.COLOR_SURFACE)
        
        labels = []
        sizes = []
        colors = []
        
        # Define colors for ending types
        type_colors = {
            "Checkmate": Styles.COLOR_BEST,    # Greenish
            "Resignation": Styles.COLOR_ACCENT, # Blue
            "Time": "#e67e22",                 # Orange
            "Abandon": Styles.COLOR_BLUNDER,    # Red
            "Draw": "#888888"                  # Grey
        }
        
        # Order: Mate, Resign, Time, Abandon, Draw
        for k in ["Checkmate", "Resignation", "Time", "Abandon", "Draw"]:
            v = counts.get(k, 0)
            if v > 0:
                labels.append(k)
                sizes.append(v)
                colors.append(type_colors.get(k, '#888'))
        
        if sizes:
            wedges, texts, autotexts = ax.pie(sizes, labels=None, autopct='%1.0f%%', 
                                              startangle=90, colors=colors, pctdistance=0.85,
                                              textprops=dict(color=Styles.COLOR_TEXT_PRIMARY))
            
            # Donut hole
            centre_circle = matplotlib.patches.Circle((0,0),0.70,fc=Styles.COLOR_SURFACE)
            fig.gca().add_artist(centre_circle)
            
            # Center Text (Total Won/Decisive?)
            total = sum(sizes)
            ax.text(0, 0, str(total), ha='center', va='center', fontsize=12, color=Styles.COLOR_TEXT_PRIMARY, weight='bold')
            
        else:
             ax.text(0, 0, "No Data", ha='center', va='center', color=Styles.COLOR_TEXT_SECONDARY)

        canvas = FigureCanvasQTAgg(fig)
        canvas.setStyleSheet("background: transparent;")
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Canvas
        layout.addWidget(canvas, stretch=3)
        
        # Legend
        legend_widget = QWidget()
        legend_layout = QVBoxLayout(legend_widget)
        legend_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        legend_layout.setSpacing(8)
        
        for i, label in enumerate(labels):
            row = QHBoxLayout()
            row.setSpacing(8)
            
            # Dot
            dot = QLabel("●")
            dot.setStyleSheet(f"color: {colors[i]}; font-size: 16px; border: none; background: transparent;")
            row.addWidget(dot)
            
            # Label
            lbl_name = QLabel(label)
            lbl_name.setStyleSheet(f"color: {Styles.COLOR_TEXT_SECONDARY}; font-size: 12px; border: none; background: transparent;")
            row.addWidget(lbl_name)
            
            # Value
            lbl_val = QLabel(str(sizes[i]))
            lbl_val.setStyleSheet(f"color: {Styles.COLOR_TEXT_PRIMARY}; font-weight: bold; font-size: 12px; border: none; background: transparent;")
            row.addWidget(lbl_val)
            
            row.addStretch()
            legend_layout.addLayout(row)
            
        layout.addWidget(legend_widget, stretch=2)
        
        return container

    def _create_accuracy_chart(self, full_history):
        fig = Figure(figsize=(5, 3), dpi=100, facecolor=Styles.COLOR_SURFACE)
        ax = fig.add_subplot(111)
        ax.set_facecolor(Styles.COLOR_SURFACE)
        
        accuracies = full_history[:20][::-1] if full_history else []
                
        if accuracies:
            # Smooth curve? Matplotlib default plot is fine, just style it better
            x = range(len(accuracies))
            ax.plot(x, accuracies, color=Styles.COLOR_ACCENT, marker='o', linewidth=2, markersize=6)
            
            # Fill under area
            ax.fill_between(x, accuracies, alpha=0.1, color=Styles.COLOR_ACCENT)
            
            ax.set_ylim(0, 100)
            ax.grid(True, color='#444', linestyle=':', alpha=0.3)
            
            # Remove spines
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            ax.spines['left'].set_visible(False)
            ax.spines['bottom'].set_visible(False)
            
        ax.tick_params(colors=Styles.COLOR_TEXT_SECONDARY, which='both', length=0)
            
        canvas = FigureCanvasQTAgg(fig)
        return canvas

    def _create_color_chart(self, color_stats):
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(15)
        layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        
        # Helper to create a single color bar
        def create_bar(label, stats):
            total = stats['total']
            if total == 0:
                wins_pct = draws_pct = losses_pct = 0
            else:
                wins_pct = stats['wins'] / total * 100
                draws_pct = stats['draws'] / total * 100
                losses_pct = stats['losses'] / total * 100
            
            wrapper = QWidget()
            w_layout = QVBoxLayout(wrapper)
            w_layout.setSpacing(5)
            w_layout.setContentsMargins(0,0,0,0)
            
            # Label Row
            lbl_row = QHBoxLayout()
            lbl = QLabel(label)
            lbl.setStyleSheet(f"color: {Styles.COLOR_TEXT_PRIMARY}; font-weight: bold; font-size: 13px;")
            lbl_row.addWidget(lbl)
            lbl_row.addStretch()
            val = QLabel(f"{total} Games")
            val.setStyleSheet(f"color: {Styles.COLOR_TEXT_SECONDARY}; font-size: 11px;")
            lbl_row.addWidget(val)
            w_layout.addLayout(lbl_row)
            
            # Bar Container
            bar_container = QFrame()
            bar_container.setFixedHeight(20)
            bar_container.setStyleSheet(f"background-color: {Styles.COLOR_SURFACE_LIGHT}; border-radius: 10px;")
            bar_layout = QHBoxLayout(bar_container)
            bar_layout.setContentsMargins(0, 0, 0, 0)
            bar_layout.setSpacing(0)
            
            # Segments
            def add_segment(pct, color, tooltip):
                if pct > 0:
                    seg = QFrame()
                    seg.setStyleSheet(f"background-color: {color}; border-right: 1px solid {Styles.COLOR_SURFACE};")
                    # seg.setToolTip(tooltip) # Tooltip
                    # Using Fixed size policy relative to parent? No, use stretch
                    bar_layout.addWidget(seg, stretch=int(pct*10))
            
            add_segment(wins_pct, Styles.COLOR_BEST, f"Wins: {stats['wins']}")
            add_segment(draws_pct, "#888888", f"Draws: {stats['draws']}")
            add_segment(losses_pct, Styles.COLOR_BLUNDER, f"Losses: {stats['losses']}")
            
            if total == 0:
                empty = QFrame()
                empty.setStyleSheet("background: transparent;")
                bar_layout.addWidget(empty)
                
            w_layout.addWidget(bar_container)
            
            # Stats Row beneath
            stat_row = QHBoxLayout()
            stat_row.setSpacing(10)
            
            def add_pill(txt, color):
                l = QLabel(txt)
                l.setStyleSheet(f"color: {color}; font-size: 10px; font-weight: bold;")
                stat_row.addWidget(l)
                
            add_pill(f"{wins_pct:.0f}% W", Styles.COLOR_BEST)
            add_pill(f"{draws_pct:.0f}% D", "#888888")
            add_pill(f"{losses_pct:.0f}% L", Styles.COLOR_BLUNDER)
            stat_row.addStretch()
            
            w_layout.addLayout(stat_row)
            return wrapper

        layout.addWidget(create_bar("White", color_stats['white']))
        layout.addWidget(create_bar("Black", color_stats['black']))
        
        return container

    def _get_asset_path(self, filename):
        """
        Robustly find assets using the project's standard resource resolver.
        Proxy to module-level helper.
        """
        return resolve_asset(filename)

    def _create_openings_list(self, openings, opening_wins):
        sorted_ops = sorted(openings.items(), key=lambda x: x[1], reverse=True) 
        
        container = QWidget()
                    
        sorted_ops = sorted(openings.items(), key=lambda x: x[1], reverse=True) 
        
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(8) # Tighter spacing for list
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Header Row
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
            # Hover effect for list items
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
            
            # Progress bar for win rate
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
             
        return container

    def _create_insights_panel(self):
        self.insights_container = QWidget()
        self.insights_layout = QVBoxLayout(self.insights_container)
        self.insights_layout.setSpacing(15)
        self.insights_layout.setContentsMargins(10, 10, 10, 10)
        self.insights_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        # Initial State: Placeholder Text / Skeleton
        # Removed the big generate button as we now have a header button
        
        lbl_placeholder = QLabel("Analysis ready. Click refresh to get insights.")
        lbl_placeholder.setStyleSheet(f"color: {Styles.COLOR_TEXT_SECONDARY}; font-style: italic;")
        lbl_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.insights_layout.addWidget(lbl_placeholder)
        
        # Add a few placeholder lines
        for _ in range(3):
            line = QFrame()
            line.setFixedHeight(12)
            line.setStyleSheet(f"background-color: {Styles.COLOR_SURFACE_LIGHT}; border-radius: 6px;")
            self.insights_layout.addWidget(line)
            
        return self.insights_container
        
    def _generate_insights(self, stats):
        # 1. Clear current Layout
        self._clear_layout(self.insights_layout)
        
        # 2. Show Loading
        lbl_loading = QLabel("Asking Coach Gemini...")
        lbl_loading.setStyleSheet(f"color: {Styles.COLOR_TEXT_PRIMARY};")
        lbl_loading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.insights_layout.addWidget(lbl_loading)
        
        # 3. Call API via Worker
        # Add some context about openings/etc
        stats_str = json.dumps(stats, indent=2)
        
        self.worker = InsightWorker(self.gemini_service, stats_str)
        self.worker.finished.connect(self._populate_insights)
        self.worker.error.connect(self._handle_insight_error)
        self.worker.start()

    def _handle_insight_error(self, err_msg):
        self._clear_layout(self.insights_layout)
        lbl_err = QLabel(f"Error: {err_msg}")
        lbl_err.setStyleSheet(f"color: {Styles.COLOR_BLUNDER};")
        lbl_err.setWordWrap(True)
        self.insights_layout.addWidget(lbl_err)
        
        # Retry button
        btn_retry = QPushButton("Retry")
        btn_retry.setStyleSheet(Styles.get_button_style())
        btn_retry.clicked.connect(self._generate_insights)
        self.insights_layout.addWidget(btn_retry)
        
    def _populate_insights(self, insight_text):
        self._clear_layout(self.insights_layout)
        
        # Helper to create insight item
        def add_insight(icon, text):
            row = QHBoxLayout()
            row.setSpacing(15)
            row.setAlignment(Qt.AlignmentFlag.AlignTop) # Align top for multi-line text
            
            # Use robust resolve_asset
            icon_path = None
            
            # Smart icon mapping if string provided
            if icon.endswith(".png") or icon.endswith(".svg"):
                 icon_path = resolve_asset(icon)
            else:
                 icon_path = resolve_asset(f"{icon}.png")
                 if not icon_path: icon_path = resolve_asset(f"{icon}.svg")
            
            if icon_path and os.path.exists(icon_path):
                lbl_icon = QLabel()
                pixmap = QPixmap(icon_path)
                if not pixmap.isNull():
                    # 24x24 for better visibility
                    pixmap = pixmap.scaled(24, 24, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                    lbl_icon.setPixmap(pixmap)
                    lbl_icon.setStyleSheet("border: none; background: transparent;")
                    # Add fixed width container for alignment
                    icon_container = QWidget()
                    icon_container.setFixedWidth(30)
                    icon_layout = QVBoxLayout(icon_container)
                    icon_layout.setContentsMargins(0,0,0,0)
                    icon_layout.addWidget(lbl_icon, alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
                    row.addWidget(icon_container)
                else:
                    # Fallback
                    lbl_icon = QLabel("💡") 
                    lbl_icon.setStyleSheet(f"color: {Styles.COLOR_ACCENT}; font-size: 20px; border: none; background: transparent;")
                    row.addWidget(lbl_icon)
            else:
                lbl_icon = QLabel("💡") # Fallback
                lbl_icon.setStyleSheet(f"color: {Styles.COLOR_ACCENT}; font-size: 20px; border: none; background: transparent;")
                row.addWidget(lbl_icon)

            # Clean text: Remove markdown bold (**text**) -> text
            clean_text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
            # Remove leading/trailing quotes if commonly added by LLM
            clean_text = clean_text.strip('"').strip("'")
            # Remove emojis (Basic range)
            # This regex matches many common emoji ranges and symbols
            clean_text = re.sub(r'[^\x00-\x7F]+', '', clean_text).strip()
            
            # Ensure it starts with capital letter
            if clean_text and clean_text[0].islower():
                clean_text = clean_text[0].upper() + clean_text[1:]

            lbl_text = QLabel(clean_text)
            lbl_text.setWordWrap(True)
            lbl_text.setStyleSheet(f"color: {Styles.COLOR_TEXT_SECONDARY}; font-size: 13px; line-height: 1.4; border: none; background: transparent;")
            row.addWidget(lbl_text, stretch=1)
            
            self.insights_layout.addLayout(row)

        # Parse the response (Expect prompt format)
        
        lines = insight_text.split('\n')
        count = 0
        for line in lines:
            line = line.strip()
            if not line: continue
            
            # Heuristic parsing for bullet points or numbered lists
            # Logic: If it looks like a list item, extract text and guess icon
            
            is_item = False
            content = line
            
            # Check for "1. ", "- ", "* "
            if line[0].isdigit() and ('.' in line[:4] or ')' in line[:4]):
                parts = line.split('.', 1)
                if len(parts) > 1: content = parts[1].strip()
                else: content = line.split(')', 1)[-1].strip()
                is_item = True
            elif line.startswith('- ') or line.startswith('* '):
                content = line[2:].strip()
                is_item = True
            
            # Even if not strict list, if it's substantial text, treat as insight
            if len(content) > 20: 
                 # Heuristic Icon Selection
                 lower_text = content.lower()
                 icon = "idea" # Default
                 
                 if "opening" in lower_text: icon = "opening_icon.png"
                 elif any(x in lower_text for x in ["endgame", "mate", "queen"]): icon = "phase_icon.png"
                 elif any(x in lower_text for x in ["accuracy", "precision", "blunder"]): icon = "accuracy.png"
                 elif any(x in lower_text for x in ["win", "momentum", "streak", "victory"]): icon = "win_rate.png"
                 elif any(x in lower_text for x in ["best", "great", "brilliant"]): icon = "best_v2.svg"
                 
                 add_insight(icon, content)
                 count += 1
        
        if count == 0:
            # Fallback if format is weird
            add_insight("idea", insight_text)

    def _create_quality_donut(self, counts):
        # counts passed in
        pass
                
        fig = Figure(figsize=(4, 3), dpi=100, facecolor=Styles.COLOR_SURFACE)
        ax = fig.add_subplot(111)
        ax.set_facecolor(Styles.COLOR_SURFACE)
        
        labels = []
        sizes = []
        colors = []
        color_map = {"Best": Styles.COLOR_BEST, "Inaccuracy": Styles.COLOR_INACCURACY, "Mistake": Styles.COLOR_MISTAKE, "Blunder": Styles.COLOR_BLUNDER}
        
        for k, v in counts.items():
            if v > 0:
                labels.append(k)
                sizes.append(v)
                colors.append(color_map.get(k, '#888'))
                
        if sizes:
            wedges, texts, autotexts = ax.pie(sizes, labels=None, autopct='%1.0f%%', colors=colors, 
                                              pctdistance=0.85, startangle=90,
                                              textprops=dict(color=Styles.COLOR_TEXT_SECONDARY))
            
            # Draw circle
            centre_circle = matplotlib.patches.Circle((0,0),0.70,fc=Styles.COLOR_SURFACE)
            fig.gca().add_artist(centre_circle)
            

            # Custom legend will be added below
            pass
            
        else:
             ax.text(0, 0, "No moves", ha='center', va='center', color=Styles.COLOR_TEXT_SECONDARY)
            
        canvas = FigureCanvasQTAgg(fig)
        canvas.setStyleSheet("background: transparent;")
        canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        # Container for Chart + Legend
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(canvas, stretch=3)
        
        # 3. Custom Legend Sidebar
        legend_widget = QWidget()
        legend_layout = QVBoxLayout(legend_widget)
        legend_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        legend_layout.setSpacing(12)
        
        order = ["Best", "Inaccuracy", "Mistake", "Blunder"]
        total_moves = sum(counts.values())
        
        for k in order:
            v = counts.get(k, 0)
            if v == 0 and total_moves > 0: continue 
            
            row = QHBoxLayout()
            row.setSpacing(10)
            
            # Icon
            icon_name = k.lower() 
            if icon_name == "best": icon_name = "best_v2"
            
            # Use robust resolver
            icon_path = resolve_asset(f"{icon_name}.svg")
            if not icon_path: icon_path = resolve_asset(f"{icon_name}.png")
            
            if icon_path and os.path.exists(icon_path):
                lbl_icon = QLabel()
                pixmap = QPixmap(icon_path)
                if not pixmap.isNull():
                    # Nice large icon for legend (24px)
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
            
            # Text Stats
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
            
        return container

    def _clear_layout(self, layout):
        # Legacy method for backward compatibility - uses shared utility
        clear_layout(layout)

    request_settings = pyqtSignal()

    def go_to_settings(self):
        self.request_settings.emit()
