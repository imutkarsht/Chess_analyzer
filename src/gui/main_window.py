import os
import json
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QSplitter, QFileDialog, QMenuBar,
                             QStatusBar, QMessageBox, QInputDialog, QDialog,
                             QListWidget, QListWidgetItem, QPushButton, QLineEdit, QLabel, QStackedWidget, QTextEdit, QFrame)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QAction, QIcon, QShortcut, QKeySequence
from PyQt6.QtWidgets import QMenu
import shutil

from src.gui.board import BoardWidget  # From board package
from src.gui.views.analysis_view import MoveListPanel, AnalysisPanel
from src.gui.analysis import CapturedPiecesWidget, GameControlsWidget  # From analysis package
from src.gui.views.metrics_view import MetricsWidget
from src.gui.analysis.analysis_worker import AnalysisWorker
from src.gui.components.sidebar import Sidebar
from src.gui.views.explorer_view import ExplorerView
from src.gui.views import HistoryView, SettingsView  # From views package
from src.backend.storage.pgn_parser import PGNParser
from src.backend.analysis.analyzer import Analyzer
from src.utils.resources import ResourceManager
from src.utils.logger import logger
from src.utils.config import ConfigManager
from src.backend.analysis.engine import EngineManager
from src.backend.api.chess_com_api import ChessComAPI
from src.backend.api.lichess_api import LichessAPI
from src.gui.styles import Styles
from src.gui.utils.gui_utils import create_button
from src.backend.storage.models import MoveAnalysis, GameAnalysis, GameMetadata
from src.backend.storage.game_history import GameHistoryManager
from src.utils.path_utils import get_resource_path
from src.gui.components.loading_widget import LoadingOverlay



class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Chess Analyzer Pro")
        self.resize(1600, 900)

        # State
        self.games = []
        self.current_game = None
        self.config_manager = ConfigManager()
        self.engine_path = self.config_manager.get("engine_path", "stockfish")
        self.analyzer = Analyzer(
            EngineManager(self.engine_path, config_manager=self.config_manager)
        )
        self.history_manager = GameHistoryManager()
        self.resource_manager = ResourceManager()

        # Restore the last known window geometry, if any. Done before
        # setup_ui() so child layouts see the real size during their
        # first showEvent pass.
        self._restore_window_state()
        
        # Set Window Icon
        icon_path = get_resource_path(os.path.join("assets", "images", "logo.png"))
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        # Load Configured Theme
        saved_accent = self.config_manager.get("accent_color")
        if saved_accent:
            Styles.set_accent_color(saved_accent)

        # UI Setup
        self.setup_ui()
        
        # Apply Theme
        self.setStyleSheet(Styles.get_theme())

        # Engine status pill + analysis status label — left side of status bar
        # Note: background + border-radius on QLabel inside QStatusBar renders as a
        # plain rectangle in Qt — use colored text only for a clean look.
        self._engine_pill = QLabel()
        self._engine_pill.setStyleSheet("font-size: 12px; font-weight: 600; padding: 0 6px;")
        self.statusBar().addWidget(self._engine_pill)

        # Thin separator
        sep = QLabel("│")
        sep.setStyleSheet(f"color: {Styles.COLOR_BORDER}; padding: 0 4px;")
        self.statusBar().addWidget(sep)

        self._status_lbl = QLabel("Ready")
        self._status_lbl.setStyleSheet(f"font-size: 12px; color: {Styles.COLOR_TEXT_SECONDARY};")
        self.statusBar().addWidget(self._status_lbl)

        # Spinner timer for Calculating animation
        self._spinner_frames = ["⠋","⠙","⠹","⠸","⠼","⠴","⠦","⠧","⠇","⠏"]
        self._spinner_idx = 0
        self._spinner_timer = QTimer(self)
        self._spinner_timer.timeout.connect(self._tick_spinner)

        self._refresh_engine_status()
        
        # Overlay
        self.loading_overlay = LoadingOverlay(self)
        self.loading_overlay.resize(self.size())
        
        # Check for updates (in background)
        self.check_for_updates()

    def check_for_updates(self):
        """Start background update check after a delay (max once per day)."""
        from PyQt6.QtCore import QTimer
        from datetime import datetime, timedelta
        
        # Check if we already checked today
        last_check = self.config_manager.get("last_update_check", "")
        today = datetime.now().strftime("%Y-%m-%d")
        
        if last_check == today:
            # Already checked today, skip
            return
        
        # Save today as last check date
        self.config_manager.set("last_update_check", today)
        
        # Delay update check by 2 seconds to ensure splash is gone
        QTimer.singleShot(2000, self._start_update_check)
    
    def _start_update_check(self):
        """Actually start the update check."""
        from src.backend.updater.update_checker import UpdateCheckerWorker
        
        self.update_worker = UpdateCheckerWorker()
        self.update_worker.update_checked.connect(self.on_update_checked)
        self.update_worker.start()
    
    def on_update_checked(self, update_info):
        """Handle update check result."""
        if update_info.available:
            from .dialogs import UpdateNotificationDialog
            dialog = UpdateNotificationDialog(update_info, self)
            dialog.exec()

    # ------------------------------------------------------------------
    # Window geometry persistence
    # ------------------------------------------------------------------

    def _restore_window_state(self):
        """Restore the main window's last-known position and size.

        Values come from ``config["window_state"]``. Any field that is
        missing, non-numeric, or would push the window off-screen is
        silently ignored so the user can never end up with a window
        they cannot reach.
        """
        from PyQt6.QtCore import QPoint
        from PyQt6.QtGui import QGuiApplication

        state = self.config_manager.get("window_state") or {}
        try:
            x = state.get("x")
            y = state.get("y")
            w = state.get("width")
            h = state.get("height")
        except AttributeError:
            return

        # Reject booleans explicitly: in Python, isinstance(True, int) is True,
        # and `True` would be silently coerced to `1`. The config should only
        # ever hold real numbers for window geometry, so anything else is
        # treated as "missing" and ignored.
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
            # Only apply the position if it intersects at least one
            # available screen — otherwise the user could end up with
            # an unreachable window after a monitor change.
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
        self.config_manager.set("window_state", {
            "x": frame.x(),
            "y": frame.y(),
            "width": self.width(),
            "height": self.height(),
        })

    def closeEvent(self, event):
        """Save window geometry on close so the next launch can restore it."""
        try:
            self._save_window_state()
        except Exception as e:  # pragma: no cover - defensive
            logger.error(f"Failed to save window state: {e}")
            
        # Stop live analysis worker thread cleanly
        if hasattr(self, 'move_list_panel') and hasattr(self.move_list_panel, 'live_worker'):
            try:
                self.move_list_panel.live_worker.stop()
            except Exception as e:
                logger.error(f"Failed to stop analysis live worker: {e}")

        # Stop explorer's live analysis worker
        if hasattr(self, 'explorer_view') and hasattr(self.explorer_view, 'live_worker'):
            try:
                self.explorer_view.live_worker.stop()
            except Exception as e:
                logger.error(f"Failed to stop explorer live worker: {e}")

        # Stop full analysis worker if it is running
        if hasattr(self, 'worker') and self.worker and self.worker.isRunning():
            try:
                self.worker.stop()
                self.worker.wait()
            except Exception as e:
                logger.error(f"Failed to stop full analysis worker: {e}")

        # Stop AI Coach summary thread if running
        if hasattr(self, 'analysis_panel') and self.analysis_panel:
            if hasattr(self.analysis_panel, 'summary_thread') and self.analysis_panel.summary_thread and self.analysis_panel.summary_thread.isRunning():
                try:
                    self.analysis_panel.summary_thread.finished.disconnect()
                except (TypeError, RuntimeError):
                    pass
                self.analysis_panel.summary_thread.quit()
                self.analysis_panel.summary_thread.wait()

        # Stop metrics workers if running
        if hasattr(self, 'metrics_view') and self.metrics_view:
            if hasattr(self.metrics_view, 'stats_worker') and self.metrics_view.stats_worker and self.metrics_view.stats_worker.isRunning():
                try:
                    self.metrics_view.stats_worker.finished.disconnect()
                except (TypeError, RuntimeError):
                    pass
                self.metrics_view.stats_worker.quit()
                self.metrics_view.stats_worker.wait()
            if hasattr(self.metrics_view, 'worker') and self.metrics_view.worker and self.metrics_view.worker.isRunning():
                try:
                    self.metrics_view.worker.finished.disconnect()
                    self.metrics_view.worker.error.disconnect()
                except (TypeError, RuntimeError):
                    pass
                self.metrics_view.worker.quit()
                self.metrics_view.worker.wait()

        # Stop SettingsView test worker if running
        if hasattr(self, 'settings_view') and self.settings_view:
            prev = getattr(self.settings_view, "_test_worker", None)
            if prev is not None and prev.isRunning():
                try:
                    prev.done.disconnect()
                except (TypeError, RuntimeError):
                    pass
                prev.quit()
                prev.wait(1000)

        # Stop update worker if running
        if hasattr(self, 'update_worker') and self.update_worker and self.update_worker.isRunning():
            try:
                self.update_worker.wait(500)
            except Exception as e:
                logger.error(f"Failed to stop update worker: {e}")

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
        self.stack = QStackedWidget()
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
        self.stack.addWidget(self.history_view)
        
        # --- Page 3: Metrics View ---
        self.metrics_view = MetricsWidget(self.config_manager, self.history_manager)
        self.metrics_view.request_settings.connect(lambda: (self.sidebar.set_active(4), self.switch_page(4)))
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
        
    def _setup_shortcuts(self):
        # File Operations
        self.shortcut_open = QShortcut(QKeySequence("Ctrl+O"), self)
        self.shortcut_open.activated.connect(lambda: QTimer.singleShot(0, lambda: self.open_load_dialog(0)))
        
        self.shortcut_paste = QShortcut(QKeySequence("Ctrl+V"), self)
        self.shortcut_paste.activated.connect(self._handle_paste)

        self.shortcut_analyze = QShortcut(QKeySequence("Ctrl+A"), self)
        self.shortcut_analyze.activated.connect(self.start_analysis)
        
        # Navigation
        self.shortcut_left = QShortcut(QKeySequence("Left"), self)
        self.shortcut_left.activated.connect(self._nav_prev)
        
        self.shortcut_right = QShortcut(QKeySequence("Right"), self)
        self.shortcut_right.activated.connect(self._nav_next)
        
        self.shortcut_up = QShortcut(QKeySequence("Up"), self)
        self.shortcut_up.activated.connect(self._nav_last)
        
        self.shortcut_end = QShortcut(QKeySequence("End"), self)
        self.shortcut_end.activated.connect(self._nav_last)
        
        self.shortcut_down = QShortcut(QKeySequence("Down"), self)
        self.shortcut_down.activated.connect(self._nav_first)
        
        self.shortcut_home = QShortcut(QKeySequence("Home"), self)
        self.shortcut_home.activated.connect(self._nav_first)

    def _handle_paste(self):
        focus_widget = QApplication.focusWidget()
        if isinstance(focus_widget, (QLineEdit, QTextEdit)):
            # Restore native paste functionality since the shortcut swallowed it
            focus_widget.paste()
            return
            
        text = QApplication.clipboard().text().strip()
        if text and ("[Event" in text or "1." in text):
            QTimer.singleShot(0, lambda: self.open_load_dialog(initial_source=1, initial_text=text))

    def _nav_prev(self):
        if self.stack.currentIndex() == 1:
            self.explorer_view.move_list_widget.nav_prev.emit()
            return
            
        if not self.current_game: return
        idx = max(-1, self.board_widget.current_move_index - 1)
        if idx != self.board_widget.current_move_index:
            self.on_move_selected(idx)

    def _nav_next(self):
        if self.stack.currentIndex() == 1:
            self.explorer_view.move_list_widget.nav_next.emit()
            return
            
        if not self.current_game: return
        idx = min(len(self.current_game.moves) - 1, self.board_widget.current_move_index + 1)
        if idx != self.board_widget.current_move_index:
            self.on_move_selected(idx)

    def _nav_last(self):
        if self.stack.currentIndex() == 1:
            self.explorer_view.move_list_widget.nav_last.emit()
            return
            
        if not self.current_game: return
        idx = len(self.current_game.moves) - 1
        if idx != self.board_widget.current_move_index:
            self.on_move_selected(idx)

    def _nav_first(self):
        if self.stack.currentIndex() == 1:
            self.explorer_view.move_list_widget.nav_first.emit()
            return
            
        if not self.current_game: return
        if self.board_widget.current_move_index != -1:
            self.on_move_selected(-1)

    # ------------------------------------------------------------------
    # Status bar helpers
    # ------------------------------------------------------------------

    def _on_live_thinking_started(self):
        """Live engine started computing — show Calculating unless full analysis is running."""
        if not getattr(self, '_full_analysis_running', False):
            self._set_engine_state("calculating")

    def _on_live_thinking_stopped(self):
        """Live engine finished computing — revert to Ready unless full analysis is running."""
        if not getattr(self, '_full_analysis_running', False):
            self._set_engine_state("ready")

    # Engine states: 'offline' | 'ready' | 'calculating'
    def _refresh_engine_status(self):
        """Check engine binary and update pill. Call after path changes."""
        path = self.config_manager.get("engine_path", "stockfish")
        found = bool(shutil.which(path) or os.path.isfile(path))
        self._set_engine_state("ready" if found else "offline")

    def _set_engine_state(self, state: str, progress_msg: str = ""):
        """Update engine status text. state: 'offline' | 'ready' | 'calculating'."""
        if state == "calculating":
            self._spinner_idx = 0
            if not self._spinner_timer.isActive():
                self._spinner_timer.start(120)
            self._engine_pill.setText("⬤  Calculating")
            self._engine_pill.setStyleSheet(
                "font-size: 12px; font-weight: 600; padding: 0 6px; color: #e67e22;"
            )
        else:
            self._spinner_timer.stop()
            if state == "ready":
                self._engine_pill.setText("⬤  Engine Ready")
                self._engine_pill.setStyleSheet(
                    "font-size: 12px; font-weight: 600; padding: 0 6px; color: #27ae60;"
                )
            else:  # offline
                self._engine_pill.setText("⬤  Engine Offline")
                self._engine_pill.setStyleSheet(
                    "font-size: 12px; font-weight: 600; padding: 0 6px; color: #e74c3c;"
                )

    def _tick_spinner(self):
        """Advance the braille spinner animation one frame."""
        frame = self._spinner_frames[self._spinner_idx % len(self._spinner_frames)]
        self._spinner_idx += 1
        self._engine_pill.setText(f"{frame}  Calculating")

    # status label states
    _STATUS_STYLES = {
        "idle":       ("○",  "#888888"),
        "info":       ("◎",  "#3498db"),
        "success":    ("✔",  "#27ae60"),
        "warning":    ("⚠",  "#e67e22"),
        "error":      ("✖",  "#e74c3c"),
        "progress":   ("◌",  "#3498db"),
    }

    def _set_status(self, message: str, kind: str = "info"):
        """Update the status label with an icon prefix and matching colour."""
        icon, color = self._STATUS_STYLES.get(kind, ("◎", "#3498db"))
        self._status_lbl.setText(f"{icon}  {message}")
        self._status_lbl.setStyleSheet(f"font-size: 12px; color: {color};")

    # ------------------------------------------------------------------

    def update_engine_path(self, new_path):
        """Updates the engine path and re-initializes the analyzer."""
        logger.info(f"Updating engine path to: {new_path}")
        self.engine_path = new_path
        # Re-initialize analyzer with new engine
        try:
            self.analyzer = Analyzer(
                EngineManager(self.engine_path, config_manager=self.config_manager)
            )
            if hasattr(self, 'move_list_panel'):
                self.move_list_panel.update_engine_path(new_path)
            QMessageBox.information(self, "Success", "Engine path updated. Future analyses will use the new engine.")
        except Exception as e:
            logger.error(f"Failed to update engine: {e}")
            QMessageBox.warning(self, "Warning", f"Engine path updated, but failed to initialize: {e}")
        finally:
            self._refresh_engine_status()

    def apply_engine_settings(self):
        """Re-apply the current Threads/Hash settings to a running engine.

        No-op when no analysis is in progress — the next analysis will
        pick up the new values automatically.
        """
        logger.info("MainWindow: apply_engine_settings triggered by settings update.")
        engine = getattr(self.analyzer, "engine_manager", None)
        if engine is not None:
            engine.apply_settings_from_config()
        # Also reconfigure the live analysis worker engine dynamically
        if hasattr(self, 'move_list_panel') and hasattr(self.move_list_panel, 'live_worker'):
            logger.info("MainWindow: Reconfiguring live worker engine.")
            self.move_list_panel.live_worker.configure_engine()
        if hasattr(self, 'explorer_view') and hasattr(self.explorer_view, 'live_worker'):
            logger.info("MainWindow: Reconfiguring explorer live worker engine.")
            self.explorer_view.live_worker.configure_engine()

    def update_llm_config(self):
        """Re-instantiate the LLM service in every view that holds one.

        Triggered by SettingsView.llm_config_changed after the user saves
        a profile. The new GroqService() reads its settings from the
        ConfigManager itself, so we don't have to pass anything here.
        """
        from src.backend.services.groq_service import GroqService
        logger.info("Updating LLM configuration in all views...")
        if hasattr(self, 'metrics_view') and hasattr(self.metrics_view, 'groq_service'):
            self.metrics_view.groq_service = GroqService()
            logger.info("LLM service in metrics_view refreshed.")
        if hasattr(self, 'analysis_panel') and hasattr(self.analysis_panel, 'groq_service'):
            self.analysis_panel.groq_service = GroqService()
            logger.info("LLM service in analysis_panel refreshed.")

    def on_usernames_changed(self):
        """Reloads config values in views that use usernames."""
        logger.info("Usernames changed, refreshing dependent views...")
        # Reload config in config_manager (it's a singleton pattern issue)
        self.config_manager.reload_config()
        # Refresh metrics view which uses usernames
        if hasattr(self, 'metrics_view'):
            self.metrics_view.refresh()
        # Refresh history view
        if hasattr(self, 'history_view'):
            self.history_view.load_history()

    def refresh_theme(self):
        """Re-applies the theme and updates widgets that need manual refresh."""
        self.setStyleSheet(Styles.get_theme())
        
        # Update Sidebar
        self.sidebar.setStyleSheet(Styles.get_sidebar_style())
        
        # Update Board
        if hasattr(self, 'board_widget'):
            self.board_widget.update_board()

        # Update Explorer Board
        if hasattr(self, 'explorer_view') and hasattr(self.explorer_view, 'board_widget'):
            self.explorer_view.board_widget.update_board()
            
        # Update Analysis Panel
        if hasattr(self, 'analysis_panel'):
            self.analysis_panel.refresh_styles()
            
        # Update Move List Panel
        if hasattr(self, 'move_list_panel'):
            self.move_list_panel.refresh_styles()
            
        # Update Settings View
        if hasattr(self, 'settings_view'):
            self.settings_view.refresh_styles()
            
        # Update Metrics View (using lightweight style refresh if possible)
        if hasattr(self, 'metrics_view'):
            if hasattr(self.metrics_view, 'refresh_styles'):
                self.metrics_view.refresh_styles()
            else:
                self.metrics_view.refresh()
            
        # Update Analysis Header Bar
        if hasattr(self, 'analysis_header_bar') and self.analysis_header_bar:
            self.analysis_header_bar.setStyleSheet(f"""
                QFrame {{
                    background-color: {Styles.COLOR_BACKGROUND};
                    border-bottom: 1px solid {Styles.COLOR_BORDER};
                }}
            """)

        # Update MainWindow Buttons
        if hasattr(self, 'btn_load'):
            self.btn_load.setStyleSheet(Styles.get_control_button_style())
        if hasattr(self, 'btn_analyze'):
            self.btn_analyze.setStyleSheet(Styles.get_button_style())
        
        # Update Menu Styles
        menu_style = f"QMenu {{ background-color: {Styles.COLOR_SURFACE}; color: {Styles.COLOR_TEXT_PRIMARY}; border: 1px solid {Styles.COLOR_BORDER}; }} QMenu::item {{ padding: 5px 20px; }} QMenu::item:selected {{ background-color: {Styles.COLOR_ACCENT}; color: white; }}"
        if hasattr(self, 'load_menu'):
            self.load_menu.setStyleSheet(menu_style)
        if hasattr(self, 'menu_pgn'):
            self.menu_pgn.setStyleSheet(menu_style)
        if hasattr(self, 'menu_chesscom'):
            self.menu_chesscom.setStyleSheet(menu_style)
        if hasattr(self, 'menu_lichess'):
            self.menu_lichess.setStyleSheet(menu_style)
        
        # Update History View
        if hasattr(self, 'history_view'):
            if hasattr(self.history_view, 'refresh_styles'):
                self.history_view.refresh_styles()
            elif hasattr(self.history_view, 'game_list'):
                self.history_view.game_list.refresh_styles()
            elif hasattr(self.history_view, 'game_list_widget'):
                self.history_view.game_list_widget.refresh_styles()
            
        # Force update
        self.update()

    def switch_page(self, index):
        QTimer.singleShot(0, lambda: self._do_switch_page(index))

    def _do_switch_page(self, index):
        self.stack.setCurrentIndex(index)
        if index == 3: # Stats page
            self.metrics_view.refresh()

    def load_game_from_history(self, game):
        self.load_game(game)
        self.sidebar.set_active(0) # Switch to Analyze tab
        self.switch_page(0)

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
        """)
        header_layout = QHBoxLayout(self.analysis_header_bar)
        header_layout.setContentsMargins(40, 12, 40, 12)

        # Title
        title_lbl = QLabel("Chess Analysis")
        title_lbl.setStyleSheet(f"font-size: 24px; font-weight: bold; color: {Styles.COLOR_TEXT_PRIMARY}; background: transparent; border: none;")
        header_layout.addWidget(title_lbl)

        header_layout.addStretch()  # ← pushes buttons to the right, eating spare space

        # Explore Button
        self.btn_explore = create_button("Explore from here", style="secondary", on_click=self.explore_current_position, icon_name="fa5s.compass")
        self.btn_explore.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        header_layout.addWidget(self.btn_explore)

        # Load Game Button
        self.btn_load = create_button("Load Game", style="secondary", on_click=self.open_load_dialog, icon_name="fa5s.folder-open")
        self.btn_load.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        header_layout.addWidget(self.btn_load)

        # Analyze Game Button
        self.btn_analyze = create_button("Analyze Game", style="primary", on_click=self.start_analysis, icon_name="fa5s.play")
        header_layout.addWidget(self.btn_analyze)
        
        main_layout.addWidget(self.analysis_header_bar)
        
        # Splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(2)
        main_layout.addWidget(splitter, 1)
        
        # Left: Move List
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        self.move_list_panel = MoveListPanel(self.engine_path, config_manager=self.config_manager)
        self.move_list_panel.move_selected.connect(self.on_move_selected)
        # Wire live-engine thinking signals to the status bar indicator
        self.move_list_panel.live_worker.thinking_started.connect(self._on_live_thinking_started)
        self.move_list_panel.live_worker.thinking_stopped.connect(self._on_live_thinking_stopped)
        left_layout.addWidget(self.move_list_panel)
        
        splitter.addWidget(left_widget)
        
        # Center: Board
        center_widget = QWidget()
        center_layout = QVBoxLayout(center_widget)
        self.center_layout = center_layout  # needed for flip_board()
        center_layout.setContentsMargins(10, 10, 10, 10)
        center_layout.setSpacing(10)
        
        self.game_info_label = QLabel("No Game Loaded")
        self.game_info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.game_info_label.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {Styles.COLOR_TEXT_PRIMARY}; padding: 5px;")
        center_layout.addWidget(self.game_info_label)

        # Captured pieces: White sits at the BOTTOM of the board view,
        # so White's captures (the black pieces White took) belong BELOW
        # the board. Black sits at the TOP, so Black's captures (the
        # white pieces Black took) belong ABOVE the board. Keeping each
        # capture row adjacent to its capturer is the standard convention.
        self.captured_white = CapturedPiecesWidget(side="white")
        self.captured_black = CapturedPiecesWidget(side="black")
        # Backwards-compat alias — some code may still reference the old name.
        self.captured_widget = self.captured_white
 
        self.board_widget = BoardWidget()
        # Layout order (indices shown):
        #   1 captured_black  (above board, near Black)
        #   2 board
        #   3 captured_white  (below board, near White)
        center_layout.addWidget(self.captured_black)
        center_layout.addWidget(self.board_widget)
        center_layout.addWidget(self.captured_white)
        # Board takes all remaining vertical space. Without this, the
        # board (which now has no inner layout of its own, so no useful
        # sizeHint) collapses to its minimum size and the window is
        # dominated by empty space.
        center_layout.setStretch(1, 1)
        
        self.controls = GameControlsWidget()
        self.controls.first_clicked.connect(self.go_first)
        self.controls.prev_clicked.connect(self.go_prev)
        self.controls.next_clicked.connect(self.go_next)
        self.controls.last_clicked.connect(self.go_last)
        self.controls.flip_clicked.connect(self.flip_board)
        center_layout.addWidget(self.controls)
        
        splitter.addWidget(center_widget)
        
        # Right: Analysis
        self.analysis_panel = AnalysisPanel()
        if self.analysis_panel.layout:
            self.analysis_panel.layout.setContentsMargins(5, 5, 5, 5)
        self.analysis_panel.cache_toggled.connect(self.on_cache_toggled)
        self.move_list_panel.lines_updated.connect(self.analysis_panel.update_lines)
        self.analysis_panel.toggle_checkbox.toggled.connect(self.move_list_panel.set_engine_lines_enabled)
        
        splitter.addWidget(self.analysis_panel)
        splitter.setSizes([250, 630, 320])
        splitter.setStretchFactor(0, 1)  # Left: move list
        splitter.setStretchFactor(1, 3)  # Center: board (priority)
        splitter.setStretchFactor(2, 1)  # Right: analysis

    def _parse_and_load_game(self, pgn_text, source_data=None, status_msg=""):
        """
        Common pattern: Parse PGN text, attach source data, load first game.
        Returns True on success, False on failure.
        """
        from src.backend.storage.pgn_parser import PGNParser
        self.games = PGNParser.parse_pgn_text(pgn_text)
        if self.games:
            if source_data:
                for g in self.games:
                    g.source_data = source_data
            self.load_game(self.games[0])
            if status_msg:
                self._set_status(status_msg, "success")
            return True
        else:
            QMessageBox.warning(self, "Error", "Failed to parse game PGN.")
            return False

    def load_game(self, game):
        # If game has no moves but has PGN content (loaded from history), parse it
        if not game.moves and game.pgn_content:
            try:
                from src.backend.storage.pgn_parser import PGNParser
                parsed_games = PGNParser.parse_pgn_text(game.pgn_content)
                if parsed_games:
                    parsed = parsed_games[0]
                    game.moves = parsed.moves
                    game.metadata.chess960 = parsed.metadata.chess960
            except Exception as e:
                logger.error(f"Failed to parse PGN for history game: {e}")
                QMessageBox.warning(self, "Error", "Failed to load game moves.")
                return
        
        # Metadata Enrichment from source data if available
        if hasattr(game, "source_data") and game.source_data:
            self.enrich_game_metadata(game, game.source_data)

        self.current_game = game
        
        white = game.metadata.white
        black = game.metadata.black
        result = game.metadata.result
        w_elo = game.metadata.white_elo or game.metadata.headers.get("WhiteElo", "?")
        b_elo = game.metadata.black_elo or game.metadata.headers.get("BlackElo", "?")
        
        info_text = f"{white} ({w_elo}) vs {black} ({b_elo})  [{result}]"
        self.game_info_label.setText(info_text)
        
        self.board_widget.load_game(game)
        self.move_list_panel.set_game(game)
        self.analysis_panel.set_game(game)
        self.captured_white.update_captured(None)
        self.captured_black.update_captured(None)

        # Wire graph click → board navigation.
        # Disconnect first to prevent duplicate connections across game loads.
        try:
            self.analysis_panel.graph_widget.move_clicked.disconnect(self.on_move_selected)
        except (RuntimeError, TypeError):
            pass  # Was not connected yet — that's fine
        self.analysis_panel.graph_widget.move_clicked.connect(self.on_move_selected)

        logger.info(f"Game loaded: {game.metadata.white} vs {game.metadata.black}")
        self.resource_manager.play_sound("notify")

    def enrich_game_metadata(self, game, source_data):
        """
        Enriches game metadata with information from API source data 
        if the PGN parsing yielded missing or placeholder values.
        """
        md = game.metadata
        
        # Helper to get rating from diverse source structures
        def get_rating(data, color):
            # Structure 1: Nested (Chess.com / Lichess User Games) -> data['white']['rating']
            if color in data and isinstance(data[color], dict):
                return data[color].get("rating")
            # Structure 2: Flat (Lichess ID export) -> data['white_rating']
            flat_key = f"{color}_rating"
            if flat_key in data:
                return data[flat_key]
            return None

        # White Elo
        if not md.white_elo or md.white_elo == "?" or md.white_elo == "None":
            r = get_rating(source_data, "white")
            if r: 
                md.white_elo = str(r)
                md.headers["WhiteElo"] = str(r)

        # Black Elo
        if not md.black_elo or md.black_elo == "?" or md.black_elo == "None":
            r = get_rating(source_data, "black")
            if r: 
                md.black_elo = str(r)
                md.headers["BlackElo"] = str(r)
                    
        # Update source
        # If we loaded from API, we can set source if not already set
        if not getattr(md, "source", None) or md.source == "file":
             # Infer source?
             if "url" in source_data and "chess.com" in source_data["url"]:
                 md.source = "chesscom"
             elif "url" in source_data and "lichess.org" in source_data["url"]:
                 md.source = "lichess"
             # Or check keys
             elif "white_rating" in source_data: # Lichess ID structure
                 md.source = "lichess"

    def start_analysis(self):
        if not self.current_game:
            return
            
        if hasattr(self, 'worker') and self.worker and self.worker.isRunning():
            QMessageBox.warning(self, "Analysis in Progress", "An analysis is already running.")
            return
        
        # Check if engine exists
        is_in_path = shutil.which(self.engine_path) is not None
        is_file = os.path.exists(self.engine_path) and os.path.isfile(self.engine_path)
        
        if not (is_in_path or is_file):
             logger.warning(f"Engine not found at: {self.engine_path}")
             QMessageBox.warning(self, "Engine Not Found", "Please configure the engine path in Settings.")
             self.sidebar.set_active(3)
             self.switch_page(3)
             return

        logger.info("Starting analysis...")
        self.worker = AnalysisWorker(self.analyzer, self.current_game)
        self.worker.progress.connect(self.on_analysis_progress)
        self.worker.finished.connect(self.on_analysis_finished)
        self.worker.error.connect(self.on_analysis_error)

        self._full_analysis_running = True
        self._set_engine_state("calculating", "Starting...")
        self._set_status("Starting analysis...", "progress")
        

        if hasattr(self, 'move_list_panel') and hasattr(self.move_list_panel, 'live_worker'):
            self.move_list_panel.live_worker.stop()
            
        self.worker.start()

    def on_analysis_progress(self, current, total):
        if current > total:
            self._set_engine_state("calculating", "Final...")
            self._set_status("Analyzing final position...", "progress")
        else:
            self._set_engine_state("calculating", f"{current}/{total}")
            self._set_status(f"Analyzing move {current} of {total}", "progress")

    def on_analysis_finished(self, game):
        self._full_analysis_running = False
        self._set_engine_state("ready")
        self._set_status("Analysis complete", "success")
        logger.info("Analysis finished successfully.")
        self.current_game = game
        if hasattr(self, 'move_list_panel') and hasattr(self.move_list_panel, 'live_worker'):
            self.move_list_panel.live_worker.start()
        self.move_list_panel.set_game(game)
        self.analysis_panel.set_game(game)
        # Update other views with new data
        if hasattr(self, 'metrics_view'):
            self.metrics_view.refresh()
        if hasattr(self, 'history_view'):
            self.history_view.load_history()

    def on_analysis_error(self, error_msg):
        self._full_analysis_running = False
        self._set_engine_state("ready")
        self._set_status(f"Analysis failed: {error_msg}", "error")
        logger.error(f"Analysis error: {error_msg}")
        if hasattr(self, 'move_list_panel') and hasattr(self.move_list_panel, 'live_worker'):
            self.move_list_panel.live_worker.start()
        QMessageBox.critical(self, "Analysis Error", error_msg)

    def open_load_dialog(self, initial_source: int = 0, initial_text: str = None):
        """Open the unified Load Game dialog."""
        from .dialogs.load_game_dialog import LoadGameDialog
        dialog = LoadGameDialog(self, initial_source=initial_source)
        if initial_text and initial_source == 1:
            dialog._pgn_text_panel._text_edit.setPlainText(initial_text)
            dialog._pgn_text_panel._parse()
            
        if dialog.exec() == QDialog.DialogCode.Accepted:
            if dialog._pending_pgn:
                pgn = dialog._pending_pgn
                sd = dialog._pending_source_data
                QTimer.singleShot(0, lambda: self._parse_and_load_game(
                    pgn, 
                    source_data=sd, 
                    status_msg="Game loaded."
                ))

    def _on_game_ready(self, pgn_text: str, source_data):
        """Deprecated: Kept for compatibility. Called by LoadGameDialog when the user confirms a game selection."""
        self._parse_and_load_game(pgn_text, source_data=source_data,
                                  status_msg="Game loaded.")

    def keyPressEvent(self, event):
        # Global shortcuts (help)
        if event.key() == Qt.Key.Key_F1 or (event.key() == Qt.Key.Key_Question):
            self.show_shortcuts_help()
            return
        
        if event.key() == Qt.Key.Key_Slash and event.modifiers() == Qt.KeyboardModifier.ShiftModifier:
            # Shift+/ = ? on most keyboards
            self.show_shortcuts_help()
            return
            
        super().keyPressEvent(event)
    
    def show_shortcuts_help(self):
        """Show the keyboard shortcuts help dialog."""
        from .dialogs import ShortcutHelpDialog
        dialog = ShortcutHelpDialog(self)
        dialog.exec()

    def on_move_selected(self, index):
        self.board_widget.set_position(index)
        self.move_list_panel.select_move(index)
        
        # Update evaluation chart current move indicator
        if hasattr(self, 'analysis_panel') and hasattr(self.analysis_panel, 'graph_widget'):
            self.analysis_panel.graph_widget.set_current_move(index)
        
        if self.current_game:
            moves = self.current_game.moves
            fen = None
            if index == -1:
                fen = None 
            elif 0 <= index < len(moves):
                if index + 1 < len(moves):
                    fen = moves[index+1].fen_before
                else:
                    if hasattr(self.board_widget, 'board'):
                        fen = self.board_widget.board.fen()

            self.captured_white.update_captured(fen)
            self.captured_black.update_captured(fen)

            if 0 <= index < len(moves):
                move = moves[index]
                san = move.san
                if "#" in san or "mate" in san.lower():
                    self.resource_manager.play_sound("game_end")
                elif "+" in san:
                    self.resource_manager.play_sound("check")
                elif "x" in san:
                    self.resource_manager.play_sound("capture")
                elif "O-O" in san:
                    self.resource_manager.play_sound("castle")
                else:
                    self.resource_manager.play_sound("move")

    def explore_current_position(self):
        """Switches to the Explorer tab and loads the current board position."""
        if not self.current_game:
            self._set_status("Load a game first before exploring", "warning")
            return
        if hasattr(self, 'board_widget'):
            # Switch to Explorer tab
            self.sidebar.set_active(1)
            self.switch_page(1)
            
            # Load position and full move history
            moves = self.current_game.moves if self.current_game else None
            self.explorer_view.load_board_state(
                self.board_widget.board,
                moves,
                chess960=self.current_game.metadata.chess960,
                starting_fen=self.current_game.metadata.starting_fen,
            )

    def go_first(self):
        if self.current_game:
            self.on_move_selected(-1)

    def go_prev(self):
        if self.current_game:
            current = self.board_widget.current_move_index
            new_index = max(-1, current - 1)
            self.on_move_selected(new_index)

    def go_next(self):
        if self.current_game:
            current = self.board_widget.current_move_index
            total = len(self.current_game.moves)
            new_index = min(total - 1, current + 1)
            self.on_move_selected(new_index)

    def go_last(self):
        if self.current_game:
            total = len(self.current_game.moves)
            self.on_move_selected(total - 1)

    def flip_board(self):
        self.board_widget.flip_board()
        # Keep each player's captured-pieces row adjacent to that player.
        # The board stays at layout index 2; the two capture rows swap
        # around it. After flipping (White on top, Black on bottom), the
        # white-captures row moves above the board and the black-captures
        # row moves below it.
        self.center_layout.removeWidget(self.captured_white)
        self.center_layout.removeWidget(self.captured_black)
        if self.board_widget.is_flipped:
            self.center_layout.insertWidget(1, self.captured_white)
            self.center_layout.insertWidget(3, self.captured_black)
        else:
            self.center_layout.insertWidget(1, self.captured_black)
            self.center_layout.insertWidget(3, self.captured_white)

    def on_cache_toggled(self, checked):
        self.analyzer.config["use_cache"] = checked
        
    def resizeEvent(self, event):
        if hasattr(self, 'loading_overlay'):
            self.loading_overlay.resize(self.size())
        super().resizeEvent(event)
