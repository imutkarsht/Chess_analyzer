import json
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QScrollArea, QProgressBar, QPushButton
from PyQt6.QtCore import Qt, pyqtSignal

from src.gui.styles import Styles
from src.gui.utils.gui_utils import clear_layout, create_button
from src.gui.components import StatCard, StatsLayout, MasonryLayout
from src.backend.services.groq_service import GroqService
from src.gui.metrics.workers import StatsWorker

# Import modular cards
from src.gui.views.metrics import (
    ResultDistributionCard,
    EndingDistributionCard,
    MoveQualityCard,
    AccuracyTrendCard,
    ColorPerformanceCard,
    OpeningsListCard,
    AICoachCard
)

class MetricsWidget(QWidget):
    request_settings = pyqtSignal()
    
    def __init__(self, config_manager, history_manager):
        super().__init__()
        self.config_manager = config_manager
        self.history_manager = history_manager
        self.usernames = []
        self.games_data = []
        
        self._groq_service = GroqService()
        
        # Cache stats and insights for dynamic style updates
        self.current_stats = None
        self.current_insights = None
        
        self.setup_ui()
        self.refresh()

    @property
    def groq_service(self):
        return self._groq_service

    @groq_service.setter
    def groq_service(self, service):
        self._groq_service = service
        if hasattr(self, 'ai_coach_card') and self.ai_coach_card:
            self.ai_coach_card.groq_service = service

    def setup_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        
        # Header Bar Container
        self.header_bar = QFrame()
        self.header_bar.setStyleSheet(f"""
            QFrame {{
                background-color: {Styles.COLOR_BACKGROUND};
                border-bottom: 1px solid {Styles.COLOR_BORDER};
            }}
        """)
        header_layout = QHBoxLayout(self.header_bar)
        header_layout.setContentsMargins(40, 12, 40, 12)
        
        # Title
        title = QLabel("Performance Dashboard")
        title.setStyleSheet(f"font-size: 24px; font-weight: bold; color: {Styles.COLOR_TEXT_PRIMARY}; background: transparent; border: none;")
        header_layout.addWidget(title)
        
        header_layout.addStretch()
        
        self.btn_refresh = create_button("Refresh", style="secondary", on_click=self.refresh, icon_name="fa5s.sync-alt")
        header_layout.addWidget(self.btn_refresh)
        
        self.main_layout.addWidget(self.header_bar)
        
        # Content Area
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(40, 20, 40, 20)
        self.content_layout.setSpacing(20)
        self.main_layout.addWidget(self.content_widget, 1)

    def refresh_styles(self):
        """Re-applies styles and rebuilds the dashboard using cached stats/insights."""
        if hasattr(self, 'header_bar') and self.header_bar:
            self.header_bar.setStyleSheet(f"""
                QFrame {{
                    background-color: {Styles.COLOR_BACKGROUND};
                    border-bottom: 1px solid {Styles.COLOR_BORDER};
                }}
            """)

        if hasattr(self, 'btn_refresh') and self.btn_refresh:
            self.btn_refresh.setStyleSheet(Styles.get_control_button_style())
            
        if self.current_stats:
            saved_insights = self.current_insights
            clear_layout(self.content_layout)
            self.show_dashboard(self.current_stats)
            if saved_insights and hasattr(self, 'ai_coach_card') and self.ai_coach_card:
                self.ai_coach_card.set_insights(saved_insights)

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
        if hasattr(self, 'stats_worker') and self.stats_worker is not None and self.stats_worker.isRunning():
            try:
                self.stats_worker.finished.disconnect()
            except (TypeError, RuntimeError):
                pass
            self.stats_worker.quit()
            self.stats_worker.wait()

        self.stats_worker = StatsWorker(self.games_data, self.usernames)
        self.stats_worker.finished.connect(self.on_stats_ready)
        self.stats_worker.start()

    def on_stats_ready(self, stats):
        self.current_stats = stats
        self.current_insights = None
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

    def go_to_settings(self):
        self.request_settings.emit()

    def show_dashboard(self, stats):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        
        dashboard = QWidget()
        dashboard.setStyleSheet("background: transparent;")
        
        dashboard_layout = QVBoxLayout(dashboard)
        dashboard_layout.setSpacing(20)
        dashboard_layout.setContentsMargins(10, 10, 10, 10)
        
        # 1. Key Metrics Row - uses custom adaptive StatsLayout
        self.stats_container = QWidget()
        self.stats_layout = StatsLayout(self.stats_container, spacing=20)
        self.stats_layout.addWidget(StatCard("Total Games", str(stats['total']), "Tracked this week", icon="games"))
        self.stats_layout.addWidget(StatCard("Win Rate", f"{stats['win_rate']:.1f}%", f"Vs last {stats['total']} games", icon="win_rate", color=Styles.COLOR_ACCENT))
        self.stats_layout.addWidget(StatCard("Avg Accuracy", f"{stats['avg_accuracy']:.1f}%", "Based on engine eval.", icon="accuracy"))
        self.stats_layout.addWidget(StatCard("Best Win", str(stats['best_win']), "Keep playing!", icon="best_win"))
        dashboard_layout.addWidget(self.stats_container)
        
        # 2. Donut charts — always 3 equal columns, fully dynamic width
        donuts_widget = QWidget()
        donuts_layout = QHBoxLayout(donuts_widget)
        donuts_layout.setSpacing(20)
        donuts_layout.setContentsMargins(0, 0, 0, 0)
        
        self.result_card = ResultDistributionCard()
        self.result_card.set_stats(stats)
        donuts_layout.addWidget(self.result_card)
        
        self.ending_card = EndingDistributionCard()
        self.ending_card.set_stats(stats)
        donuts_layout.addWidget(self.ending_card)
        
        self.quality_card = MoveQualityCard()
        self.quality_card.set_stats(stats)
        donuts_layout.addWidget(self.quality_card)
        
        dashboard_layout.addWidget(donuts_widget)

        # 3. Remaining cards in a 2-column masonry (shortest-column packing)
        self.charts_container = QWidget()
        self.charts_layout = MasonryLayout(self.charts_container, margin=0, spacing=20, min_col_width=400)
        
        self.accuracy_card = AccuracyTrendCard()
        self.accuracy_card.set_stats(stats)
        self.charts_layout.addWidget(self.accuracy_card)
        
        self.color_card = ColorPerformanceCard()
        self.color_card.set_stats(stats)
        self.charts_layout.addWidget(self.color_card)
        
        self.openings_card = OpeningsListCard()
        self.openings_card.set_stats(stats)
        self.charts_layout.addWidget(self.openings_card)
        
        self.ai_coach_card = AICoachCard(self.groq_service)
        self.ai_coach_card.set_stats(stats)
        
        # Connect AI card's internal worker to capture insights cached text
        self.ai_coach_card.btn_refresh_insights.clicked.connect(self._sync_insights_cache)
        self.charts_layout.addWidget(self.ai_coach_card)

        dashboard_layout.addWidget(self.charts_container)
        
        scroll.setWidget(dashboard)
        self.content_layout.addWidget(scroll)

    def _sync_insights_cache(self):
        if hasattr(self, 'ai_coach_card') and self.ai_coach_card:
            if self.ai_coach_card.worker:
                self.ai_coach_card.worker.finished.connect(self._store_insights_cache)

    def _store_insights_cache(self, insight_text):
        self.current_insights = insight_text
