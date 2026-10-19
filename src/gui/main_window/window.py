import os

from PyQt6.QtCore import QPoint, Qt, QTimer
from PyQt6.QtGui import QGuiApplication, QIcon
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from src.backend.analysis.analyzer import Analyzer
from src.backend.analysis.engine import EngineManager, resolve_engine_path
from src.backend.storage.game_history import GameHistoryManager
from src.gui.analysis import CapturedPiecesWidget, GameControlsWidget
from src.gui.board import BoardWidget
from src.gui.components.loading_widget import LoadingOverlay
from src.gui.components.sidebar import Sidebar
from src.gui.components.tour_manager import TourManager
from src.gui.components.tour_overlay import TourOverlay
from src.gui.components.transition_stack import FadedStackedWidget
from src.gui.main_window.analysis_mixin import AnalysisMixin
from src.gui.main_window.game_loading_mixin import GameLoadingMixin
from src.gui.main_window.navigation_mixin import NavigationMixin
from src.gui.main_window.status_bar_mixin import StatusBarMixin
from src.gui.main_window.theme_mixin import ThemeMixin
from src.gui.main_window.tour_mixin import TourMixin
from src.gui.main_window.update_mixin import UpdateMixin
from src.gui.styles import Styles
from src.gui.theme import ThemeManager
from src.gui.utils.gui_utils import create_button
from src.gui.views import HistoryView, SettingsView
from src.gui.views.analysis_view import AnalysisPanel, MoveListPanel
from src.gui.views.explorer_view import ExplorerView
from src.gui.views.metrics_view import MetricsWidget
from src.utils.config import ConfigManager
from src.utils.logger import logger
from src.utils.path_utils import get_resource_path
from src.utils.resources import ResourceManager


def _stop_thread(thread, timeout: int | None = None, signals: tuple = ()):
    """Safely disconnect signals, quit, and wait for a QThread to terminate."""
    if thread is not None and thread.isRunning():
        for sig in signals:
            try:
                sig.disconnect()
            except (TypeError, RuntimeError):
                pass
        thread.quit()
        if timeout is not None:
            thread.wait(timeout)
        else:
            thread.wait()


class MainWindow(
    NavigationMixin,
    AnalysisMixin,
    GameLoadingMixin,
    StatusBarMixin,
    ThemeMixin,
    TourMixin,
    UpdateMixin,
    QMainWindow,
):
    """Main application window composed of domain mixins."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Chess Analyzer Pro")
        self.resize(1600, 900)

        # State
        self.games = []
        self.current_game = None
        self.config_manager = ConfigManager()
        resolved = resolve_engine_path(self.config_manager)
        self.engine_path = resolved or self.config_manager.get("engine_path", "stockfish")
        self.analyzer = Analyzer(
            EngineManager(self.engine_path, config_manager=self.config_manager)
        )
        self.history_manager = GameHistoryManager()
        self.resource_manager = ResourceManager()
        self.tour_manager = TourManager(config_manager=self.config_manager)

        # Restore the last known window geometry, if any.
        self._restore_window_state()

        # Set Window Icon
        icon_path = get_resource_path(os.path.join("assets", "images", "logo.png"))
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        # Initialize ThemeManager
        self._theme_manager = ThemeManager(parent=self)

        saved_theme_mode = self.config_manager.get("theme_mode", "system")
        ThemeManager.set_theme_mode(saved_theme_mode)

        saved_accent = self.config_manager.get("accent_color")
        saved_accent_mode = self.config_manager.get("accent_mode", "system")
        if saved_accent_mode == "system":
            ThemeManager.set_accent_mode("system")
        elif saved_accent:
            ThemeManager.set_accent(saved_accent)

        self._theme_manager.theme_changed.connect(self._on_theme_changed)
        self._theme_manager.accent_changed.connect(self._on_accent_changed)

        # UI Setup
        self.setup_ui()
        self.setAcceptDrops(True)

        # Apply Theme
        self.refresh_theme()

        # Tour overlay — marks the page seen when the tour finishes/closes
        self.tour_overlay = TourOverlay(
            self,
            self.tour_manager,
            on_finished=self._on_tour_finished,
        )
        self.tour_overlay.hide()

        # Style the status bar itself
        self.statusBar().setStyleSheet(f"""
            QStatusBar {{
                background-color: {Styles.COLOR_BACKGROUND};
                border-top: 1px solid {Styles.COLOR_BORDER};
            }}
            QStatusBar QLabel {{
                background: transparent;
            }}
        """)

        self._engine_pill = QLabel()
        self._engine_pill.setStyleSheet(
            "font-size: 12px; font-weight: 600; padding: 0 6px; background: transparent;"
        )
        self.statusBar().addWidget(self._engine_pill)

        # Thin separator
        sep = QLabel("│")
        sep.setStyleSheet(f"color: {Styles.COLOR_BORDER}; padding: 0 4px; background: transparent;")
        self.statusBar().addWidget(sep)

        self._status_lbl = QLabel("Ready")
        self._status_lbl.setStyleSheet(
            f"font-size: 12px; color: {Styles.COLOR_TEXT_SECONDARY}; background: transparent;"
        )
        self.statusBar().addWidget(self._status_lbl)

        # Spinner timer for Calculating animation
        self._spinner_frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        self._spinner_idx = 0
        self._spinner_timer = QTimer(self)
        self._spinner_timer.timeout.connect(self._tick_spinner)

        self._refresh_engine_status()

        # Overlay
        self.loading_overlay = LoadingOverlay(self)
        self.loading_overlay.resize(self.size())

        # Check for updates (in background)
        self.check_for_updates()

    # ------------------------------------------------------------------
    # Window geometry persistence
    # ------------------------------------------------------------------

    def _restore_window_state(self):
        """Restore the main window's last-known position and size."""
        state = self.config_manager.get("window_state") or {}
        try:
            x = state.get("x")
            y = state.get("y")
            w = state.get("width")
            h = state.get("height")
        except AttributeError:
            return

        def _coerce(value):
            if isinstance(value, bool):
                return None
            if isinstance(value, (int, float)):
                return int(value)
            return None

        width = _coerce(w) or None
        height = _coerce(h) or None
        pos_x = _coerce(x)
        pos_y = _coerce(y)

        if width and height:
            self.resize(width, height)
        if pos_x is not None and pos_y is not None:
            target = self.frameGeometry()
            target.moveTopLeft(QPoint(pos_x, pos_y))
            on_screen = any(
                screen.availableGeometry().intersects(target)
                for screen in QGuiApplication.screens()
            )
            if on_screen:
                self.move(pos_x, pos_y)

    def _save_window_state(self):
        """Persist the current window geometry to the user config."""
        frame = self.frameGeometry()
        self.config_manager.set(
            "window_state",
            {
                "x": frame.x(),
                "y": frame.y(),
                "width": self.width(),
                "height": self.height(),
            },
        )

    def closeEvent(self, event):
        """Save window geometry and cleanly shut down background workers on close."""
        try:
            self._save_window_state()
        except Exception as e:  # pragma: no cover - defensive
            logger.error(f"Failed to save window state: {e}")

        # Stop live analysis worker thread cleanly
        if hasattr(self, "move_list_panel") and hasattr(self.move_list_panel, "live_worker"):
            try:
                self.move_list_panel.live_worker.stop()
            except Exception as e:
                logger.error(f"Failed to stop analysis live worker: {e}")

        # Stop explorer's live analysis worker
        if hasattr(self, "explorer_view") and hasattr(self.explorer_view, "live_worker"):
            try:
                self.explorer_view.live_worker.stop()
            except Exception as e:
                logger.error(f"Failed to stop explorer live worker: {e}")

        # Stop full analysis worker if it is running
        if hasattr(self, "worker") and self.worker and self.worker.isRunning():
            try:
                self.worker.stop()
                self.worker.wait()
            except Exception as e:
                logger.error(f"Failed to stop full analysis worker: {e}")

        # Stop AI Coach summary thread if running
        if hasattr(self, "analysis_panel") and self.analysis_panel:
            st = getattr(self.analysis_panel, "summary_thread", None)
            if st is not None:
                _stop_thread(st, signals=(getattr(st, "finished", None),))

        # Stop metrics workers if running
        if hasattr(self, "metrics_view") and self.metrics_view:
            sw = getattr(self.metrics_view, "stats_worker", None)
            if sw is not None:
                _stop_thread(sw, signals=(getattr(sw, "finished", None),))
            mw = getattr(self.metrics_view, "worker", None)
            if mw is not None:
                _stop_thread(
                    mw, signals=(getattr(mw, "finished", None), getattr(mw, "error", None))
                )

        # Stop SettingsView test worker if running
        if hasattr(self, "settings_view") and self.settings_view:
            prev = getattr(self.settings_view, "_test_worker", None)
            if prev is not None:
                _stop_thread(prev, timeout=1000, signals=(getattr(prev, "done", None),))

        # Stop update worker and timer if running
        if hasattr(self, "_update_timer") and self._update_timer.isActive():
            self._update_timer.stop()

        if hasattr(self, "update_worker") and self.update_worker:
            if hasattr(self.update_worker, "cancel"):
                self.update_worker.cancel()
            _stop_thread(
                self.update_worker,
                timeout=1000,
                signals=(getattr(self.update_worker, "update_checked", None),),
            )

        # Clean up analyzer and database resources
        if hasattr(self, "analyzer") and self.analyzer:
            try:
                self.analyzer.close()
            except Exception as e:
                logger.error(f"Failed to close analyzer: {e}")

        # Clean up explorer view databases
        if hasattr(self, "explorer_view") and self.explorer_view:
            try:
                if hasattr(self.explorer_view, "opening_db") and self.explorer_view.opening_db:
                    self.explorer_view.opening_db.close()
                if (
                    hasattr(self.explorer_view, "polyglot_manager")
                    and self.explorer_view.polyglot_manager
                ):
                    self.explorer_view.polyglot_manager.close()
            except Exception as e:
                logger.error(f"Failed to close explorer view resources: {e}")

        # Checkpoint SQLite database WAL sidecar files on exit
        try:
            GameHistoryManager().checkpoint()
        except Exception as e:
            logger.debug(f"Failed to checkpoint game history on exit: {e}")

        super().closeEvent(event)

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Sidebar
        self.sidebar = Sidebar()
        self.sidebar.page_changed.connect(self.switch_page)
        main_layout.addWidget(self.sidebar)

        # Stacked Widget for Pages
        self.stack = FadedStackedWidget()
        main_layout.addWidget(self.stack)

        # --- Page 0: Analysis View ---
        self.analysis_page = QWidget()
        self.setup_analysis_page(self.analysis_page)
        self.stack.addWidget(self.analysis_page)

        # --- Page 1: Explorer View ---
        self.explorer_view = ExplorerView(self.config_manager)
        self.stack.addWidget(self.explorer_view)

        # --- Page 2: History View ---
        self.history_view = HistoryView(self.config_manager)
        self.history_view.game_selected.connect(self.load_game_from_history)
        self.history_view.game_action_requested.connect(self.on_game_action_requested)
        self.history_view.game_deleted.connect(self.on_history_changed)
        self.history_view.games_imported.connect(self.on_history_changed)
        self.history_view.history_cleared.connect(self.on_history_changed)
        self.stack.addWidget(self.history_view)

        # --- Page 3: Metrics View ---
        self.metrics_view = MetricsWidget(self.config_manager, self.history_manager)
        self.metrics_view.request_settings.connect(
            lambda: (self.sidebar.set_active(4), self.switch_page(4))
        )
        self.metrics_view.game_selected.connect(self.load_game_from_metrics)
        self.stack.addWidget(self.metrics_view)

        # --- Page 4: Settings View ---
        self.settings_view = SettingsView()
        self.settings_view.engine_path_changed.connect(self.update_engine_path)
        self.settings_view.engine_settings_changed.connect(self.apply_engine_settings)
        self.settings_view.llm_config_changed.connect(self.update_llm_config)
        self.settings_view.usernames_changed.connect(self.on_usernames_changed)
        self.stack.addWidget(self.settings_view)

        self.sidebar.set_active(0)
        self.stack.setCurrentIndex(0)

        self._setup_shortcuts()

        # Auto-start tour for the landing page (Analysis) on initial launch
        if hasattr(self, "tour_manager") and not self.tour_manager.has_seen_tour(0):
            QTimer.singleShot(600, lambda: self._auto_start_tour(0))

    def setup_analysis_page(self, parent_widget):
        main_layout = QVBoxLayout(parent_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Header Bar Container for Chess Analysis
        self.analysis_header_bar = QFrame()
        self.analysis_header_bar.setStyleSheet(f"""
            QFrame {{
                background-color: {Styles.COLOR_BACKGROUND};
                border-bottom: 1px solid {Styles.COLOR_BORDER};
            }}
            QFrame QLabel {{
                background: transparent;
            }}
        """)
        header_layout = QHBoxLayout(self.analysis_header_bar)
        header_layout.setContentsMargins(40, 12, 40, 12)

        # Title
        self.title_lbl = QLabel("Chess Analysis")
        self.title_lbl.setStyleSheet(
            f"font-size: 24px; font-weight: bold; color: {Styles.COLOR_TEXT_PRIMARY}; background: transparent; border: none;"
        )
        header_layout.addWidget(self.title_lbl)

        header_layout.addStretch()

        # Explore Button
        self.btn_explore = create_button(
            "Explore from here",
            style="secondary",
            on_click=self.explore_current_position,
            icon_name="fa5s.compass",
        )
        self.btn_explore.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        header_layout.addWidget(self.btn_explore)

        # Load Game Button
        self.btn_load = create_button(
            "Load Game",
            style="secondary",
            on_click=lambda: self.open_load_dialog(),
            icon_name="fa5s.folder-open",
        )
        self.btn_load.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        header_layout.addWidget(self.btn_load)

        # Analyze Game Button
        self.btn_analyze = create_button(
            "Analyze Game",
            style="primary",
            on_click=lambda: self.start_analysis(),
            icon_name="fa5s.play",
        )
        header_layout.addWidget(self.btn_analyze)

        main_layout.addWidget(self.analysis_header_bar)

        # Splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter = splitter
        splitter.setHandleWidth(2)
        splitter.setStyleSheet(f"""
            QSplitter {{
                background-color: {Styles.COLOR_BACKGROUND};
            }}
            QSplitter::handle {{
                background-color: {Styles.COLOR_BORDER};
            }}
        """)
        main_layout.addWidget(splitter, 1)

        # Left: Move List
        self.left_widget = QWidget()
        self.left_widget.setStyleSheet(f"background-color: {Styles.COLOR_BACKGROUND};")
        left_layout = QVBoxLayout(self.left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        self.move_list_panel = MoveListPanel(self.engine_path, config_manager=self.config_manager)
        self.move_list_panel.move_selected.connect(self.on_move_selected)
        # Wire live-engine thinking signals to the status bar indicator
        self.move_list_panel.live_worker.thinking_started.connect(self._on_live_thinking_started)
        self.move_list_panel.live_worker.thinking_stopped.connect(self._on_live_thinking_stopped)
        left_layout.addWidget(self.move_list_panel)

        splitter.addWidget(self.left_widget)

        # Center: Board
        self.center_widget = QWidget()
        self.center_widget.setStyleSheet(f"background-color: {Styles.COLOR_BACKGROUND};")
        center_layout = QVBoxLayout(self.center_widget)
        self.center_layout = center_layout
        center_layout.setContentsMargins(10, 10, 10, 10)
        center_layout.setSpacing(10)

        self.game_info_label = QLabel("No Game Loaded")
        self.game_info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.game_info_label.setStyleSheet(
            f"font-size: 16px; font-weight: bold; color: {Styles.COLOR_TEXT_PRIMARY}; padding: 5px; background: transparent;"
        )
        center_layout.addWidget(self.game_info_label)

        self.captured_white = CapturedPiecesWidget(side="white")
        self.captured_black = CapturedPiecesWidget(side="black")
        self.captured_widget = self.captured_white

        self.board_widget = BoardWidget()
        center_layout.addWidget(self.captured_black)
        center_layout.addWidget(self.board_widget, 1)
        center_layout.addWidget(self.captured_white)

        self.controls = GameControlsWidget()
        self.controls.first_clicked.connect(self.go_first)
        self.controls.prev_clicked.connect(self.go_prev)
        self.controls.next_clicked.connect(self.go_next)
        self.controls.last_clicked.connect(self.go_last)
        self.controls.flip_clicked.connect(self.flip_board)
        center_layout.addWidget(self.controls)

        # Hero empty-state CTA below the board
        self.empty_state_cta = QFrame()
        self.empty_state_cta.setObjectName("EmptyStateCTA")
        cta_layout = QVBoxLayout(self.empty_state_cta)
        cta_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cta_layout.setContentsMargins(0, 10, 0, 14)
        cta_layout.setSpacing(8)

        self.btn_hero_load = create_button(
            "Load Game",
            style="primary",
            on_click=lambda: self.open_load_dialog(),
            icon_name="fa5s.folder-open",
        )
        self.btn_hero_load.setFixedSize(160, 42)
        self.btn_hero_load.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        cta_layout.addWidget(self.btn_hero_load, 0, Qt.AlignmentFlag.AlignCenter)

        self.lbl_hero_hint = QLabel("Drop a .pgn file anywhere or press Ctrl+V to paste")
        self.lbl_hero_hint.setStyleSheet(
            f"font-size: 13px; color: {Styles.COLOR_TEXT_MUTED}; background: transparent;"
        )
        self.lbl_hero_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cta_layout.addWidget(self.lbl_hero_hint, 0, Qt.AlignmentFlag.AlignCenter)

        center_layout.addWidget(self.empty_state_cta)

        splitter.addWidget(self.center_widget)

        # Right: Analysis
        self.analysis_panel = AnalysisPanel()
        if self.analysis_panel.layout:
            self.analysis_panel.layout.setContentsMargins(5, 5, 5, 5)
        self.analysis_panel.cache_toggled.connect(self.on_cache_toggled)
        self.move_list_panel.lines_updated.connect(self.analysis_panel.update_lines)
        self.analysis_panel.toggle_checkbox.toggled.connect(
            self.move_list_panel.set_engine_lines_enabled
        )

        splitter.addWidget(self.analysis_panel)
        splitter.setSizes([250, 630, 320])
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        splitter.setStretchFactor(2, 1)

        self._update_analysis_view_mode(has_game=self.current_game is not None)

    def resizeEvent(self, event):
        if hasattr(self, "loading_overlay"):
            self.loading_overlay.resize(self.size())
        if hasattr(self, "tour_overlay"):
            self.tour_overlay.setGeometry(self.rect())
        super().resizeEvent(event)
