import os
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QFrame, QScrollArea, QPushButton, QProgressBar, QSizePolicy)
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QRect
from PyQt6.QtGui import QColor, QPixmap
import matplotlib
matplotlib.use('QtAgg')
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
import json
from .styles import Styles
from .gui_utils import clear_layout, resolve_asset, get_user_color, create_button, show_error_dialog
from .metrics.workers import InsightWorker, StatsWorker
from .metrics.charts import (
    create_donut_figure, create_line_chart_figure,
    fig_to_canvas, fig_to_label, create_legend_widget
)
from .components import StatCard
from ..utils.logger import logger
from ..backend.groq_service import GroqService
import re
from PyQt6.QtWidgets import QLayout


# ---------------------------------------------------------------------------
# StatsLayout: Custom layout to arrange the 4 metric cards adaptively
# ---------------------------------------------------------------------------
class StatsLayout(QLayout):
    def __init__(self, parent=None, spacing=20):
        super().__init__(parent)
        self._items = []
        self._spacing = spacing
        self.setContentsMargins(0, 0, 0, 0)

    def __del__(self):
        item = self.takeAt(0)
        while item:
            item = self.takeAt(0)

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, index):
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        if not self._items:
            return 0
            
        margins = self.contentsMargins()
        available_width = width - margins.left() - margins.right()
        spacing = self._spacing
        
        if available_width >= 900:
            cols = 4
        elif available_width >= 500:
            cols = 2
        else:
            cols = 1
            
        rows = (len(self._items) + cols - 1) // cols
        
        total_height = 0
        for r in range(rows):
            max_h = 0
            for c in range(cols):
                idx = r * cols + c
                if idx < len(self._items):
                    max_h = max(max_h, self._items[idx].sizeHint().height())
            total_height += max_h
            
        if rows > 1:
            total_height += (rows - 1) * spacing
            
        return total_height + margins.top() + margins.bottom()

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self.doLayout(rect)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        size += QSize(margins.left() + margins.right(), margins.top() + margins.bottom())
        return size

    def doLayout(self, rect):
        if not self._items:
            return
            
        margins = self.contentsMargins()
        spacing = self._spacing
        available_width = rect.width() - margins.left() - margins.right()
        
        if available_width >= 900:
            cols = 4
        elif available_width >= 500:
            cols = 2
        else:
            cols = 1
            
        item_w = (available_width - (cols - 1) * spacing) // cols
        
        # Calculate Y start for each row
        row_heights = []
        rows = (len(self._items) + cols - 1) // cols
        for r in range(rows):
            max_h = 0
            for c in range(cols):
                idx = r * cols + c
                if idx < len(self._items):
                    max_h = max(max_h, self._items[idx].sizeHint().height())
            row_heights.append(max_h)

        row_y = [rect.y() + margins.top()]
        for r in range(1, rows):
            row_y.append(row_y[-1] + row_heights[r-1] + spacing)

        for idx, item in enumerate(self._items):
            r = idx // cols
            c = idx % cols
            
            x = rect.x() + margins.left() + c * (item_w + spacing)
            y = row_y[r]
            
            item.setGeometry(QRect(x, y, item_w, row_heights[r]))


# ---------------------------------------------------------------------------
# MasonryLayout: Custom QLayout for dynamic, space-efficient column packing
# ---------------------------------------------------------------------------
class MasonryLayout(QLayout):
    def __init__(self, parent=None, margin=0, spacing=20):
        super().__init__(parent)
        self._items = []
        self._spacing = spacing
        self.setContentsMargins(margin, margin, margin, margin)

    def __del__(self):
        item = self.takeAt(0)
        while item:
            item = self.takeAt(0)

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, index):
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self.doLayout(QRect(0, 0, width, 0), True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self.doLayout(rect, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        size += QSize(margins.left() + margins.right(), margins.top() + margins.bottom())
        return size

    def doLayout(self, rect, test_only):
        margins = self.contentsMargins()
        spacing = self._spacing
        
        available_width = rect.width() - margins.left() - margins.right()
        
        # We want columns to be at least 400px wide
        min_col_width = 400
        num_cols = max(1, available_width // min_col_width)
        num_cols = min(2, num_cols)  # Hard cap at 2 columns — 1 on narrow screens
        
        if num_cols > 1:
            col_width = (available_width - (num_cols - 1) * spacing) // num_cols
        else:
            col_width = available_width

        col_heights = [rect.y() + margins.top()] * num_cols

        for item in self._items:
            widget = item.widget()
            if widget and not widget.isVisible():
                continue

            min_col_idx = col_heights.index(min(col_heights))
            
            x = rect.x() + margins.left() + min_col_idx * (col_width + spacing)
            y = col_heights[min_col_idx]
            
            h = item.heightForWidth(col_width) if item.hasHeightForWidth() else item.sizeHint().height()
            
            if not test_only:
                item.setGeometry(QRect(x, y, col_width, h))
                
            col_heights[min_col_idx] = y + h + spacing

        if col_heights:
            max_height = max(col_heights) - spacing + margins.bottom()
        else:
            max_height = rect.y() + margins.top() + margins.bottom()
            
        return max_height - rect.y()


class MetricsWidget(QWidget):
    request_settings = pyqtSignal()
    
    def __init__(self, config_manager, history_manager):
        super().__init__()
        self.config_manager = config_manager
        self.history_manager = history_manager
        self.usernames = []
        self.games_data = []
        self.groq_service = GroqService()
        
        # Cache stats and insights for dynamic style updates
        self.current_stats = None
        self.current_insights = None
        
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
        
        self.btn_refresh = create_button("Refresh", style="secondary", on_click=self.refresh)
        header_layout.addWidget(self.btn_refresh)
        
        self.main_layout.addLayout(header_layout)
        
        # Content Area
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.addWidget(self.content_widget)

    def refresh_styles(self):
        """Re-applies styles and rebuilds the dashboard using cached stats/insights to pick up the new accent color immediately without re-querying the database."""
        if hasattr(self, 'btn_refresh') and self.btn_refresh:
            self.btn_refresh.setStyleSheet(Styles.get_control_button_style())
            
        if self.current_stats:
            saved_insights = self.current_insights
            clear_layout(self.content_layout)
            self.show_dashboard(self.current_stats)
            if saved_insights:
                self._populate_insights(saved_insights)

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
        self.current_stats = stats
        # Reset insights cache on new stats generation
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
        donuts_layout.addWidget(self._create_card("Result Distribution", self._create_result_donut(stats), max_height=310))
        donuts_layout.addWidget(self._create_card("Ending Distribution", self._create_termination_donut(stats['term_counts']), max_height=310))
        donuts_layout.addWidget(self._create_card("Move Quality Distribution", self._create_quality_donut(stats['quality_counts']), max_height=310))
        dashboard_layout.addWidget(donuts_widget)

        # 3. Remaining cards in a 2-column masonry (shortest-column packing)
        self.charts_container = QWidget()
        self.charts_layout = MasonryLayout(self.charts_container, margin=0, spacing=20)
        self.charts_layout.addWidget(self._create_card("Accuracy Trend", self._create_accuracy_chart(stats['accuracy_history'])))
        self.charts_layout.addWidget(self._create_card("Performance by Color", self._create_color_chart(stats['color_stats'])))
        self.charts_layout.addWidget(self._create_card("Top Openings", self._create_openings_list(stats['openings'], stats['opening_wins']), min_height=400))
        
        # AI Coach Insights refresh button
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
        self.charts_layout.addWidget(self._create_card("AI Coach Insights", self._create_insights_panel(), action_widget=btn_refresh_insights, min_height=400))

        dashboard_layout.addWidget(self.charts_container)
        
        scroll.setWidget(dashboard)
        self.content_layout.addWidget(scroll)

    def _create_card(self, title, widget, stretch=0, action_widget=None, max_height=None, min_height=None):
        # Professional Dashboard Card with modern styling
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
        # Apply size constraints before layout so masonry measures them correctly
        if max_height is not None:
            card.setMaximumHeight(max_height)
        if min_height is not None:
            card.setMinimumHeight(min_height)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)
        
        if title:
            header_layout = QHBoxLayout()
            lbl = QLabel(title)
            # Uppercase section title for modern look
            lbl.setStyleSheet(f"""
                color: {Styles.COLOR_TEXT_SECONDARY}; 
                font-size: 12px; 
                font-weight: 600; 
                letter-spacing: 0.5px;
                text-transform: uppercase;
                border: none; 
                background: transparent;
            """)
            header_layout.addWidget(lbl)
            
            header_layout.addStretch()
            
            if action_widget:
                header_layout.addWidget(action_widget)
                
            layout.addLayout(header_layout)
            
        layout.addWidget(widget)
        return card



    def _create_result_donut(self, stats):
        """Creates win/loss/draw donut chart using shared chart helper."""
        sizes = [stats['wins'], stats['losses'], stats['draws']]
        colors = [Styles.COLOR_ACCENT, '#ca3431', '#888888']
        center_text = f"{stats['win_rate']:.0f}%"
        
        fig = create_donut_figure(sizes, colors, center_text)
        return fig_to_canvas(fig)

    def _create_termination_donut(self, counts):
        """Creates termination reasons donut chart with legend."""
        # Define colors for ending types
        type_colors = {
            "Checkmate": Styles.COLOR_BEST,
            "Resignation": Styles.COLOR_ACCENT,
            "Time": "#e67e22",
            "Abandon": Styles.COLOR_BLUNDER,
            "Draw": "#888888"
        }
        
        # Build data lists
        labels, sizes, colors = [], [], []
        for k in ["Checkmate", "Resignation", "Time", "Abandon", "Draw"]:
            v = counts.get(k, 0)
            if v > 0:
                labels.append(k)
                sizes.append(v)
                colors.append(type_colors.get(k, '#888'))
        
        # Create chart
        center_text = str(sum(sizes)) if sizes else ""
        fig = create_donut_figure(sizes, colors, center_text)
        canvas = fig_to_canvas(fig)
        
        # Build container with chart + legend
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(canvas, stretch=3)
        layout.addWidget(create_legend_widget(labels, colors, sizes), stretch=2)
        
        return container

    def _create_accuracy_chart(self, full_history):
        """Creates accuracy trend line chart using shared helper."""
        accuracies = full_history[:20][::-1] if full_history else []
        fig = create_line_chart_figure(accuracies, figsize=(5, 3))
        return fig_to_canvas(fig)

    def _create_color_chart(self, color_stats):
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(20)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
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
            w_layout.setSpacing(6)
            w_layout.setContentsMargins(0, 0, 0, 0)
            
            # Label Row
            lbl_row = QHBoxLayout()
            lbl = QLabel(label)
            lbl.setStyleSheet(f"color: {Styles.COLOR_TEXT_PRIMARY}; font-weight: 600; font-size: 14px; border: none; background: transparent;")
            lbl_row.addWidget(lbl)
            lbl_row.addStretch()
            val = QLabel(f"{total} Games")
            val.setStyleSheet(f"color: {Styles.COLOR_TEXT_SECONDARY}; font-size: 12px; border: none; background: transparent;")
            lbl_row.addWidget(val)
            w_layout.addLayout(lbl_row)
            
            # Bar Container
            bar_container = QFrame()
            bar_container.setFixedHeight(24)
            bar_container.setStyleSheet(f"background-color: {Styles.COLOR_SURFACE_LIGHT}; border-radius: 12px; border: none;")
            bar_layout = QHBoxLayout(bar_container)
            bar_layout.setContentsMargins(0, 0, 0, 0)
            bar_layout.setSpacing(1)
            
            # Segments
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
            
            # Stats Row beneath
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
        # min height handled by _create_card; remove inner constraint to let card control it
        container.setMinimumHeight(0)
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
        # Scrollable wrapper so long AI responses don't get clipped
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical {
                background: transparent; width: 6px; margin: 0;
            }
            QScrollBar::handle:vertical {
                background: rgba(255,255,255,0.15); border-radius: 3px; min-height: 20px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)

        self.insights_container = QWidget()
        self.insights_container.setStyleSheet("background: transparent;")
        # Must be Expanding so QScrollArea can scroll it when content overflows
        self.insights_container.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self.insights_layout = QVBoxLayout(self.insights_container)
        self.insights_layout.setSpacing(15)
        self.insights_layout.setContentsMargins(10, 10, 10, 10)
        self.insights_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        lbl_placeholder = QLabel("Analysis ready. Click refresh to get insights.")
        lbl_placeholder.setStyleSheet(f"color: {Styles.COLOR_TEXT_SECONDARY}; font-style: italic;")
        lbl_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.insights_layout.addWidget(lbl_placeholder)

        for _ in range(3):
            line = QFrame()
            line.setFixedHeight(12)
            line.setStyleSheet(f"background-color: {Styles.COLOR_SURFACE_LIGHT}; border-radius: 6px;")
            self.insights_layout.addWidget(line)

        scroll.setWidget(self.insights_container)
        return scroll

    def _generate_insights(self, stats):
        # 1. Clear current Layout
        self._clear_layout(self.insights_layout)
        
        # 2. Show Loading
        lbl_loading = QLabel("Asking Coach Groq...")
        lbl_loading.setStyleSheet(f"color: {Styles.COLOR_TEXT_PRIMARY};")
        lbl_loading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.insights_layout.addWidget(lbl_loading)
        
        # 3. Call API via Worker
        # Add some context about openings/etc
        stats_str = json.dumps(stats, indent=2)
        
        self.worker = InsightWorker(self.groq_service, stats_str)
        self.worker.finished.connect(self._populate_insights)
        self.worker.error.connect(self._handle_insight_error)
        self.worker.start()

    def _handle_insight_error(self, err_msg):
        self._clear_layout(self.insights_layout)
        lbl_err = QLabel(f"Error: {err_msg}")
        lbl_err.setStyleSheet(f"color: {Styles.COLOR_BLUNDER};")
        lbl_err.setWordWrap(True)
        lbl_err.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        self.insights_layout.addWidget(lbl_err)

        # Retry button
        btn_retry = QPushButton("Retry")
        btn_retry.setStyleSheet(Styles.get_button_style())
        btn_retry.clicked.connect(self._generate_insights)
        self.insights_layout.addWidget(btn_retry)

        # Modal dialog with copyable text (for bug reports)
        show_error_dialog(
            self,
            "AI Coach Insights Failed",
            "Could not generate AI insights. See the insight card and "
            "the details below for the full error.",
            err_msg,
        )
        
    def _populate_insights(self, insight_text):
        self.current_insights = insight_text
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
            wedges, texts = ax.pie(sizes, labels=None, colors=colors,
                                   startangle=90)
            
            # Draw circle
            centre_circle = matplotlib.patches.Circle((0,0),0.70,fc=Styles.COLOR_SURFACE)
            fig.gca().add_artist(centre_circle)

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

    def go_to_settings(self):
        self.request_settings.emit()
