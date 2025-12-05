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
from ..utils.logger import logger
from ..backend.gemini_service import GeminiService
from ..utils.path_utils import get_resource_path

def resolve_asset(filename):
    """
    Robustly find assets using the project's standard resource resolver.
    Checks:
    1. assets/images/ (SVGs)
    2. assets/icons/ (PNGs)
    3. assets/ (Root)
    """
    candidates = [
        os.path.join("assets", "images", filename),
        os.path.join("assets", "icons", filename),
        os.path.join("assets", filename)
    ]
    
    for rel_path in candidates:
        full_path = get_resource_path(rel_path)
        if os.path.exists(full_path):
            return full_path
    return None

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

# ... (MetricsWidget class remains) ...

    def _create_quality_donut(self):
        # Container for Chart + Legend
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 1. Calculate Data
        counts = {"Best": 0, "Inaccuracy": 0, "Mistake": 0, "Blunder": 0}
        total_moves = 0
        
        for game in self.games_data:
            try:
                if game['summary_json']:
                    summary = json.loads(game['summary_json'])
                    white = game['white'].lower()
                    user_color = 'white' if white in [u.lower() for u in self.usernames] else 'black'
                    
                    s_data = summary.get(user_color, {})
                    # Map to categories
                    counts["Best"] += s_data.get("Best", 0) + s_data.get("Brilliant", 0) + s_data.get("Great", 0)
                    counts["Inaccuracy"] += s_data.get("Inaccuracy", 0)
                    counts["Mistake"] += s_data.get("Mistake", 0)
                    counts["Blunder"] += s_data.get("Blunder", 0)
            except:
                pass
        
        total_moves = sum(counts.values())

        # 2. Setup Chart
        fig = Figure(figsize=(3, 3), dpi=100, facecolor=Styles.COLOR_SURFACE)
        ax = fig.add_subplot(111)
        ax.set_facecolor(Styles.COLOR_SURFACE)
        
        labels = []
        sizes = []
        colors = []
        # Specific order for consistency
        order = ["Best", "Inaccuracy", "Mistake", "Blunder"]
        color_map = {
            "Best": Styles.COLOR_BEST, 
            "Inaccuracy": Styles.COLOR_INACCURACY, 
            "Mistake": Styles.COLOR_MISTAKE, 
            "Blunder": Styles.COLOR_BLUNDER
        }
        
        for k in order:
            v = counts.get(k, 0)
            if v > 0:
                labels.append(k)
                sizes.append(v)
                colors.append(color_map.get(k, '#888'))
                
        if sizes:
            wedges, texts, autotexts = ax.pie(sizes, labels=None, autopct=None, colors=colors, 
                                              startangle=90, counterclock=False)
            
            # Donut hole
            centre_circle = matplotlib.patches.Circle((0,0), 0.75, fc=Styles.COLOR_SURFACE)
            fig.gca().add_artist(centre_circle)
        else:
             ax.text(0, 0, "No Data", ha='center', va='center', color=Styles.COLOR_TEXT_SECONDARY)
            
        canvas = FigureCanvasQTAgg(fig)
        canvas.setStyleSheet("background: transparent;")
        canvas.setSizePolicy(Qt.QSizePolicy.Policy.Expanding, Qt.QSizePolicy.Policy.Expanding)
        layout.addWidget(canvas, stretch=3)
        
        # 3. Custom Legend
        legend_widget = QWidget()
        legend_layout = QVBoxLayout(legend_widget)
        legend_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        legend_layout.setSpacing(12)
        
        for k in order:
            v = counts.get(k, 0)
            if v == 0 and total_moves > 0: continue 
            
            row = QHBoxLayout()
            row.setSpacing(8)
            
            # Icon
            icon_name = k.lower() 
            if icon_name == "best": icon_name = "best_v2" # User preference
            
            # Check SVG first, then PNG
            icon_path = self._get_asset_path(f"{icon_name}.svg")
            if not icon_path:
                icon_path = self._get_asset_path(f"{icon_name}.png")
            
            if icon_path and os.path.exists(icon_path):
                lbl_icon = QLabel()
                pixmap = QPixmap(icon_path)
                if not pixmap.isNull():
                    pixmap = pixmap.scaled(20, 20, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                    lbl_icon.setPixmap(pixmap)
                    lbl_icon.setStyleSheet("border: none; background: transparent;")
                    row.addWidget(lbl_icon)
                else:
                    # Fallback
                    dot = QLabel("●") 
                    dot.setStyleSheet(f"color: {color_map[k]}; font-size: 14px; border: none;")
                    row.addWidget(dot) 
            else:
                # Color dot fallback
                dot = QLabel("●") 
                dot.setStyleSheet(f"color: {color_map[k]}; font-size: 14px; border: none;")
                row.addWidget(dot)
            
            # Label
            lbl_name = QLabel(k)
            lbl_name.setStyleSheet(f"color: {Styles.COLOR_TEXT_SECONDARY}; font-size: 13px; font-weight: 500; border: none;")
            row.addWidget(lbl_name)
            
            row.addStretch()
            
            # Percentage/Count
            pct = (v / total_moves * 100) if total_moves > 0 else 0
            lbl_stat = QLabel(f"{v} ({pct:.0f}%)")
            lbl_stat.setStyleSheet(f"color: {Styles.COLOR_TEXT_PRIMARY}; font-size: 13px; font-weight: bold; border: none;")
            row.addWidget(lbl_stat)
            
            legend_layout.addLayout(row)
            
        if total_moves == 0:
            lbl_no_data = QLabel("No analyzed moves")
            lbl_no_data.setStyleSheet(f"color: {Styles.COLOR_TEXT_SECONDARY}; font-style: italic;")
            legend_layout.addWidget(lbl_no_data)

        layout.addWidget(legend_widget, stretch=2)
        
        return container

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
        self._clear_layout(self.content_layout)
        
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
            
        self.show_dashboard()

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

    def show_dashboard(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        
        dashboard = QWidget()
        dashboard.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(dashboard)
        layout.setSpacing(20)
        
        stats = self._calculate_stats()
        
        # 1. Key Metrics Row (2x2 on small, 4x1 on large - using simple hbox for now)
        metrics_layout = QHBoxLayout()
        metrics_layout.setSpacing(20)
        
        metrics_layout.addWidget(StatCard("Total Games", str(stats['total']), "Tracked this week", icon="games"))
        metrics_layout.addWidget(StatCard("Win Rate", f"{stats['win_rate']:.1f}%", f"Vs last {stats['total']} games", icon="win_rate", color=Styles.COLOR_ACCENT))
        metrics_layout.addWidget(StatCard("Avg Accuracy", f"{stats['avg_accuracy']:.1f}%", "Based on engine eval.", icon="accuracy"))
        metrics_layout.addWidget(StatCard("Best Win", str(stats['best_win']), "Keep playing!", icon="best_win"))
        
        layout.addLayout(metrics_layout)
        
        # 2. Charts Row
        charts_layout = QHBoxLayout()
        charts_layout.setSpacing(20)
        
        # Consistent Card Styling for wrappers
        # Result Distribution
        charts_layout.addWidget(self._create_card("Result Distribution", self._create_result_donut(stats), 1))
        # Accuracy Trend
        charts_layout.addWidget(self._create_card("Accuracy Trend", self._create_accuracy_chart(), 2))
        # Move Quality
        charts_layout.addWidget(self._create_card("Move Quality Distribution", self._create_quality_donut(), 1))
        
        layout.addLayout(charts_layout)
        
        # 3. Insights & Openings
        bottom_layout = QHBoxLayout()
        bottom_layout.setSpacing(20)
        
        # Top Openings
        bottom_layout.addWidget(self._create_card("Top Openings", self._create_openings_list(), 1))
        
        # Insights
        bottom_layout.addWidget(self._create_card("AI Coach Insights", self._create_insights_panel(), 1)) 
        
        layout.addLayout(bottom_layout)
        
        scroll.setWidget(dashboard)
        self.content_layout.addWidget(scroll)

    def _create_card(self, title, widget, stretch=0):
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
            lbl = QLabel(title)
            # Distinct title style matching StatCard
            lbl.setStyleSheet(f"color: {Styles.COLOR_TEXT_SECONDARY}; font-size: 14px; font-weight: 600; border: none; background: transparent;")
            layout.addWidget(lbl)
            
        layout.addWidget(widget)
        # Apply stretch to wrapping layout if possible, but here we return card
        # wrapper HBox handles stretch
        return card

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

    def _create_accuracy_chart(self):
        fig = Figure(figsize=(5, 3), dpi=100, facecolor=Styles.COLOR_SURFACE)
        ax = fig.add_subplot(111)
        ax.set_facecolor(Styles.COLOR_SURFACE)
        
        # Get last 20 accuracies
        accuracies = []
        for game in self.games_data[:20][::-1]:
            try:
                if game['summary_json']:
                    summary = json.loads(game['summary_json'])
                    white = game['white'].lower()
                    user_color = 'white' if white in [u.lower() for u in self.usernames] else 'black'
                    acc = summary.get(user_color, {}).get('accuracy', 0)
                    if acc > 0:
                        accuracies.append(acc)
            except:
                pass
                
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

    def _get_asset_path(self, filename):
        """
        Robustly find assets using the project's standard resource resolver.
        Proxy to module-level helper.
        """
        return resolve_asset(filename)

    def _create_openings_list(self):
        # Data aggregation
        openings = {}
        opening_wins = {}
        # ... (same parsing logic)
        for game in self.games_data:
            pgn = game['pgn']
            if 'Opening "' in pgn:
                import re
                match = re.search(r'\[Opening "([^"]+)"\]', pgn)
                if match:
                    op = match.group(1)
                    # Simplify name
                    main_name = op.split(":")[0].split(",")[0].strip()
                    openings[main_name] = openings.get(main_name, 0) + 1
                    
                    # Check win
                    res = game['result']
                    white = game['white'].lower()
                    user_color = 'white' if white in [u.lower() for u in self.usernames] else 'black'
                    win = False
                    if res == '1-0' and user_color == 'white': win = True
                    elif res == '0-1' and user_color == 'black': win = True
                    
                    if win:
                        opening_wins[main_name] = opening_wins.get(main_name, 0) + 1
                    
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
        
        # Initial State: Button
        self.btn_generate = QPushButton("Generate AI Insights (Gemini)")
        self.btn_generate.setStyleSheet(Styles.get_button_style())
        self.btn_generate.setCursor(Qt.CursorShape.PointingHandCursor) # Visual cue
        self.btn_generate.clicked.connect(self._generate_insights)
        self.insights_layout.addWidget(self.btn_generate, alignment=Qt.AlignmentFlag.AlignCenter)
        
        lbl_placeholder = QLabel("Click to get your coach's summary")
        lbl_placeholder.setStyleSheet(f"color: {Styles.COLOR_TEXT_SECONDARY}; font-style: italic; margin-top: 10px;")
        lbl_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.insights_layout.addWidget(lbl_placeholder)
        
        return self.insights_container
        
    def _generate_insights(self):
        # 1. Clear current Layout
        self._clear_layout(self.insights_layout)
        
        # 2. Show Loading
        lbl_loading = QLabel("Asking Coach Gemini...")
        lbl_loading.setStyleSheet(f"color: {Styles.COLOR_TEXT_PRIMARY};")
        lbl_loading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.insights_layout.addWidget(lbl_loading)
        
        # 3. Call API via Worker
        stats = self._calculate_stats()
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
            row.setSpacing(10)
            
            # Use robust resolve_asset
            icon_path = resolve_asset(f"{icon}.png")
            # If not found as png, try svg just in case
            if not icon_path:
                 icon_path = resolve_asset(f"{icon}.svg")
            
            if icon_path and os.path.exists(icon_path):
                lbl_icon = QLabel()
                pixmap = QPixmap(icon_path)
                if not pixmap.isNull():
                    pixmap = pixmap.scaled(16, 16, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                    lbl_icon.setPixmap(pixmap)
                    lbl_icon.setStyleSheet("border: none; background: transparent;")
                    row.addWidget(lbl_icon)
                else:
                    # Fallback
                    lbl_icon = QLabel("💡") 
                    lbl_icon.setStyleSheet(f"color: {Styles.COLOR_ACCENT}; font-size: 16px; border: none; background: transparent;")
                    row.addWidget(lbl_icon)
            else:
                lbl_icon = QLabel("💡") # Fallback
                lbl_icon.setStyleSheet(f"color: {Styles.COLOR_ACCENT}; font-size: 16px; border: none; background: transparent;")
                row.addWidget(lbl_icon)

            lbl_text = QLabel(text)
            lbl_text.setWordWrap(True)
            # Basic markdown-like parsing for bolding if needed, but for now just text
            lbl_text.setText(text) 
            lbl_text.setStyleSheet(f"color: {Styles.COLOR_TEXT_SECONDARY}; font-size: 14px; border: none; background: transparent;")
            row.addWidget(lbl_text, stretch=1)
            
            self.insights_layout.addLayout(row)

        # Parse the response (Expect prompt format)
        # ... (rest of parsing logic)
        
        lines = insight_text.split('\n')
        count = 0
        for line in lines:
            line = line.strip()
            if not line: continue
            
            # Heuristic parsing
            if line[0].isdigit() and ('.' in line or ')' in line):
                 # It's an insight point
                 clean_text = line.split('.', 1)[-1].strip()
                 if not clean_text: clean_text = line.split(')', 1)[-1].strip()
                 
                 icon = "idea" # Generic icon
                 if "opening" in clean_text.lower(): icon = "opening_icon"
                 elif "endgame" in clean_text.lower(): icon = "phase_icon"
                 elif "accuracy" in clean_text.lower(): icon = "accuracy" # Re-mapped to accuracy.png
                 elif "win" in clean_text.lower(): icon = "win_rate"
                 
                 add_insight(icon, clean_text)
                 count += 1
        
        if count == 0:
            # Fallback if format is weird
            add_insight("idea", insight_text)

    def _create_quality_donut(self):
        # Aggregate move qualities
        counts = {"Best": 0, "Inaccuracy": 0, "Mistake": 0, "Blunder": 0}
        
        for game in self.games_data:
            try:
                if game['summary_json']:
                    summary = json.loads(game['summary_json'])
                    white = game['white'].lower()
                    user_color = 'white' if white in [u.lower() for u in self.usernames] else 'black'
                    
                    s_data = summary.get(user_color, {})
                    # Map to simpler categories if needed or use existing
                    # Assuming standard mapping
                    counts["Best"] += s_data.get("Best", 0) + s_data.get("Brilliant", 0) + s_data.get("Great", 0)
                    counts["Inaccuracy"] += s_data.get("Inaccuracy", 0)
                    counts["Mistake"] += s_data.get("Mistake", 0)
                    counts["Blunder"] += s_data.get("Blunder", 0)
            except:
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
