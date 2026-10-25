import os
import sys

import chess
from PyQt6.QtCore import QPoint, Qt, QTimer, pyqtSignal
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
from src.backend.storage.historic_games import get_random_historic_position
from src.gui.analysis import CapturedPiecesWidget, GameControlsWidget
from src.gui.analysis.variation_graph import VariationGraph
from src.gui.analysis.variation_mode import VariationMode
from src.gui.board import Board, BoardGameHeader, BoardPanel
from src.gui.components.loading_widget import LoadingOverlay
from src.gui.components.sidebar import Sidebar
from src.gui.components.tour_manager import TourManager
from src.gui.components.tour_overlay import TourOverlay
from src.gui.components.transition_stack import FadedStackedWidget
from src.gui.components.welcome_panel import WelcomePanel
from src.gui.main_window.analysis_mixin import AnalysisMixin
from src.gui.main_window.game_loading_mixin import GameLoadingMixin
from src.gui.main_window.navigation_mixin import NavigationMixin
from src.gui.main_window.status_bar_mixin import StatusBarMixin
from src.gui.main_window.theme_mixin import ThemeMixin
from src.gui.main_window.tour_mixin import TourMixin
from src.gui.main_window.update_mixin import UpdateMixin
from src.gui.main_window.variation_mixin import VariationMixin
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
    VariationMixin,
    StatusBarMixin,
    ThemeMixin,
    TourMixin,
    UpdateMixin,
    QMainWindow,
):
    """Main application window composed of domain mixins."""

    # Emitted with the new ply index (-1 = start position) whenever the
    # analysis board moves, whether from a click, a button or a shortcut.
    move_changed = pyqtSignal(int)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Chess Analyzer Pro")
        self._apply_default_window_size()

        # State
        self.games = []
        self.current_game = None
        self._drop_highlight_active = False
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

    def _apply_default_window_size(self):
        """Pick a first-launch size from the user's actual screen."""
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            self.resize(1600, 900)
            return
        available = screen.availableGeometry()
        self.resize(
            max(1280, min(1920, int(available.width() * 0.85))),
            max(720, min(1080, int(available.height() * 0.85))),
        )

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

        # Stop the shared live-engine sessions cleanly
        if hasattr(self, "move_list_panel") and hasattr(self.move_list_panel, "session"):
            try:
                self.move_list_panel.session.shutdown()
            except Exception as e:
                logger.error(f"Failed to stop analysis live session: {e}")

        # Stop explorer's live engine session
        if hasattr(self, "explorer_view") and hasattr(self.explorer_view, "session"):
            try:
                self.explorer_view.session.shutdown()
            except Exception as e:
                logger.error(f"Failed to stop explorer live session: {e}")

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
        self.sidebar = Sidebar(self.config_manager)
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
        self.metrics_view.drill_down_opened.connect(self._on_drill_down_opened)
        self.metrics_view.drill_down_closed.connect(self._on_drill_down_closed)
        self.stack.addWidget(self.metrics_view)

        # --- Page 4: Settings View ---
        self.settings_view = SettingsView()
        self.settings_view.engine_path_changed.connect(self.update_engine_path)
        self.settings_view.engine_settings_changed.connect(self.apply_engine_settings)
        self.settings_view.llm_config_changed.connect(self.update_llm_config)
        self.settings_view.usernames_changed.connect(self.on_usernames_changed)
        self.settings_view.sidebar_prefs_changed.connect(self.sidebar.apply_preferences)
        self.settings_view.analysis_prefs_changed.connect(self.sync_analysis_prefs)
        self.stack.addWidget(self.settings_view)

        self.sidebar.set_active(0)
        self.stack.setCurrentIndex(0)

        self._setup_shortcuts()

        # Auto-start tour for the landing page (Analysis) on initial launch
        if hasattr(self, "tour_manager") and not self.tour_manager.has_seen_tour("landing"):
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

        # Workspace-only title. The landing hides the whole header bar, so this
        # never appears above the empty-state hero.
        self.title_lbl = QLabel("Analysis View")
        self.title_lbl.setStyleSheet(
            f"font-size: 20px; font-weight: bold; color: {Styles.COLOR_TEXT_PRIMARY}; background: transparent; border: none;"
        )
        header_layout.addWidget(self.title_lbl)

        self.game_info_label = QLabel("No Game Loaded")
        self.game_info_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        self.game_info_label.setMaximumWidth(520)
        self.game_info_label.setStyleSheet(
            f"font-size: 13px; font-weight: 600; color: {Styles.COLOR_TEXT_SECONDARY};"
            " padding: 0 12px; background: transparent; border: none;"
        )
        header_layout.addWidget(self.game_info_label)

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
        self.left_widget.setMinimumWidth(240)
        # Cap the pane so a wide drag does not leave the move columns mostly empty.
        self.left_widget.setMaximumWidth(420)
        self.left_widget.setStyleSheet(f"background-color: {Styles.COLOR_BACKGROUND};")
        left_layout = QVBoxLayout(self.left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        self.move_list_panel = MoveListPanel(self.engine_path, config_manager=self.config_manager)
        self.move_list_panel.move_selected.connect(self.on_move_selected)
        # Wire live-engine lifecycle to the status bar indicator
        self.move_list_panel.session.state_changed.connect(self._on_live_engine_state)
        left_layout.addWidget(self.move_list_panel)

        splitter.addWidget(self.left_widget)

        # Center: Board
        self.center_widget = QWidget()
        self.center_widget.setMinimumWidth(420)
        self.center_widget.setStyleSheet(f"background-color: {Styles.COLOR_BACKGROUND};")
        center_layout = QVBoxLayout(self.center_widget)
        self.center_layout = center_layout
        center_layout.setContentsMargins(6, 6, 6, 6)
        center_layout.setSpacing(6)

        self.captured_white = CapturedPiecesWidget(side="white")
        self.captured_black = CapturedPiecesWidget(side="black")
        self.captured_widget = self.captured_white

        self.board_widget = Board()
        self.board_panel = BoardPanel(
            self.board_widget, self.captured_white, self.captured_black
        )

        # Hero empty-state CTA card placed prominently above the board
        self.empty_state_cta = QFrame()
        self.empty_state_cta.setObjectName("EmptyStateCTA")
        self.empty_state_cta.setStyleSheet(Styles.get_empty_state_cta_style())
        cta_layout = QVBoxLayout(self.empty_state_cta)
        cta_layout.setContentsMargins(14, 10, 14, 10)
        cta_layout.setSpacing(8)

        hero_actions = QHBoxLayout()
        hero_actions.setSpacing(10)
        hero_actions.addStretch(1)

        self.btn_hero_load = create_button(
            "Load Game",
            style="primary",
            on_click=lambda: self.open_load_dialog(),
            icon_name="fa5s.folder-open",
        )
        self.btn_hero_load.setFixedSize(140, 38)
        self.btn_hero_load.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        hero_actions.addWidget(self.btn_hero_load)

        self.btn_hero_paste = create_button(
            "Paste PGN",
            style="secondary",
            on_click=self.paste_pgn_from_clipboard,
            icon_name="fa5s.paste",
        )
        self.btn_hero_paste.setFixedSize(130, 38)
        self.btn_hero_paste.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_hero_paste.setToolTip("Load PGN text from the clipboard")
        hero_actions.addWidget(self.btn_hero_paste)

        hero_actions.addStretch(1)
        cta_layout.addLayout(hero_actions)

        hint_row = QHBoxLayout()
        hint_row.setSpacing(8)
        hint_row.addStretch(1)

        self._hero_hint_default = "Drop a .pgn anywhere"
        self.lbl_hero_hint = QLabel(self._hero_hint_default)
        self.lbl_hero_hint.setStyleSheet(Styles.get_hero_hint_style())
        self.lbl_hero_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint_row.addWidget(self.lbl_hero_hint)

        open_key = "⌘O" if sys.platform == "darwin" else "Ctrl+O"
        paste_key = "⌘V" if sys.platform == "darwin" else "Ctrl+V"
        self.lbl_hero_keys = QLabel(f"{open_key} open   ·   {paste_key} paste")
        self.lbl_hero_keys.setStyleSheet(Styles.get_keycap_style())
        hint_row.addWidget(self.lbl_hero_keys)

        hint_row.addStretch(1)
        cta_layout.addLayout(hint_row)

        self.board_game_header = BoardGameHeader()
        self.board_game_header.setVisible(False)
        center_layout.addWidget(
            self.board_game_header, 0, Qt.AlignmentFlag.AlignHCenter
        )

        center_layout.addWidget(self.empty_state_cta, 0, Qt.AlignmentFlag.AlignCenter)
        center_layout.addWidget(self.board_panel, 1)

        self.variation_graph = VariationGraph()
        center_layout.addWidget(self.variation_graph)

        self.controls = GameControlsWidget()
        self.controls.first_clicked.connect(self.go_first)
        self.controls.prev_clicked.connect(self.go_prev)
        self.controls.next_clicked.connect(self.go_next)
        self.controls.last_clicked.connect(self.go_last)
        self.controls.flip_clicked.connect(self.flip_board)
        center_layout.addWidget(self.controls, 0, Qt.AlignmentFlag.AlignHCenter)
        self.board_widget.board_side_changed.connect(self._sync_board_chrome_widths)

        # ── Historic Game Info Bar (empty-state only, shown below board) ──────
        self.historic_info_bar = QFrame()
        self.historic_info_bar.setObjectName("HistoricInfoBar")
        self.historic_info_bar.setVisible(False)
        self.historic_info_bar.setStyleSheet(f"""
            QFrame#HistoricInfoBar {{
                background-color: {Styles.COLOR_SURFACE};
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 10px;
            }}
            QLabel {{ background: transparent; border: none; }}
        """)
        hib_outer = QVBoxLayout(self.historic_info_bar)
        hib_outer.setContentsMargins(16, 12, 16, 12)
        hib_outer.setSpacing(6)

        # Row 1: title + shuffle button
        hib_top = QHBoxLayout()
        hib_top.setSpacing(8)
        self._hib_title = QLabel()
        self._hib_title.setStyleSheet(
            f"font-size: 15px; font-weight: 700; color: {Styles.COLOR_TEXT_PRIMARY};"
        )
        self._hib_title.setWordWrap(False)
        hib_top.addWidget(self._hib_title)
        hib_top.addStretch()
        self.btn_hib_reveal = create_button(
            "Reveal Move",
            style="secondary",
            on_click=self._reveal_historic_move,
            icon_name="fa5s.eye",
        )
        self.btn_hib_reveal.setFixedHeight(30)
        self.btn_hib_reveal.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_hib_reveal.setToolTip("Play the famous move on the board")
        hib_top.addWidget(self.btn_hib_reveal)
        self.btn_hib_explore = create_button(
            "Explore Position",
            style="secondary",
            on_click=self._explore_historic_position,
            icon_name="fa5s.compass",
        )
        self.btn_hib_explore.setFixedHeight(30)
        self.btn_hib_explore.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_hib_explore.setToolTip("Open this position in the Opening Explorer")
        self.btn_hib_explore.hide()
        hib_top.addWidget(self.btn_hib_explore)
        self._btn_shuffle = create_button(
            "Next Gem",
            style="secondary",
            on_click=self._load_random_historic_position,
            icon_name="fa5s.random",
        )
        self._btn_shuffle.setFixedHeight(30)
        self._btn_shuffle.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        hib_top.addWidget(self._btn_shuffle)
        hib_outer.addLayout(hib_top)

        # Row 2: players / year / event
        self._hib_meta = QLabel()
        self._hib_meta.setStyleSheet(f"font-size: 12px; color: {Styles.COLOR_TEXT_SECONDARY};")
        hib_outer.addWidget(self._hib_meta)

        # Row 3: puzzle prompt (turn_desc)
        self._hib_hint = QLabel()
        self._hib_hint.setStyleSheet(
            f"font-size: 13px; font-weight: 500; color: {Styles.COLOR_ACCENT};"
        )
        self._hib_hint.setWordWrap(True)
        hib_outer.addWidget(self._hib_hint)

        # Row 4: celebration / blurb row (hidden until famous move is found)
        self._hib_celebration = QFrame()
        self._hib_celebration.setObjectName("HistoricCelebration")
        self._hib_celebration.setVisible(False)
        self._hib_celebration.setStyleSheet(f"""
            QFrame#HistoricCelebration {{
                background-color: {Styles.COLOR_SURFACE_LIGHT};
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 6px;
            }}
            QLabel {{ background: transparent; border: none; }}
        """)
        cel_layout = QHBoxLayout(self._hib_celebration)
        cel_layout.setContentsMargins(10, 8, 10, 8)
        cel_layout.setSpacing(8)
        self._hib_cel_icon = QLabel("✨")
        self._hib_cel_icon.setStyleSheet("font-size: 20px;")
        cel_layout.addWidget(self._hib_cel_icon)
        self._hib_cel_text = QLabel()
        self._hib_cel_text.setWordWrap(True)
        self._hib_cel_text.setStyleSheet(f"font-size: 12px; color: {Styles.COLOR_TEXT_PRIMARY};")
        cel_layout.addWidget(self._hib_cel_text, 1)
        hib_outer.addWidget(self._hib_celebration)

        center_layout.addWidget(self.historic_info_bar)

        # Wire board move_made to historic move detector
        self.board_widget.move_made.connect(self._on_board_move_made)

        splitter.addWidget(self.center_widget)

        # Right: Analysis
        self.analysis_panel = AnalysisPanel()
        self.analysis_panel.setMinimumWidth(300)
        if self.analysis_panel.layout:
            self.analysis_panel.layout.setContentsMargins(5, 5, 5, 5)
        self.analysis_panel.cache_toggled.connect(self.on_cache_toggled)
        self.move_list_panel.lines_updated.connect(self.analysis_panel.update_lines)
        self.analysis_panel.toggle_checkbox.toggled.connect(
            self.move_list_panel.set_engine_lines_enabled
        )
        self.analysis_panel.toggle_checkbox.toggled.connect(
            self.on_engine_lines_toggled
        )

        # Variation mode: makes the main board playable for "Show best move",
        # "Show refutation" and engine-line clicks without leaving the game.
        self.variation = VariationMode(
            self.board_widget, self.move_list_panel, self.variation_graph
        )
        self.variation.exited.connect(self._on_variation_exited)
        self.variation.position_changed.connect(self._on_variation_position_changed)
        self.variation.tree_changed.connect(self._on_variation_tree_changed)
        self.variation.message.connect(self._on_variation_message)
        self.analysis_panel.variation_requested.connect(self._on_variation_requested)
        self.move_list_panel.variation_requested.connect(self._open_variation_tree_for_index)

        splitter.addWidget(self.analysis_panel)

        # Right: Welcome & Project Hub (displayed on empty state when no game is loaded)
        self.welcome_panel = WelcomePanel(parent=self)
        splitter.addWidget(self.welcome_panel)

        splitter.setStretchFactor(0, 25)
        splitter.setStretchFactor(1, 45)
        splitter.setStretchFactor(2, 30)
        splitter.setStretchFactor(3, 0)

        self._update_analysis_view_mode(has_game=self.current_game is not None)

    def showEvent(self, event):
        super().showEvent(event)
        if not self.current_game and hasattr(self, "splitter"):
            total_w = self.splitter.width()
            if total_w > 100:
                left_w = int(total_w * 0.60)
                right_w = total_w - left_w
                self.splitter.setSizes([0, left_w, 0, right_w])
            # Load a random historic position onto the landing board
            QTimer.singleShot(0, self._load_random_historic_position)

    # ── Historic landing board helpers ────────────────────────────────────

    def _load_random_historic_position(self):
        """Pick a random position from the curated historic collection and load it onto the board."""
        # Avoid repeating the same game back-to-back
        existing = getattr(self, "_current_historic", None)
        pos = get_random_historic_position()
        if existing and pos.id == existing.id:
            pos = get_random_historic_position()

        self._current_historic = pos
        self._historic_move_found = False

        if hasattr(self, "board_widget"):
            self.board_widget.load_fen(pos.fen, pos.flipped)

        if hasattr(self, "_hib_title"):
            self._hib_title.setText(f"\u2736  {pos.title}  \u00b7  {pos.year}")
        if hasattr(self, "_hib_meta"):
            self._hib_meta.setText(f"{pos.white}  vs  {pos.black}   \u00b7   {pos.event}")
        if hasattr(self, "_hib_hint"):
            self._hib_hint.setText(pos.turn_desc)
        if hasattr(self, "_hib_celebration"):
            self._hib_celebration.setVisible(False)
        if hasattr(self, "btn_hib_reveal"):
            self.btn_hib_reveal.setEnabled(True)
            self.btn_hib_reveal.setText("  Reveal Move")
            self.btn_hib_reveal.show()
        if hasattr(self, "btn_hib_explore"):
            self.btn_hib_explore.hide()
        if hasattr(self, "historic_info_bar") and not self.current_game:
            self.historic_info_bar.setVisible(True)

    def _reveal_historic_move(self):
        """Play the curated historic move so the landing puzzle is discoverable."""
        pos = getattr(self, "_current_historic", None)
        if pos is None or getattr(self, "_historic_move_found", False):
            return

        try:
            board = chess.Board(pos.fen)
            board.push(board.parse_san(pos.famous_move))
        except (ValueError, AssertionError) as e:
            logger.debug(f"Could not reveal historic move: {e}")
            return

        self.board_widget.load_fen(board.fen(), pos.flipped)
        self._celebrate_historic_move(pos)

    def _explore_historic_position(self):
        """Open the revealed landing position in the Explorer page."""
        self.sidebar.set_active(1)
        self.switch_page(1)
        self.explorer_view.load_fen(self.board_widget.board.fen())

    def _on_board_move_made(self, new_fen: str):
        """Called every time the user makes a move on the interactive landing board.
        Checks whether the move matches the historic famous move and celebrates if so.
        """
        if self.current_game:
            return
        pos = getattr(self, "_current_historic", None)
        if pos is None or getattr(self, "_historic_move_found", False):
            return

        try:
            ref_board = chess.Board(pos.fen)
            ref_move = ref_board.parse_san(pos.famous_move)
            ref_board.push(ref_move)
            # Compare piece placement, active color, castling, en-passant (first 4 FEN fields)
            if new_fen.split()[:4] == ref_board.fen().split()[:4]:
                self._historic_move_found = True
                self._celebrate_historic_move(pos)
        except Exception as e:
            logger.debug(f"Historic move check error: {e}")

    def _celebrate_historic_move(self, pos):
        """Reveal the historical blurb with an accent highlight when the famous move is found."""
        if not hasattr(self, "_hib_celebration"):
            return
        self._historic_move_found = True
        self._hib_cel_text.setText(f"<b>{pos.famous_move}!</b> — {pos.blurb}")
        if hasattr(self, "btn_hib_reveal"):
            self.btn_hib_reveal.setEnabled(False)
            self.btn_hib_reveal.hide()
        if hasattr(self, "btn_hib_explore"):
            self.btn_hib_explore.show()
        self._hib_celebration.setStyleSheet(f"""
            QFrame#HistoricCelebration {{
                background-color: {Styles.COLOR_SURFACE_LIGHT};
                border: 1px solid {Styles.COLOR_ACCENT};
                border-radius: 6px;
            }}
            QLabel {{ background: transparent; border: none; }}
        """)
        self._hib_celebration.setVisible(True)

    def resizeEvent(self, event):
        if hasattr(self, "loading_overlay"):
            self.loading_overlay.resize(self.size())
        if hasattr(self, "tour_overlay"):
            self.tour_overlay.setGeometry(self.rect())
        super().resizeEvent(event)
