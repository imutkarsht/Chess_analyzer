from typing import Any

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from src.backend.analysis.metrics_aggregator import MetricsAggregator
from src.backend.services.groq_service import GroqService
from src.gui.components import MasonryLayout, StatCard, StatsLayout
from src.gui.metrics.drill_down_view import DrillDownView
from src.gui.metrics.workers import StatsWorker
from src.gui.styles import Styles
from src.gui.utils.gui_utils import clear_layout, create_button, create_combobox

# Import modular cards
from src.gui.views.metrics import (
    AccuracyTrendCard,
    AdvantageConversionCard,
    AICoachCard,
    BrilliancyHallCard,
    EndingDistributionCard,
    HangingPiecesCard,
    MoveQualityCard,
    OpeningsListCard,
    PhasePerformanceCard,
    TacticalThemesCard,
    TimeManagementCard,
)


class MetricsWidget(QWidget):
    request_settings = pyqtSignal()
    game_selected = pyqtSignal(object, int)  # Emits (GameAnalysis, move_index)

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
        self._needs_refresh: bool = True
        self._filter_cache: dict[tuple[str, str, str, str], dict[str, Any]] = {}

        self.setup_ui()
        self.refresh()

    @property
    def needs_refresh(self) -> bool:
        """Returns True if the dashboard data needs to be re-fetched or recomputed."""
        return self._needs_refresh

    def mark_dirty(self) -> None:
        """Marks the dashboard as dirty so it refreshes on the next view."""
        self._needs_refresh = True
        self._filter_cache.clear()

    @property
    def groq_service(self):
        return self._groq_service

    @groq_service.setter
    def groq_service(self, service):
        self._groq_service = service
        if hasattr(self, "ai_coach_card") and self.ai_coach_card:
            self.ai_coach_card.groq_service = service

    def setup_ui(self):
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # Header Bar Container
        self.header_bar = QFrame()
        self.header_bar.setStyleSheet(Styles.get_header_bar_ext_style(Styles.COLOR_BACKGROUND))
        header_layout = QHBoxLayout(self.header_bar)
        header_layout.setContentsMargins(24, 12, 24, 12)

        # Title
        self.title_lbl = QLabel("Performance Dashboard")
        self.title_lbl.setStyleSheet(
            Styles.get_label_style(size=24, color=Styles.COLOR_TEXT_PRIMARY, bold=True)
            + " "
            + Styles.get_transparent_label_style()
        )
        header_layout.addWidget(self.title_lbl)

        header_layout.addStretch()

        self.btn_refresh = create_button(
            "Refresh",
            style="secondary",
            on_click=lambda: self.refresh(force=True),
            icon_name="fa5s.sync-alt",
        )
        header_layout.addWidget(self.btn_refresh)

        self.main_layout.addWidget(self.header_bar)

        # Filter Toolbar Container
        self.filter_bar = QFrame()
        self.filter_bar.setObjectName("filter_bar")
        self.filter_bar.setStyleSheet(
            f"QFrame#filter_bar {{ background-color: {Styles.COLOR_BACKGROUND}; border-bottom: 1px solid {Styles.COLOR_BORDER}; }}"
        )
        filter_layout = QHBoxLayout(self.filter_bar)
        filter_layout.setContentsMargins(24, 8, 24, 8)
        filter_layout.setSpacing(10)

        lbl_style = f"{Styles.get_label_style(size=12, color=Styles.COLOR_TEXT_PRIMARY, weight=600)} border: none; background: transparent;"

        # 1. Color Filter
        self.lbl_color = QLabel("Color:")
        self.lbl_color.setStyleSheet(lbl_style)
        filter_layout.addWidget(self.lbl_color)

        self.combo_color = create_combobox(
            items=["All Colors", "White", "Black"],
            on_change=self.on_filter_changed,
        )
        self.combo_color.setFixedWidth(110)
        filter_layout.addWidget(self.combo_color)

        filter_layout.addSpacing(10)

        # 2. Format Filter
        self.lbl_format = QLabel("Format:")
        self.lbl_format.setStyleSheet(lbl_style)
        filter_layout.addWidget(self.lbl_format)

        self.combo_format = create_combobox(
            items=["All Formats", "Rapid", "Blitz", "Bullet", "Classical", "Freestyle (Chess960)"],
            on_change=self.on_filter_changed,
        )
        self.combo_format.setFixedWidth(155)
        filter_layout.addWidget(self.combo_format)

        filter_layout.addSpacing(10)

        # 3. Source Filter
        self.lbl_source = QLabel("Source:")
        self.lbl_source.setStyleSheet(lbl_style)
        filter_layout.addWidget(self.lbl_source)

        self.combo_source = create_combobox(
            items=["All Sources", "Chess.com", "Lichess", "File"],
            on_change=self.on_filter_changed,
        )
        self.combo_source.setFixedWidth(110)
        filter_layout.addWidget(self.combo_source)

        filter_layout.addSpacing(10)

        # 4. Period Filter
        self.lbl_period = QLabel("Period:")
        self.lbl_period.setStyleSheet(lbl_style)
        filter_layout.addWidget(self.lbl_period)

        self.combo_period = create_combobox(
            items=[
                "All Time",
                "Last 24 Hours",
                "Last 7 Days",
                "Last 30 Days",
                "Last 90 Days",
                "This Year",
            ],
            on_change=self.on_filter_changed,
        )
        self.combo_period.setFixedWidth(135)
        filter_layout.addWidget(self.combo_period)

        filter_layout.addSpacing(10)

        # Reset button
        self.btn_reset_filters = create_button(
            "Reset", style="secondary", on_click=self.reset_filters, icon_name="fa5s.undo"
        )
        filter_layout.addWidget(self.btn_reset_filters)

        filter_layout.addStretch()

        # Games count badge
        self.lbl_games_badge = QLabel("0 Games")
        self.lbl_games_badge.setStyleSheet(
            f"background-color: {Styles.COLOR_SURFACE_LIGHT}; color: {Styles.COLOR_ACCENT}; "
            f"border: 1px solid {Styles.COLOR_BORDER}; border-radius: 12px; "
            "padding: 4px 12px; font-weight: 600; font-size: 12px;"
        )
        filter_layout.addWidget(self.lbl_games_badge)

        self.main_layout.addWidget(self.filter_bar)

        # Content Area Stack (Index 0 = Dashboard Container, Index 1 = DrillDownView)
        self.stacked_widget = QStackedWidget()
        self.stacked_widget.setStyleSheet(Styles.get_background_style())

        self.content_widget = QWidget()
        self.content_widget.setStyleSheet(Styles.get_background_style())
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(0)
        self.stacked_widget.addWidget(self.content_widget)

        self.drill_down_view = DrillDownView()
        self.drill_down_view.back_requested.connect(self._on_drill_down_back)
        self.drill_down_view.position_selected.connect(self._on_drill_down_position_selected)
        self.stacked_widget.addWidget(self.drill_down_view)

        self.main_layout.addWidget(self.stacked_widget, 1)

    def refresh_styles(self):
        """Re-applies styles and rebuilds the dashboard using cached stats/insights."""
        if hasattr(self, "header_bar") and self.header_bar:
            self.header_bar.setStyleSheet(Styles.get_header_bar_ext_style(Styles.COLOR_BACKGROUND))

        if hasattr(self, "filter_bar") and self.filter_bar:
            self.filter_bar.setStyleSheet(
                f"QFrame#filter_bar {{ background-color: {Styles.COLOR_BACKGROUND}; border-bottom: 1px solid {Styles.COLOR_BORDER}; }}"
            )

        if hasattr(self, "title_lbl") and self.title_lbl:
            self.title_lbl.setStyleSheet(
                Styles.get_label_style(size=24, color=Styles.COLOR_TEXT_PRIMARY, bold=True)
                + " "
                + Styles.get_transparent_label_style()
            )

        if hasattr(self, "btn_refresh") and self.btn_refresh:
            self.btn_refresh.setStyleSheet(Styles.get_control_button_style())
            try:
                import qtawesome as qta

                self.btn_refresh.setIcon(
                    qta.icon("fa5s.sync-alt", color=Styles.COLOR_TEXT_SECONDARY)
                )
            except ImportError:
                pass

        if hasattr(self, "btn_reset_filters") and self.btn_reset_filters:
            self.btn_reset_filters.setStyleSheet(Styles.get_control_button_style())
            try:
                import qtawesome as qta

                self.btn_reset_filters.setIcon(
                    qta.icon("fa5s.undo", color=Styles.COLOR_TEXT_SECONDARY)
                )
            except ImportError:
                pass

        if hasattr(self, "content_widget") and self.content_widget:
            self.content_widget.setStyleSheet(Styles.get_background_style())

        if hasattr(self, "lbl_games_badge") and self.lbl_games_badge:
            self.lbl_games_badge.setStyleSheet(
                f"background-color: {Styles.COLOR_SURFACE_LIGHT}; color: {Styles.COLOR_ACCENT}; "
                f"border: 1px solid {Styles.COLOR_BORDER}; border-radius: 12px; "
                "padding: 4px 12px; font-weight: 600; font-size: 12px;"
            )

        for combo in (
            getattr(self, "combo_color", None),
            getattr(self, "combo_format", None),
            getattr(self, "combo_source", None),
            getattr(self, "combo_period", None),
        ):
            if combo:
                combo.setStyleSheet(Styles.get_combobox_style())

        lbl_style = (
            f"{Styles.get_label_style(size=12, color=Styles.COLOR_TEXT_PRIMARY, weight=600)} "
            "border: none; background: transparent;"
        )
        for lbl in (
            getattr(self, "lbl_color", None),
            getattr(self, "lbl_format", None),
            getattr(self, "lbl_source", None),
            getattr(self, "lbl_period", None),
        ):
            if lbl:
                lbl.setStyleSheet(lbl_style)

        if hasattr(self, "scroll_area") and self.scroll_area:
            self.scroll_area.setStyleSheet(Styles.get_transparent_scroll_area_style())

        if hasattr(self, "drill_down_view") and self.drill_down_view:
            self.drill_down_view.refresh_styles()

        if self.current_stats:
            saved_insights = self.current_insights
            clear_layout(self.content_layout)
            self.show_dashboard(self.current_stats)
            if saved_insights and hasattr(self, "ai_coach_card") and self.ai_coach_card:
                self.ai_coach_card.set_insights(saved_insights)

    def refresh(self, _=None, force: bool = False):
        if not force and not self._needs_refresh and self.current_stats is not None:
            if hasattr(self, "stacked_widget") and self.stacked_widget:
                self.stacked_widget.setCurrentIndex(0)
                self.filter_bar.setVisible(True)
            return

        if hasattr(self, "stacked_widget") and self.stacked_widget:
            self.stacked_widget.setCurrentIndex(0)
            self.filter_bar.setVisible(True)

        clear_layout(self.content_layout)

        chesscom = self.config_manager.get("chesscom_username", "")
        lichess = self.config_manager.get("lichess_username", "")
        self.usernames = [u for u in [chesscom, lichess] if u]

        if not self.usernames:
            self.filter_bar.setVisible(False)
            self.show_setup_required()
            return

        self.games_data = self.history_manager.get_games_for_users(self.usernames)

        if not self.games_data:
            self.filter_bar.setVisible(False)
            self.show_no_data()
            return

        self.filter_bar.setVisible(True)
        self._filter_cache.clear()
        self.on_filter_changed()

    def on_filter_changed(self, _=None):
        if not self.games_data or not self.usernames:
            return

        color = self.combo_color.currentText()
        fmt = self.combo_format.currentText()
        source = self.combo_source.currentText()
        period = self.combo_period.currentText()
        filter_key = (color, fmt, source, period)

        # Serve from in-memory cache if data has not changed
        if not self._needs_refresh and filter_key in self._filter_cache:
            self.on_stats_ready(self._filter_cache[filter_key])
            return

        # Show Loading in content area
        clear_layout(self.content_layout)
        loading_widget = QWidget()
        l_layout = QVBoxLayout(loading_widget)
        l_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        spinner = QProgressBar()
        spinner.setRange(0, 0)  # Infinite loading
        spinner.setFixedWidth(200)
        spinner.setStyleSheet(Styles.get_progress_bar_style())
        l_layout.addWidget(spinner)

        lbl = QLabel("Filtering Statistics...")
        lbl.setStyleSheet(
            Styles.get_label_style(size=16, color=Styles.COLOR_TEXT_PRIMARY) + "; margin-top: 10px;"
        )
        l_layout.addWidget(lbl)

        # Stop existing worker safely
        self.stop_worker()

        self.stats_worker = StatsWorker(
            self.games_data,
            self.usernames,
            color_filter=color,
            format_filter=fmt,
            source_filter=source,
            date_filter=period,
        )
        self.stats_worker.finished.connect(
            lambda stats, fk=filter_key: self._on_worker_stats_ready(stats, fk)
        )
        self.stats_worker.start()

    def _on_worker_stats_ready(
        self, stats: dict[str, Any], filter_key: tuple[str, str, str, str]
    ) -> None:
        self._filter_cache[filter_key] = stats
        self.on_stats_ready(stats)

    def stop_worker(self):
        """Safely stops any active background stats worker."""
        if (
            hasattr(self, "stats_worker")
            and self.stats_worker is not None
            and self.stats_worker.isRunning()
        ):
            try:
                self.stats_worker.finished.disconnect()
            except (TypeError, RuntimeError):
                pass
            self.stats_worker.quit()
            self.stats_worker.wait(2000)

    def closeEvent(self, event):
        self.stop_worker()
        super().closeEvent(event)

    def reset_filters(self):
        self.combo_color.blockSignals(True)
        self.combo_format.blockSignals(True)
        self.combo_source.blockSignals(True)
        self.combo_period.blockSignals(True)

        self.combo_color.setCurrentText("All Colors")
        self.combo_format.setCurrentText("All Formats")
        self.combo_source.setCurrentText("All Sources")
        self.combo_period.setCurrentText("All Time")

        self.combo_color.blockSignals(False)
        self.combo_format.blockSignals(False)
        self.combo_source.blockSignals(False)
        self.combo_period.blockSignals(False)

        self.on_filter_changed()

    def on_stats_ready(self, stats):
        self._needs_refresh = False
        self.current_stats = stats
        total = stats.get("total", 0)
        if hasattr(self, "lbl_games_badge") and self.lbl_games_badge:
            self.lbl_games_badge.setText(f"{total} Games")

        if hasattr(self, "stacked_widget") and self.stacked_widget:
            self.stacked_widget.setCurrentIndex(0)
            self.filter_bar.setVisible(True)

        clear_layout(self.content_layout)
        if total == 0:
            self._show_message_view(
                "No Matching Games",
                "No analyzed games match your selected filters.\nTry resetting or widening your filter criteria.",
                "Reset Filters",
                self.reset_filters,
            )
        else:
            self.show_dashboard(stats)

    def show_setup_required(self):
        self._show_message_view(
            "Setup Required",
            "Please configure your Chess.com or Lichess.org username in Settings to view your stats.",
            "Go to Settings",
            self.go_to_settings,
        )

    def show_no_data(self):
        self._show_message_view(
            "No Games Found",
            f"No analyzed games found for users: {', '.join(self.usernames)}.\nAnalyze some games to see your stats!",
            None,
            None,
        )

    def _show_message_view(self, title_text, msg_text, btn_text, btn_callback):
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(20)

        lbl = QLabel(title_text)
        lbl.setStyleSheet(
            Styles.get_label_style(size=24, color=Styles.COLOR_TEXT_PRIMARY, bold=True)
        )
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl)

        msg = QLabel(msg_text)
        msg.setStyleSheet(Styles.get_label_style(size=16, color=Styles.COLOR_TEXT_SECONDARY))
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
        self.current_stats = stats
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setStyleSheet(Styles.get_transparent_scroll_area_style())
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        dashboard = QWidget()
        dashboard.setStyleSheet(f"background-color: {Styles.COLOR_BACKGROUND};")

        dashboard_layout = QVBoxLayout(dashboard)
        dashboard_layout.setSpacing(16)
        dashboard_layout.setContentsMargins(24, 16, 24, 24)

        # 1. Key Metrics Row - uses custom adaptive StatsLayout
        self.stats_container = QWidget()
        self.stats_layout = StatsLayout(self.stats_container, spacing=16)

        # Dynamic context subtitle based on active filters
        filters = stats.get("filter_applied", {})
        fmt_val = filters.get("format", "All Formats")
        period_val = filters.get("date", "All Time")
        color_val = filters.get("color", "All Colors")

        context_parts = []
        if fmt_val != "All Formats":
            context_parts.append(fmt_val)
        if color_val != "All Colors":
            context_parts.append(f"as {color_val}")
        if period_val != "All Time":
            context_parts.append(period_val)

        total_sub = " • ".join(context_parts) if context_parts else "All analyzed games"

        # Win rate subtitle with exact record counts
        wins = stats.get("wins", 0)
        draws = stats.get("draws", 0)
        losses = stats.get("losses", 0)
        win_sub = f"{wins}W • {draws}D • {losses}L"

        self.stats_layout.addWidget(StatCard("Total Games", str(stats["total"]), total_sub))
        self.stats_layout.addWidget(
            StatCard(
                "Win Rate",
                f"{stats['win_rate']:.1f}%",
                win_sub,
            )
        )
        self.stats_layout.addWidget(
            StatCard(
                "Avg Accuracy",
                f"{stats['avg_accuracy']:.1f}%",
                "Weighted harmonic mean",
            )
        )

        total_games = stats.get("total", 0)
        total_blunders = stats.get("detailed_quality_counts", {}).get(
            "Blunder", stats.get("quality_counts", {}).get("Blunder", 0)
        )
        bpg = (total_blunders / total_games) if total_games > 0 else 0.0
        blunders_card = StatCard(
            "Blunders / Game", f"{bpg:.1f}", "Average tactical errors", clickable=True
        )
        blunders_card.setToolTip("Click to inspect all blunder positions")
        blunders_card.clicked.connect(lambda: self._trigger_drill_down("blunders"))
        self.stats_layout.addWidget(blunders_card)

        clean_cnt = stats.get("clean_games", 0)
        clean_pct = stats.get("clean_games_pct", 0.0)
        clean_card = StatCard(
            "Clean Games",
            f"{clean_pct:.0f}%",
            f"{clean_cnt} zero-blunder matches",
            clickable=True,
        )
        clean_card.setToolTip("Click to inspect all clean games without blunders")
        clean_card.clicked.connect(lambda: self._trigger_drill_down("clean_games"))
        self.stats_layout.addWidget(clean_card)

        dashboard_layout.addWidget(self.stats_container)

        # 2. Performance & Form Row — Accuracy Trend & Phase Performance (50% / 50%)
        perf_row_widget = QWidget()
        perf_row_layout = QHBoxLayout(perf_row_widget)
        perf_row_layout.setSpacing(20)
        perf_row_layout.setContentsMargins(0, 0, 0, 0)

        self.accuracy_card = AccuracyTrendCard()
        self.accuracy_card.set_stats(stats)
        perf_row_layout.addWidget(self.accuracy_card)

        self.phase_card = PhasePerformanceCard()
        self.phase_card.set_stats(stats)
        perf_row_layout.addWidget(self.phase_card)

        dashboard_layout.addWidget(perf_row_widget)

        # 3. Distribution Row — Ending Distribution & Move Quality Distribution (50% / 50%)
        dist_row_widget = QWidget()
        dist_row_layout = QHBoxLayout(dist_row_widget)
        dist_row_layout.setSpacing(20)
        dist_row_layout.setContentsMargins(0, 0, 0, 0)

        self.ending_card = EndingDistributionCard()
        self.ending_card.set_stats(stats)
        dist_row_layout.addWidget(self.ending_card)

        self.quality_card = MoveQualityCard()
        self.quality_card.set_stats(stats)
        dist_row_layout.addWidget(self.quality_card)

        dashboard_layout.addWidget(dist_row_widget)

        # 4. Remaining cards in a 2-column masonry (shortest-column packing)
        self.charts_container = QWidget()
        self.charts_layout = MasonryLayout(
            self.charts_container, margin=0, spacing=20, min_col_width=400
        )

        self.time_card = TimeManagementCard()
        self.time_card.set_stats(stats)
        self.charts_layout.addWidget(self.time_card)

        self.hanging_card = HangingPiecesCard()
        self.hanging_card.set_stats(stats)
        self.hanging_card.drill_down_requested.connect(self._trigger_drill_down)
        self.charts_layout.addWidget(self.hanging_card)

        self.tactics_card = TacticalThemesCard()
        self.tactics_card.set_stats(stats)
        self.tactics_card.drill_down_requested.connect(self._trigger_drill_down)
        self.charts_layout.addWidget(self.tactics_card)

        self.advantage_card = AdvantageConversionCard()
        self.advantage_card.set_stats(stats)
        self.advantage_card.drill_down_requested.connect(self._trigger_drill_down)
        self.charts_layout.addWidget(self.advantage_card)

        self.brilliancy_card = BrilliancyHallCard()
        self.brilliancy_card.set_stats(stats)
        self.brilliancy_card.move_selected.connect(self._on_brilliancy_clicked)
        self.charts_layout.addWidget(self.brilliancy_card)

        self.openings_card = OpeningsListCard()
        self.openings_card.set_stats(stats)
        self.openings_card.drill_down_requested.connect(self._trigger_drill_down)
        self.charts_layout.addWidget(self.openings_card)

        self.ai_coach_card = AICoachCard(self.groq_service)
        self.ai_coach_card.set_stats(stats)
        if self.current_insights:
            self.ai_coach_card.set_insights(self.current_insights)

        # Connect AI card's signals to capture insights cache
        self.ai_coach_card.insights_generated.connect(self._store_insights_cache)
        self.ai_coach_card.btn_refresh_insights.clicked.connect(self._sync_insights_cache)
        self.charts_layout.addWidget(self.ai_coach_card)

        dashboard_layout.addWidget(self.charts_container)

        self.scroll_area.setWidget(dashboard)
        self.content_layout.addWidget(self.scroll_area)

    def _on_brilliancy_clicked(self, game_id: str, move_index: int):
        if not game_id or not self.history_manager:
            return
        game = self.history_manager.get_game_analysis(game_id)
        if game:
            self.game_selected.emit(game, move_index)

    def _trigger_drill_down(
        self,
        category: str,
        subcategory: str | None = None,
        custom_title: str | None = None,
        custom_subtitle: str | None = None,
    ):
        """Switches to drill-down view with matching occurrences from current_stats."""
        if not self.current_stats:
            return

        items = MetricsAggregator.get_drill_down_items(self.current_stats, category, subcategory)

        title = custom_title or self._get_drill_down_title(category, subcategory)
        if category in ("clean_games", "openings"):
            subtitle = custom_subtitle or f"Showing {len(items)} matching games"
        else:
            subtitle = custom_subtitle or f"Showing {len(items)} matching game positions"

        self.header_bar.setVisible(False)
        self.filter_bar.setVisible(False)
        self.drill_down_view.set_data(title, subtitle, items)
        self.stacked_widget.setCurrentIndex(1)

    def _on_drill_down_back(self):
        """Returns to the main performance dashboard."""
        self.header_bar.setVisible(True)
        self.filter_bar.setVisible(True)
        self.stacked_widget.setCurrentIndex(0)

    def _on_drill_down_position_selected(self, game_id: str, move_index: int):
        """Loads game into Analysis view at the specified move."""
        self._on_brilliancy_clicked(game_id, move_index)

    def _get_drill_down_title(self, category: str, subcategory: str | None) -> str:
        if category == "clean_games":
            return "Clean Games (Zero Blunders)"
        if category == "openings":
            return f"{subcategory} Games" if subcategory else "Opening Repertoire Games"
        if category == "blunders":
            return "Blunders & Tactical Oversights"
        if category == "hung_pieces":
            sub_name = (
                f" • {subcategory.capitalize()}s" if subcategory and subcategory != "all" else ""
            )
            return f"Dropped Pieces{sub_name}"
        if category == "opp_captured":
            sub_name = (
                f" • {subcategory.capitalize()}s" if subcategory and subcategory != "all" else ""
            )
            return f"Opponent Mistakes Punished{sub_name}"
        if category == "tactical_themes":
            sub_name = (
                f" • {subcategory.replace('_', ' ').title()}"
                if subcategory and subcategory != "all"
                else ""
            )
            return f"Tactical Patterns{sub_name}"
        if category == "advantage":
            adv_map = {
                "thrown_losses": "Thrown Losses (Lost Leads)",
                "squandered_draws": "Squandered Draws (Drawn Leads)",
                "comeback_wins": "Miracle Comeback Wins",
                "comeback_draws": "Resilient Comeback Draws",
            }
            return adv_map.get(subcategory or "", "Advantage Turning Points")
        return f"{category.replace('_', ' ').title()}"

    def _sync_insights_cache(self):
        if hasattr(self, "ai_coach_card") and self.ai_coach_card and self.ai_coach_card.worker:
            self.ai_coach_card.worker.finished.connect(self._store_insights_cache)

    def _store_insights_cache(self, insight_text):
        self.current_insights = insight_text
