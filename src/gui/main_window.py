import os
import json
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QSplitter, QFileDialog, QMenuBar,
                             QStatusBar, QMessageBox, QInputDialog, QDialog,
                             QListWidget, QListWidgetItem, QPushButton, QLineEdit, QLabel, QStackedWidget)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtWidgets import QMenu
import shutil

from .board import BoardWidget  # From board package
from .analysis_view import MoveListPanel, AnalysisPanel
from .analysis import CapturedPiecesWidget, GameControlsWidget  # From analysis package
from .metrics_widget import MetricsWidget
from .analysis_worker import AnalysisWorker
from .sidebar import Sidebar
from .views import HistoryView, SettingsView  # From views package
from ..backend.pgn_parser import PGNParser
from ..backend.analyzer import Analyzer
from ..utils.resources import ResourceManager
from ..utils.logger import logger
from ..utils.config import ConfigManager
from ..backend.engine import EngineManager
from ..backend.chess_com_api import ChessComAPI
from ..backend.lichess_api import LichessAPI
from .styles import Styles
from .gui_utils import create_button
from ..backend.models import MoveAnalysis, GameAnalysis, GameMetadata
from ..backend.game_history import GameHistoryManager
from ..utils.path_utils import get_resource_path
from .loading_widget import LoadingOverlay

class APILoaderWorker(QThread):
    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, api_func, *args, **kwargs):
        super().__init__()
        self.api_func = api_func
        self.args = args
        self.kwargs = kwargs

    def run(self):
        try:
            result = self.api_func(*self.args, **self.kwargs)
            # Result can be list (multiple games) or dict (single game)
            if result is None: result = []
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))

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
        self.analyzer = Analyzer(EngineManager(self.engine_path))
        self.history_manager = GameHistoryManager()
        self.resource_manager = ResourceManager()
        
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
        
        
        # Overlay
        self.loading_overlay = LoadingOverlay(self)
        self.loading_overlay.resize(self.size())
        
        # Load History
        # self.load_history()

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
        
        # --- Page 1: History View ---
        self.history_view = HistoryView(self.config_manager)
        self.history_view.game_selected.connect(self.load_game_from_history)
        self.stack.addWidget(self.history_view)
        
        # --- Page 2: Metrics View ---
        self.metrics_view = MetricsWidget(self.config_manager, self.history_manager)
        self.metrics_view.request_settings.connect(lambda: (self.sidebar.set_active(3), self.stack.setCurrentIndex(3)))
        self.stack.addWidget(self.metrics_view)
        
        # --- Page 3: Settings View ---
        self.settings_view = SettingsView()
        self.settings_view.engine_path_changed.connect(self.update_engine_path)
        self.settings_view.gemini_key_changed.connect(self.update_gemini_key)
        self.settings_view.usernames_changed.connect(self.on_usernames_changed)
        self.stack.addWidget(self.settings_view)

    def update_engine_path(self, new_path):
        """Updates the engine path and re-initializes the analyzer."""
        logger.info(f"Updating engine path to: {new_path}")
        self.engine_path = new_path
        # Re-initialize analyzer with new engine
        try:
            self.analyzer = Analyzer(EngineManager(self.engine_path))
            # Also update worker if it exists? 
            # Worker is created per analysis, so next analysis will use new analyzer/engine.
            QMessageBox.information(self, "Success", "Engine path updated. Future analyses will use the new engine.")
        except Exception as e:
            logger.error(f"Failed to update engine: {e}")
            QMessageBox.warning(self, "Warning", f"Engine path updated, but failed to initialize: {e}")

    def update_gemini_key(self, new_key):
        """Updates the Gemini API key in MetricsWidget immediately."""
        logger.info("Updating Gemini API key...")
        if hasattr(self, 'metrics_view') and hasattr(self.metrics_view, 'gemini_service'):
            from ..backend.gemini_service import GeminiService
            self.metrics_view.gemini_service = GeminiService(new_key)
            logger.info("Gemini service updated with new API key.")

    def on_usernames_changed(self):
        """Reloads config values in views that use usernames."""
        logger.info("Usernames changed, refreshing dependent views...")
        # Reload config in config_manager (it's a singleton pattern issue)
        self.config_manager.config = self.config_manager.load_config()
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
            
        # Update Analysis Panel
        if hasattr(self, 'analysis_panel'):
            self.analysis_panel.refresh_styles()
            
        # Update Settings View
        if hasattr(self, 'settings_view'):
            self.settings_view.refresh_styles()
            
        # Update Metrics View
        if hasattr(self, 'metrics_view'):
            self.metrics_view.refresh()
            
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
        
        # Update History View Game List
        if hasattr(self, 'history_view') and hasattr(self.history_view, 'game_list_widget'):
            self.history_view.game_list_widget.refresh_styles()
            
        # Force update
        self.update()

    def switch_page(self, index):
        self.stack.setCurrentIndex(index)
        if index == 2: # Stats page
            self.metrics_view.refresh()

    def load_game_from_history(self, game):
        self.load_game(game)
        self.sidebar.set_active(0) # Switch to Analyze tab
        self.stack.setCurrentIndex(0)

    def setup_analysis_page(self, parent_widget):
        layout = QHBoxLayout(parent_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(2)
        layout.addWidget(splitter)
        
        # Left: Move List
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        self.move_list_panel = MoveListPanel(self.engine_path)
        self.move_list_panel.move_selected.connect(self.on_move_selected)
        left_layout.addWidget(self.move_list_panel)
        
        splitter.addWidget(left_widget)
        
        # Center: Board
        center_widget = QWidget()
        center_layout = QVBoxLayout(center_widget)
        center_layout.setContentsMargins(10, 10, 10, 10)
        center_layout.setSpacing(10)
        
        self.game_info_label = QLabel("No Game Loaded")
        self.game_info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.game_info_label.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {Styles.COLOR_TEXT_PRIMARY}; padding: 5px;")
        center_layout.addWidget(self.game_info_label)
        
        self.captured_widget = CapturedPiecesWidget()
        center_layout.addWidget(self.captured_widget)
        
        self.board_widget = BoardWidget()
        center_layout.addWidget(self.board_widget)
        
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
        self.analysis_panel.cache_toggled.connect(self.on_cache_toggled)
        self.move_list_panel.lines_updated.connect(self.analysis_panel.update_lines)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        # Load Game Button with Menu
        self.btn_load = create_button("Load Game", style="secondary")
        
        self.load_menu = QMenu(self)
        menu_style = f"QMenu {{ background-color: {Styles.COLOR_SURFACE}; color: {Styles.COLOR_TEXT_PRIMARY}; border: 1px solid {Styles.COLOR_BORDER}; }} QMenu::item {{ padding: 5px 20px; }} QMenu::item:selected {{ background-color: {Styles.COLOR_ACCENT}; color: white; }}"
        self.load_menu.setStyleSheet(menu_style)
        
        # 1. PGN Submenu
        self.menu_pgn = QMenu("Load from PGN", self)
        self.menu_pgn.setStyleSheet(menu_style)
        
        action_pgn = QAction("From File...", self)
        action_pgn.triggered.connect(self.open_pgn)
        self.menu_pgn.addAction(action_pgn)

        action_pgn_text = QAction("From Text...", self)
        action_pgn_text.triggered.connect(self.load_from_pgn_text)
        self.menu_pgn.addAction(action_pgn_text)
        
        self.load_menu.addMenu(self.menu_pgn)
        
        # 2. Chess.com Submenu
        self.menu_chesscom = QMenu("Load from Chess.com", self)
        self.menu_chesscom.setStyleSheet(menu_style)
        
        action_user = QAction("By Username...", self)
        action_user.triggered.connect(self.load_from_chesscom)
        self.menu_chesscom.addAction(action_user)
        
        action_link = QAction("By Game Link...", self)
        action_link.triggered.connect(self.load_from_link)
        self.menu_chesscom.addAction(action_link)
        
        self.load_menu.addMenu(self.menu_chesscom)

        # 3. Lichess Submenu
        self.menu_lichess = QMenu("Load from Lichess", self)
        self.menu_lichess.setStyleSheet(menu_style)

        action_lichess = QAction("By Username...", self)
        action_lichess.triggered.connect(self.load_from_lichess)
        self.menu_lichess.addAction(action_lichess)
        
        action_lichess_link = QAction("By Game Link...", self)
        action_lichess_link.triggered.connect(self.load_from_lichess_link)
        self.menu_lichess.addAction(action_lichess_link)
        
        self.load_menu.addMenu(self.menu_lichess)
        
        self.btn_load.setMenu(self.load_menu)
        btn_layout.addWidget(self.btn_load)
        
        # Analyze Button
        self.btn_analyze = create_button("Analyze Game", style="primary", on_click=self.start_analysis)
        btn_layout.addWidget(self.btn_analyze)
        
        left_layout.insertLayout(0, btn_layout) # Insert at top
        
        splitter.addWidget(self.analysis_panel)
        splitter.setSizes([250, 600, 350])

    def load_from_pgn_text(self):
        text, ok = QInputDialog.getMultiLineText(
            self,
            "Load PGN",
            "Paste your PGN below:"
        )
        if ok and text.strip():
            logger.info("PGN obtained from textline entry...")
            try:
                parsed_games = PGNParser.parse_pgn_text(text)
                
                # Validation: A valid game must have moves OR a starting FEN (position setup)
                valid_games = []
                for game in parsed_games:
                    if game.moves or game.metadata.starting_fen:
                        valid_games.append(game)
                
                if valid_games:
                    self.games = valid_games
                    self.load_game(self.games[0])
                    logger.info(f"Loaded {len(self.games)} valid games.")
                else:
                    logger.warning("No valid games found in PGN text (no moves or setup).")
                    QMessageBox.warning(self, "Invalid PGN", "No valid games found in the provided text.\nPlease ensure it contains moves or a FEN setup.")
            except Exception as e:
                logger.error(f"Failed to parse PGN: {e}", exc_info=True)
                QMessageBox.critical(self, "Error", f"Failed to parse PGN: {e}")
        else:
            logger.info("PGN text entry cancelled or empty.")


    def open_pgn(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Open PGN File", "", "PGN Files (*.pgn);;All Files (*)")
        if file_name:
            logger.info(f"Loading PGN file: {file_name}")
            try:
                self.games = PGNParser.parse_pgn_file(file_name)
                if self.games:
                    self.load_game(self.games[0])
                    logger.info(f"Loaded {len(self.games)} games.")
                else:
                    logger.warning("No games found in PGN file.")
            except Exception as e:
                logger.error(f"Failed to parse PGN: {e}", exc_info=True)
                QMessageBox.critical(self, "Error", f"Failed to parse PGN: {e}")
        else:
            logger.info("PGN file selection cancelled.")

    def load_from_chesscom(self):
        default_user = self.config_manager.get("chesscom_username", "")
        username, ok = QInputDialog.getText(self, "Load from Chess.com", "Enter Chess.com Username:", text=default_user)
        if ok and username:
            self._load_games_from_api(
                ChessComAPI().get_last_games, 
                username.strip(), 
                "Chess.com", 
                limit=5
            )

    def _load_games_from_api(self, api_func, username, source, **kwargs):
        """Common pattern for loading games from API with worker thread."""
        logger.info(f"Attempting to load games for {source} user: {username}")
        self.loading_overlay.start("Fetching games...", f"Getting recent games for {username}")
        self.statusBar().showMessage(f"Fetching games for {username}...")
        
        self.api_worker = APILoaderWorker(api_func, username, **kwargs)
        self.api_worker.finished.connect(lambda games: self.on_games_loaded(games, username, source))
        self.api_worker.error.connect(self.on_api_error)
        self.api_worker.finished.connect(self.loading_overlay.stop)
        self.api_worker.error.connect(lambda _: self.loading_overlay.stop())
        self.api_worker.start()

    def _parse_and_load_game(self, pgn_text, source_data=None, status_msg=""):
        """
        Common pattern: Parse PGN text, attach source data, load first game.
        Returns True on success, False on failure.
        """
        self.games = PGNParser.parse_pgn_text(pgn_text)
        if self.games:
            if source_data:
                for g in self.games:
                    g.source_data = source_data
            self.load_game(self.games[0])
            if status_msg:
                self.statusBar().showMessage(status_msg)
            return True
        else:
            QMessageBox.warning(self, "Error", "Failed to parse game PGN.")
            return False

    def on_games_loaded(self, games_data, username, source):
        self.statusBar().clearMessage()
        if games_data:
            from .dialogs.game_selection_dialog import GameSelectionDialog
            dialog = GameSelectionDialog(games_data, self)
            if dialog.exec():
                selected_game = dialog.selected_game_data
                if selected_game and "pgn" in selected_game:
                    self._parse_and_load_game(
                        selected_game["pgn"], 
                        source_data=selected_game, 
                        status_msg=f"Loaded game for {username} from {source}."
                    )
                else:
                    QMessageBox.warning(self, "Error", "Selected game has no PGN data.")
            else:
                self.statusBar().showMessage("Game selection cancelled.")
        else:
            QMessageBox.warning(self, "No Games", f"No games found for this user on {source}.")

    def on_api_error(self, error_msg):
        self.statusBar().clearMessage()
        logger.error(f"API Load Error: {error_msg}")
        QMessageBox.critical(self, "Error", f"Failed to load games: {error_msg}")

    def load_from_link(self):
        url, ok = QInputDialog.getText(self, "Load from Link", "Enter Chess.com Game URL:")
        if ok and url:
            try:
                api = ChessComAPI()
                game_id = api.extract_game_id(url)
                if game_id:
                    self.loading_overlay.start("Fetching game...", f"Getting game {game_id}")
                    self.api_worker = APILoaderWorker(api.get_game_by_id, game_id, url=url)
                    self.api_worker.finished.connect(lambda data: self._on_link_game_loaded(data, game_id, "Chess.com"))
                    self.api_worker.error.connect(lambda e: (self.loading_overlay.stop(), self.on_api_error(e)))
                    self.api_worker.start()
                else:
                    QMessageBox.warning(self, "Error", "Invalid Chess.com URL.")
            except Exception as e:
                logger.error(f"Link load error: {e}")
                QMessageBox.critical(self, "Error", f"Failed to load from link: {e}")

    def load_game(self, game):
        # If game has no moves but has PGN content (loaded from history), parse it
        if not game.moves and game.pgn_content:
            try:
                parsed_games = PGNParser.parse_pgn_text(game.pgn_content)
                if parsed_games:
                    game.moves = parsed_games[0].moves
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
        # self.move_list_panel.load_game(game) # REMOVED: Method does not exist
        self.move_list_panel.set_game(game)
        self.analysis_panel.set_game(game)
        self.captured_widget.update_captured(None)
        logger.info(f"Game loaded: {game.metadata.white} vs {game.metadata.black}")

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
                 
    
    def load_from_lichess(self):
        # Check for token first
        token = self.config_manager.get("lichess_token") or os.getenv("LICHESS_TOKEN")
        if not token:
            reply = QMessageBox.question(
                self, 
                "Lichess Token Missing", 
                "Lichess API token is not configured. You need a token to load games.\n\nWould you like to configure it in Settings now?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.sidebar.set_active(3)
                self.stack.setCurrentIndex(3)
                if hasattr(self, 'settings_view') and hasattr(self.settings_view, 'lichess_token_input'):
                    self.settings_view.lichess_token_input.setFocus()
            return

        default_user = self.config_manager.get("lichess_username", "")
        username, ok = QInputDialog.getText(self, "Load from Lichess.org", "Enter Lichess.org Username:", text=default_user)
        if ok and username:
            self._load_games_from_api(
                LichessAPI().get_user_games, 
                username.strip(), 
                "Lichess", 
                max_games=5
            )

    def load_from_lichess_link(self):
        url, ok = QInputDialog.getText(self, "Load from Lichess Link", "Enter Lichess.org Game URL:")
        if ok and url:
            try:
                self.statusBar().showMessage("Fetching game from Lichess link...")
                api = LichessAPI()
                game_id = api.extract_game_id(url)
                if game_id:
                    self.loading_overlay.start("Fetching game...", f"Getting game {game_id}")
                    self.api_worker = APILoaderWorker(api.get_game_by_id, game_id)
                    self.api_worker.finished.connect(lambda data: self._on_link_game_loaded(data, game_id, "Lichess"))
                    self.api_worker.error.connect(lambda e: (self.loading_overlay.stop(), self.on_api_error(e)))
                    self.api_worker.start()
                else:
                    QMessageBox.warning(self, "Error", "Invalid Lichess URL.")
                    self.statusBar().clearMessage()
            except Exception as e:
                logger.error(f"Lichess link load error: {e}")
                QMessageBox.critical(self, "Error", f"Failed to load from link: {e}")
                self.statusBar().clearMessage()

    def _on_link_game_loaded(self, game_data, game_id, source):
        """Common handler for link-based game loading."""
        self.loading_overlay.stop()
        if game_data and "pgn" in game_data:
            self._parse_and_load_game(game_data["pgn"], game_data, f"Loaded game {game_id} from {source}.")
        else:
            QMessageBox.warning(self, "Error", "Failed to fetch game data or invalid ID.")

    def start_analysis(self):
        if not self.current_game:
            return
        
        # Check if engine exists
        is_in_path = shutil.which(self.engine_path) is not None
        is_file = os.path.exists(self.engine_path) and os.path.isfile(self.engine_path)
        
        if not (is_in_path or is_file):
             logger.warning(f"Engine not found at: {self.engine_path}")
             QMessageBox.warning(self, "Engine Not Found", "Please configure the engine path in Settings.")
             self.sidebar.set_active(3)
             self.stack.setCurrentIndex(3)
             return

        logger.info("Starting analysis...")
        self.worker = AnalysisWorker(self.analyzer, self.current_game)
        self.worker.progress.connect(self.on_analysis_progress)
        self.worker.finished.connect(self.on_analysis_finished)
        self.worker.error.connect(self.on_analysis_error)
        
        self.statusBar().showMessage("Starting analysis...")
        self.worker.start()

    def on_analysis_progress(self, current, total):
        self.statusBar().showMessage(f"Analyzing move {current}/{total}...")

    def on_analysis_finished(self, game):
        self.statusBar().showMessage("Analysis complete.")
        logger.info("Analysis finished successfully.")
        self.current_game = game
        self.move_list_panel.set_game(game)
        self.analysis_panel.set_game(game)
        # Update other views with new data
        if hasattr(self, 'metrics_view'):
            self.metrics_view.refresh()
        if hasattr(self, 'history_view'):
            self.history_view.load_history()

    def on_analysis_error(self, error_msg):
        self.statusBar().showMessage(f"Analysis failed: {error_msg}")
        logger.error(f"Analysis error: {error_msg}")
        QMessageBox.critical(self, "Analysis Error", error_msg)

    def keyPressEvent(self, event):
        # Global shortcuts (work regardless of game state)
        if event.key() == Qt.Key.Key_F1 or (event.key() == Qt.Key.Key_Question):
            self.show_shortcuts_help()
            return
        
        if event.key() == Qt.Key.Key_Slash and event.modifiers() == Qt.KeyboardModifier.ShiftModifier:
            # Shift+/ = ? on most keyboards
            self.show_shortcuts_help()
            return
        
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            if event.key() == Qt.Key.Key_O:
                self.open_pgn()
                return
            elif event.key() == Qt.Key.Key_A:
                self.start_analysis()
                return
        
        # Game-specific shortcuts
        if not self.current_game:
            super().keyPressEvent(event)
            return

        current_index = self.board_widget.current_move_index
        total_moves = len(self.current_game.moves)
        
        if event.key() == Qt.Key.Key_Left:
            new_index = max(-1, current_index - 1)
            if new_index != current_index:
                self.on_move_selected(new_index)
        
        elif event.key() == Qt.Key.Key_Right:
            new_index = min(total_moves - 1, current_index + 1)
            if new_index != current_index:
                self.on_move_selected(new_index)
        
        elif event.key() == Qt.Key.Key_Home:
            self.go_first()
        
        elif event.key() == Qt.Key.Key_End:
            self.go_last()
        
        elif event.key() == Qt.Key.Key_F:
            self.flip_board()
        
        else:
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
            
            self.captured_widget.update_captured(fen)
            
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

    def on_cache_toggled(self, checked):
        self.analyzer.config["use_cache"] = checked
        
    def resizeEvent(self, event):
        if hasattr(self, 'loading_overlay'):
            self.loading_overlay.resize(self.size())
        super().resizeEvent(event)
