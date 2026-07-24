import os
import json
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QSplitter, QFileDialog, QMenuBar,
                             QStatusBar, QMessageBox, QInputDialog, QDialog,
                             QListWidget, QListWidgetItem, QPushButton, QLineEdit, QLabel, QStackedWidget, QTextEdit, QFrame)

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QAction, QIcon, QShortcut, QKeySequence, QPalette, QColor
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
from src.backend.analysis.engine import EngineManager, resolve_engine_path, invalidate_engine_cache
from src.backend.api.chess_com_api import ChessComAPI
from src.backend.api.lichess_api import LichessAPI
from src.gui.styles import Styles
from src.gui.theme import ThemeManager
from src.gui.utils.gui_utils import create_button
from src.backend.storage.models import MoveAnalysis, GameAnalysis, GameMetadata
from src.backend.storage.game_history import GameHistoryManager
from src.utils.path_utils import get_resource_path
from src.gui.components.loading_widget import LoadingOverlay
from src.gui.components.tour_manager import TourManager, TourStep
from src.gui.components.tour_overlay import TourOverlay
from src.gui.components.transition_stack import FadedStackedWidget
from src.gui.components.toast import Toast

class MainWindow(QMainWindow):
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

        # Restore the last known window geometry, if any. Done before
        # setup_ui() so child layouts see the real size during their
        # first showEvent pass.
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
        
        # Apply Theme
        self.refresh_theme()

        # Tour overlay — marks the page seen when the tour finishes/closes
        self.tour_overlay = TourOverlay(
            self,
            self.tour_manager,
            on_finished=self._on_tour_finished,
        )
        self.tour_overlay.hide()

        # Style the status bar itself — without this, macOS renders a grey
        # native bounding box behind each addWidget() item.
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
        self._engine_pill.setStyleSheet("font-size: 12px; font-weight: 600; padding: 0 6px; background: transparent;")
        self.statusBar().addWidget(self._engine_pill)

        # Thin separator
        sep = QLabel("│")
        sep.setStyleSheet(f"color: {Styles.COLOR_BORDER}; padding: 0 4px; background: transparent;")
        self.statusBar().addWidget(sep)

        self._status_lbl = QLabel("Ready")
        self._status_lbl.setStyleSheet(f"font-size: 12px; color: {Styles.COLOR_TEXT_SECONDARY}; background: transparent;")
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

        # Tour
        self.shortcut_tour = QShortcut(QKeySequence("Ctrl+T"), self)
        self.shortcut_tour.activated.connect(self.start_tour)

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
    # Toast notifications
    # ------------------------------------------------------------------

    def show_toast(self, message: str, kind: str = "info", duration: int | None = None):
        Toast.show_message(self, message, kind, duration)

    @staticmethod
    def toast_from_widget(widget, message: str, kind: str = "info", duration: int | None = None):
        win = widget.window()
        if hasattr(win, "show_toast"):
            win.show_toast(message, kind, duration)

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
        found = resolve_engine_path(self.config_manager) is not None
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
        self._status_lbl.setStyleSheet(f"font-size: 12px; color: {color}; background: transparent;")

    # ------------------------------------------------------------------

    def update_engine_path(self, new_path):
        """Updates the engine path and re-initializes the analyzer."""
        resolved = resolve_engine_path(self.config_manager)
        if resolved:
            new_path = resolved
        logger.info(f"Updating engine path to: {new_path}")
        self.engine_path = new_path
        # Re-initialize analyzer with new engine
        try:
            self.analyzer = Analyzer(
                EngineManager(self.engine_path, config_manager=self.config_manager)
            )
            if hasattr(self, 'move_list_panel'):
                self.move_list_panel.update_engine_path(new_path)
            self.show_toast("Engine path updated. Future analyses will use the new engine.", "info")
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

    def _apply_palette(self):
        p = ThemeManager.palette()
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor(p.background))
        palette.setColor(QPalette.ColorRole.WindowText, QColor(p.text_primary))
        palette.setColor(QPalette.ColorRole.Base, QColor(p.surface))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor(p.surface_light))
        palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(p.surface_light))
        palette.setColor(QPalette.ColorRole.ToolTipText, QColor(p.text_primary))
        palette.setColor(QPalette.ColorRole.Text, QColor(p.text_primary))
        palette.setColor(QPalette.ColorRole.Button, QColor(p.surface))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor(p.text_primary))
        palette.setColor(QPalette.ColorRole.BrightText, QColor(p.accent))
        palette.setColor(QPalette.ColorRole.Link, QColor(p.accent))
        palette.setColor(QPalette.ColorRole.Highlight, QColor(p.accent))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#FFFFFF"))
        QApplication.setPalette(palette)

    def _on_theme_changed(self, mode: str):
        self.refresh_theme()

    def _on_accent_changed(self, hex_color: str):
        self.config_manager.set("accent_color", hex_color)
        self.refresh_theme()

    def refresh_theme(self):
        """Re-applies the theme and updates widgets that need manual refresh."""
        self._apply_palette()
        theme_qss = Styles.get_theme()
        self.setStyleSheet(theme_qss)
        QApplication.instance().setStyleSheet(theme_qss)
        
        # Update Sidebar
        self.sidebar.apply_style()
        
        # Update Board
        if hasattr(self, 'board_widget'):
            self.board_widget.update_board()

        # Update analysis page container backgrounds
        if hasattr(self, 'left_widget') and self.left_widget:
            self.left_widget.setStyleSheet(f"background-color: {Styles.COLOR_BACKGROUND};")
        if hasattr(self, 'center_widget') and self.center_widget:
            self.center_widget.setStyleSheet(f"background-color: {Styles.COLOR_BACKGROUND};")

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
                QFrame QLabel {{
                    background: transparent;
                }}
            """)

        # Update MainWindow Buttons
        if hasattr(self, 'btn_explore'):
            self.btn_explore.setStyleSheet(Styles.get_control_button_style())
        if hasattr(self, 'btn_load'):
            self.btn_load.setStyleSheet(Styles.get_control_button_style())
        if hasattr(self, 'btn_analyze'):
            self.btn_analyze.setStyleSheet(Styles.get_button_style())
        if hasattr(self, 'game_info_label'):
            self.game_info_label.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {Styles.COLOR_TEXT_PRIMARY}; padding: 5px; background: transparent;")
        
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
        
        # Update Captured Pieces
        for cp in ("captured_white", "captured_black"):
            if hasattr(self, cp):
                w = getattr(self, cp)
                if hasattr(w, 'refresh_styles'):
                    w.refresh_styles()

        # Update Game Controls
        if hasattr(self, 'controls') and hasattr(self.controls, 'refresh_styles'):
            self.controls.refresh_styles()

        # Update explorer view panels
        if hasattr(self, 'explorer_view'):
            ev = self.explorer_view
            if hasattr(ev, 'refresh_styles'):
                ev.refresh_styles()
            if hasattr(ev, 'move_list_widget') and hasattr(ev.move_list_widget, 'refresh_styles'):
                ev.move_list_widget.refresh_styles()

        # Update History View
        if hasattr(self, 'history_view'):
            if hasattr(self.history_view, 'refresh_styles'):
                self.history_view.refresh_styles()
            elif hasattr(self.history_view, 'game_list'):
                self.history_view.game_list.refresh_styles()
            elif hasattr(self.history_view, 'game_list_widget'):
                self.history_view.game_list_widget.refresh_styles()
            
        # Update tour overlay accent
        if hasattr(self, 'tour_overlay'):
            self.tour_overlay.refresh_accent()

        # Update status bar
        self.statusBar().setStyleSheet(f"""
            QStatusBar {{
                background-color: {Styles.COLOR_BACKGROUND};
                border-top: 1px solid {Styles.COLOR_BORDER};
            }}
            QStatusBar QLabel {{
                background: transparent;
            }}
        """)
        if hasattr(self, '_status_lbl'):
            self._status_lbl.setStyleSheet(f"font-size: 12px; color: {Styles.COLOR_TEXT_SECONDARY}; background: transparent;")
        if hasattr(self, '_engine_pill'):
            state = self._engine_pill.text()
            if "Offline" in state:
                self._engine_pill.setStyleSheet("font-size: 12px; font-weight: 600; padding: 0 6px; color: #e74c3c;")
            elif "Calculating" in state:
                self._engine_pill.setStyleSheet("font-size: 12px; font-weight: 600; padding: 0 6px; color: #e67e22;")
            else:
                self._engine_pill.setStyleSheet("font-size: 12px; font-weight: 600; padding: 0 6px; color: #27ae60;")

        # Force full style re-evaluation for all children
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def switch_page(self, index):
        QTimer.singleShot(0, lambda: self._do_switch_page(index))

    def _do_switch_page(self, index):
        self.stack.setCurrentIndex(index)
        if index == 3:  # Stats page
            self.metrics_view.refresh()
        # If a tour is active, close it silently (don't mark seen — user didn't finish it).
        if hasattr(self, 'tour_overlay') and self.tour_overlay.isVisible():
            self.tour_overlay.close_silently()
        # Auto-start the tour the first time the user visits this page.
        if not self.tour_manager.has_seen_tour(index):
            QTimer.singleShot(400, lambda idx=index: self._auto_start_tour(idx))

    def _auto_start_tour(self, page_index: int):
        """Start tour on first visit only — guards against delayed mis-fires."""
        if self.stack.currentIndex() != page_index:
            return  # user navigated away during the 400ms delay
        if self.tour_manager.has_seen_tour(page_index):
            return  # already seen (e.g. Ctrl+T was pressed and dismissed)

        # Skip tour if the page has no relevant data yet (don't mark seen,
        # so the tour retriggers on next visit once data becomes available).
        if page_index == 0 and self.current_game is None:
            return
        if page_index == 2 and hasattr(self, 'history_view') and not self.history_view.games:
            return
        if page_index == 3 and hasattr(self, 'metrics_view'):
            mv = self.metrics_view
            if not any(hasattr(mv, attr) for attr in ('accuracy_card', 'result_card', 'openings_card')):
                return

        self._launch_tour(page_index)

    def start_tour(self):
        """Ctrl+T: replay tour only if this page has not been seen yet."""
        index = self.stack.currentIndex()
        if not self.tour_manager.has_seen_tour(index):
            self._launch_tour(index)

    def _launch_tour(self, page_index: int):
        """Build steps and show the tour overlay for the given page."""
        steps = self._build_tour_steps(page_index)
        if not steps:
            self.tour_manager.mark_seen(page_index)  # nothing to show — mark done
            return
        self._tour_page = page_index  # remember the originating page
        self.tour_overlay.setGeometry(self.rect())
        self.tour_manager.start(steps)
        self.tour_overlay.show_tour()

    def _on_tour_finished(self):
        """Called when the tour overlay closes. Uses the page the tour *started*
        on so a mid-tour page switch doesn't mark the wrong page.
        """
        page_index = getattr(self, '_tour_page', self.stack.currentIndex())
        self.tour_manager.mark_seen(page_index)

    def _build_tour_steps(self, page_index: int) -> list:
        """Return a list of TourStep objects tailored to the visible page."""
        ev = self.explorer_view
        hv = self.history_view
        sv = self.settings_view
        mv = self.metrics_view
        steps = []

        if page_index == 0:  # ── Analysis ───────────────────────────────────
            steps.append(TourStep(
                target=self.btn_load,
                text='Load a game via PGN file, paste PGN text, or fetch directly from Chess.com / Lichess using "Load Game".',
                position="below", page_index=0,
            ))
            steps.append(TourStep(
                target=self.btn_analyze,
                text='Click "Analyze Game" to run Stockfish on every move. Each move gets classified: brilliant, best, excellent, good, inaccuracy, mistake, or blunder.',
                position="below", page_index=0,
            ))
            steps.append(TourStep(
                target=self.board_widget,
                text="Navigate with the arrow keys or by clicking moves in the list. The board is interactive and shows the current position.",
                position="right", page_index=0,
            ))
            steps.append(TourStep(
                target=self.move_list_panel,
                text="The move list shows colour-coded badges (brilliant, best, inaccuracy, blunder). The live engine line updates as you navigate.",
                position="right", page_index=0,
            ))
            steps.append(TourStep(
                target=self.analysis_panel,
                text="The eval graph, engine lines, and AI Coach summary are here. Click any point on the graph to jump to that move.",
                position="left", page_index=0,
            ))
            steps.append(TourStep(
                target=self.btn_explore,
                text='"Explore from here" opens the Opening Explorer at the current board position so you can study master-level continuations.',
                position="below", page_index=0,
            ))

        elif page_index == 1:  # ── Explorer ────────────────────────────────
            steps.append(TourStep(
                target=ev.header_bar if hasattr(ev, 'header_bar') else ev,
                text="The ECO code and full opening name for the current position are shown in the header badge, updating with every move.",
                position="below", page_index=1,
            ))
            steps.append(TourStep(
                target=ev.board_widget if hasattr(ev, 'board_widget') else ev,
                text="Click squares to make moves, or use the arrow keys to walk through your move history. The engine evaluates each position in real time.",
                position="right", page_index=1,
            ))
            steps.append(TourStep(
                target=ev.book_toggle if hasattr(ev, 'book_toggle') else ev,
                text="Book Moves lists the most-played responses from master games. Click any move to play it instantly on the board.",
                position="right", page_index=1,
            ))
            steps.append(TourStep(
                target=ev.lines_widget if hasattr(ev, 'lines_widget') else ev,
                text="Engine Lines shows Stockfish top candidate moves with evaluation scores. Raise multi-PV in Settings to see more alternatives.",
                position="left", page_index=1,
            ))
            steps.append(TourStep(
                target=ev.chk_classify if hasattr(ev, 'chk_classify') else ev,
                text='Enable "Classify Moves" to get brilliant/blunder badges on every move you play in the explorer, just like full analysis mode.',
                position="above", page_index=1,
            ))
            steps.append(TourStep(
                target=ev.move_list_widget if hasattr(ev, 'move_list_widget') else ev,
                text="Your move history. You can also type a move in SAN notation (e.g. e4, Nf3) in the input box to jump to any position quickly.",
                position="left", page_index=1,
            ))

        elif page_index == 2:  # ── History ──────────────────────────────────
            steps.append(TourStep(
                target=hv.search_input if hasattr(hv, 'search_input') else hv,
                text="Search your game history by player name, opening ECO, event, or result. The list filters instantly as you type.",
                position="below", page_index=2,
            ))
            if hasattr(hv, 'result_filter'):
                steps.append(TourStep(
                    target=hv.result_filter,
                    text="Filter by result (Win / Draw / Loss) or by source (Chess.com / Lichess / PGN file) using the dropdowns.",
                    position="below", page_index=2,
                ))
            if hasattr(hv, 'btn_export'):
                steps.append(TourStep(
                    target=hv.btn_export,
                    text='"Export" saves all your analyzed games to a PGN file you can open in Lichess Studies, ChessBase, or any other chess app.',
                    position="left", page_index=2,
                ))
            if hasattr(hv, 'btn_import'):
                steps.append(TourStep(
                    target=hv.btn_import,
                    text='"Import" loads a previously exported PGN back into your history. Use this to restore a backup or transfer games between machines.',
                    position="left", page_index=2,
                ))
            if hasattr(hv, 'btn_clear'):
                steps.append(TourStep(
                    target=hv.btn_clear,
                    text='"Clear History" permanently deletes all saved games. Always export a backup first if you want to keep the data.',
                    position="left", page_index=2,
                ))

        elif page_index == 3:  # ── Stats ────────────────────────────────────
            if hasattr(mv, 'btn_refresh'):
                steps.append(TourStep(
                    target=mv.btn_refresh,
                    text="Stats update automatically when you open this page. Hit Refresh to pick up any games analyzed since the last load.",
                    position="left", page_index=3,
                ))
            if hasattr(mv, 'accuracy_card'):
                steps.append(TourStep(
                    target=mv.accuracy_card,
                    text="Accuracy Trend shows your average move accuracy over time. Watch the line climb as your chess improves.",
                    position="right", page_index=3,
                ))
            if hasattr(mv, 'result_card'):
                steps.append(TourStep(
                    target=mv.result_card,
                    text="Result Distribution breaks down your wins, draws, and losses by colour (White / Black).",
                    position="right", page_index=3,
                ))
            if hasattr(mv, 'openings_card'):
                steps.append(TourStep(
                    target=mv.openings_card,
                    text="Top Openings ranks your most-played openings by win rate — double down on what works and study what doesn't.",
                    position="left", page_index=3,
                ))
            if hasattr(mv, 'ai_coach_card'):
                steps.append(TourStep(
                    target=mv.ai_coach_card,
                    text="AI Coach reads your stats and writes personalised advice: patterns to fix, openings to study, and training priorities.",
                    position="left", page_index=3,
                ))
            if not steps:
                steps.append(TourStep(
                    target=mv,
                    text="Your personal performance dashboard with accuracy trends, result breakdown, top openings, and AI Coach insights.",
                    position="right", page_index=3,
                ))

        elif page_index == 4:  # ── Settings ─────────────────────────────────
            if hasattr(sv, 'path_input'):
                steps.append(TourStep(
                    target=sv.path_input,
                    text="Engine Path points to your Stockfish binary. Leave blank to auto-detect from PATH (works if installed via Homebrew or a package manager).",
                    position="below", page_index=4,
                ))
            if hasattr(sv, 'depth_combo'):
                steps.append(TourStep(
                    target=sv.depth_combo,
                    text="Analysis Depth controls how deep Stockfish searches (default 18). Higher = more accurate, but slower. 15-20 is ideal for most hardware.",
                    position="below", page_index=4,
                ))
            if hasattr(sv, 'llm_profile_combo'):
                steps.append(TourStep(
                    target=sv.llm_profile_combo,
                    text="LLM Profiles let you configure multiple AI providers (Groq, OpenAI, LM Studio, MiniMax). Switch between them or create new ones here.",
                    position="below", page_index=4,
                ))
            if hasattr(sv, 'llm_key_input'):
                steps.append(TourStep(
                    target=sv.llm_key_input,
                    text="Paste your API key here. For Groq the free tier is very generous. For LM Studio, set the Base URL to your local server address.",
                    position="below", page_index=4,
                ))
            if hasattr(sv, 'theme_combo'):
                steps.append(TourStep(
                    target=sv.theme_combo,
                    text="Board Theme and Piece Style let you personalise the look. Changes apply instantly without restarting.",
                    position="below", page_index=4,
                ))
            if not steps:  # fallback
                steps.append(TourStep(
                    target=sv,
                    text="Configure Stockfish engine path, analysis depth, AI provider, board theme, and piece style here.",
                    position="right", page_index=4,
                ))

        return steps

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
            QFrame QLabel {{
                background: transparent;
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
        self.center_layout = center_layout  # needed for flip_board()
        center_layout.setContentsMargins(10, 10, 10, 10)
        center_layout.setSpacing(10)
        
        self.game_info_label = QLabel("No Game Loaded")
        self.game_info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.game_info_label.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {Styles.COLOR_TEXT_PRIMARY}; padding: 5px; background: transparent;")
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
        
        splitter.addWidget(self.center_widget)
        
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
            QMessageBox.warning(self, "Error", "Could not read this game.\nThe PGN data may be empty or corrupted.")
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

        # Initialize clocks based on PGN data if present
        has_clocks = any(m.time_left is not None for m in game.moves) if game.moves else False
        if has_clocks:
            white_time = None
            black_time = None
            
            # Find first white and black clock values to estimate starting time
            for m in game.moves:
                if m.time_left is not None:
                    idx = game.moves.index(m)
                    if idx % 2 == 0 and white_time is None:
                        white_time = m.time_left + (m.time_spent if m.time_spent is not None else 0.0)
                    elif idx % 2 == 1 and black_time is None:
                        black_time = m.time_left + (m.time_spent if m.time_spent is not None else 0.0)
            
            self.captured_white.update_clock(white_time)
            self.captured_black.update_clock(black_time)
        else:
            self.captured_white.update_clock(None)
            self.captured_black.update_clock(None)

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
        
        # Auto-detect engine if the configured path doesn't work
        resolved = resolve_engine_path(self.config_manager)
        if resolved:
            if resolved != self.engine_path:
                self.engine_path = resolved
                self.analyzer = Analyzer(
                    EngineManager(self.engine_path, config_manager=self.config_manager)
                )
        else:
            logger.warning(f"Engine not found (configured: {self.engine_path})")
            from .dialogs.engine_error_dialog import EngineNotFoundDialog
            dialog = EngineNotFoundDialog(self)
            if hasattr(self, 'config_manager'):
                dialog.config_manager = lambda: self.config_manager
            if dialog.exec() == QDialog.DialogCode.Accepted:
                new_path = dialog.engine_path()
                if new_path:
                    self.config_manager.config["engine_path"] = new_path
                    self.config_manager.save_config()
                    self.engine_path = new_path
                    self.analyzer = Analyzer(
                        EngineManager(self.engine_path, config_manager=self.config_manager)
                    )
                    invalidate_engine_cache()
                    logger.info(f"Engine path set to {new_path} via error dialog")
                    self._refresh_engine_status()
            else:
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
        self.show_toast("Analysis complete!", "success")
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
            if dialog._navigate_to_settings:
                self.sidebar.set_active(4)
                QTimer.singleShot(0, lambda: self.switch_page(4))
            elif dialog._pending_pgn:
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

            # Update clock display if clock data is present
            has_clocks = any(m.time_left is not None for m in moves)
            if has_clocks:
                white_time = None
                black_time = None
                
                # Find the latest white time_left at or before index
                for i in range(index, -1, -1):
                    if i % 2 == 0:  # White's move
                        if moves[i].time_left is not None:
                            white_time = moves[i].time_left
                            break
                
                # Find the latest black time_left at or before index
                for i in range(index, -1, -1):
                    if i % 2 == 1:  # Black's move
                        if moves[i].time_left is not None:
                            black_time = moves[i].time_left
                            break
                
                # Fall back to starting times if no move has been played yet on that side
                if white_time is None:
                    for m in moves:
                        if m.time_left is not None and moves.index(m) % 2 == 0:
                            white_time = m.time_left + (m.time_spent if m.time_spent is not None else 0.0)
                            break
                if black_time is None:
                    for m in moves:
                        if m.time_left is not None and moves.index(m) % 2 == 1:
                            black_time = m.time_left + (m.time_spent if m.time_spent is not None else 0.0)
                            break
                
                self.captured_white.update_clock(white_time)
                self.captured_black.update_clock(black_time)
            else:
                self.captured_white.update_clock(None)
                self.captured_black.update_clock(None)

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
        if hasattr(self, 'tour_overlay'):
            self.tour_overlay.setGeometry(self.rect())
        super().resizeEvent(event)
