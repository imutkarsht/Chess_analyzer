import os
import json
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QSplitter, QFileDialog, QMenuBar,
                             QStatusBar, QMessageBox, QInputDialog, QDialog,
                             QListWidget, QListWidgetItem, QPushButton, QLineEdit, QLabel, QStackedWidget)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QIcon

from .board_widget import BoardWidget
from .analysis_view import MoveListPanel, AnalysisPanel, CapturedPiecesWidget, GameControlsWidget
from .metrics_widget import MetricsWidget
from .analysis_worker import AnalysisWorker
from .sidebar import Sidebar
from .history_view import HistoryView
from .settings_view import SettingsView
from ..backend.pgn_parser import PGNParser
from ..backend.analyzer import Analyzer
from ..utils.resources import ResourceManager
from ..utils.logger import logger
from ..utils.config import ConfigManager
from ..backend.engine import EngineManager
from ..backend.chess_com_api import ChessComAPI
from .styles import Styles
from ..backend.models import MoveAnalysis, GameAnalysis, GameMetadata
from ..backend.game_history import GameHistoryManager
from ..utils.path_utils import get_resource_path

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Chess Analyzer Pro")
        self.resize(1400, 900)
        
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
        self.history_view = HistoryView()
        self.history_view.game_selected.connect(self.load_game_from_history)
        self.stack.addWidget(self.history_view)
        
        # --- Page 2: Metrics View ---
        self.metrics_view = MetricsWidget(self.games)
        self.stack.addWidget(self.metrics_view)
        
        # --- Page 3: Settings View ---
        self.settings_view = SettingsView()
        self.stack.addWidget(self.settings_view)

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
            self.metrics_view.refresh(self.games)
            
        # Update MainWindow Buttons
        if hasattr(self, 'btn_load'):
            self.btn_load.setStyleSheet(Styles.get_control_button_style())
        if hasattr(self, 'btn_analyze'):
            self.btn_analyze.setStyleSheet(Styles.get_button_style())
            
        # Force update
        self.update()

    def switch_page(self, index):
        self.stack.setCurrentIndex(index)
        if index == 2: # Stats page
            self.metrics_view.refresh(self.games)

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
        # Buttons
        btn_layout = QHBoxLayout()
        
        # Load Game Button with Menu
        self.btn_load = QPushButton("Load Game")
        self.btn_load.setStyleSheet(Styles.get_control_button_style())
        
        from PyQt6.QtWidgets import QMenu
        from PyQt6.QtGui import QAction
        load_menu = QMenu(self)
        load_menu.setStyleSheet(f"QMenu {{ background-color: {Styles.COLOR_SURFACE}; color: {Styles.COLOR_TEXT_PRIMARY}; border: 1px solid {Styles.COLOR_BORDER}; }} QMenu::item {{ padding: 5px 20px; }} QMenu::item:selected {{ background-color: {Styles.COLOR_ACCENT}; color: white; }}")
        
        action_pgn = QAction("From PGN File", self)
        action_pgn.triggered.connect(self.open_pgn)
        load_menu.addAction(action_pgn)
        
        action_user = QAction("From Chess.com User", self)
        action_user.triggered.connect(self.load_from_chesscom)
        load_menu.addAction(action_user)
        
        action_link = QAction("From Chess.com Link", self)
        action_link.triggered.connect(self.load_from_link)
        load_menu.addAction(action_link)
        
        self.btn_load.setMenu(load_menu)
        btn_layout.addWidget(self.btn_load)
        
        # Analyze Button
        self.btn_analyze = QPushButton("Analyze Game")
        self.btn_analyze.setStyleSheet(Styles.get_button_style())
        self.btn_analyze.clicked.connect(self.start_analysis)
        btn_layout.addWidget(self.btn_analyze)
        
        left_layout.insertLayout(0, btn_layout) # Insert at top
        
        splitter.addWidget(self.analysis_panel)
        splitter.setSizes([250, 600, 350])

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

    def load_from_chesscom(self):
        username, ok = QInputDialog.getText(self, "Load from Chess.com", "Enter Chess.com Username:")
        if ok and username:
            try:
                self.statusBar().showMessage(f"Fetching games for {username}...")
                api = ChessComAPI()
                # Use get_last_games instead of get_player_games_pgn
                games_data = api.get_last_games(username, limit=5)
                
                if games_data:
                    from .game_selection_dialog import GameSelectionDialog
                    dialog = GameSelectionDialog(games_data, self)
                    if dialog.exec():
                        selected_game = dialog.selected_game_data
                        if selected_game and "pgn" in selected_game:
                            pgn_text = selected_game["pgn"]
                            self.games = PGNParser.parse_pgn_text(pgn_text)
                            if self.games:
                                self.load_game(self.games[0])
                                self.statusBar().showMessage(f"Loaded game for {username}.")
                            else:
                                QMessageBox.warning(self, "Error", "Failed to parse game PGN.")
                        else:
                            QMessageBox.warning(self, "Error", "Selected game has no PGN data.")
                    else:
                        self.statusBar().showMessage("Game selection cancelled.")
                else:
                    QMessageBox.warning(self, "No Games", "No games found for this user.")
                    self.statusBar().clearMessage()
            except Exception as e:
                logger.error(f"Chess.com load error: {e}")
                QMessageBox.critical(self, "Error", f"Failed to load from Chess.com: {e}")
                self.statusBar().clearMessage()

    def load_from_link(self):
        url, ok = QInputDialog.getText(self, "Load from Link", "Enter Chess.com Game URL:")
        if ok and url:
            try:
                self.statusBar().showMessage("Fetching game from link...")
                api = ChessComAPI()
                
                # Extract ID and fetch game
                game_id = api.extract_game_id(url)
                if game_id:
                    game_data = api.get_game_by_id(game_id, url)
                    if game_data and "pgn" in game_data:
                        pgn_text = game_data["pgn"]
                        self.games = PGNParser.parse_pgn_text(pgn_text)
                        if self.games:
                            self.load_game(self.games[0])
                            self.statusBar().showMessage("Game loaded from link.")
                        else:
                            QMessageBox.warning(self, "Error", "Failed to parse game PGN.")
                            self.statusBar().clearMessage()
                    else:
                        QMessageBox.warning(self, "Error", "Failed to fetch game data.")
                        self.statusBar().clearMessage()
                else:
                    QMessageBox.warning(self, "Error", "Invalid Chess.com URL.")
                    self.statusBar().clearMessage()
            except Exception as e:
                logger.error(f"Link load error: {e}")
                QMessageBox.critical(self, "Error", f"Failed to load from link: {e}")
                self.statusBar().clearMessage()

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

        self.current_game = game
        
        white = game.metadata.white
        black = game.metadata.black
        result = game.metadata.result
        w_elo = game.metadata.headers.get("WhiteElo", "?")
        b_elo = game.metadata.headers.get("BlackElo", "?")
        
        info_text = f"{white} ({w_elo}) vs {black} ({b_elo})  [{result}]"
        self.game_info_label.setText(info_text)
        
        self.board_widget.load_game(game)
        self.move_list_panel.set_game(game)
        self.analysis_panel.set_game(game)
        self.captured_widget.update_captured(None)
        logger.info(f"Game loaded: {game.metadata.white} vs {game.metadata.black}")

    def start_analysis(self):
        if not self.current_game:
            return
        
        # Check if engine exists
        import shutil
        is_in_path = shutil.which(self.engine_path) is not None
        is_file = os.path.exists(self.engine_path) and os.path.isfile(self.engine_path)
        
        if not (is_in_path or is_file):
             QMessageBox.warning(self, "Engine Not Found", "Please configure the engine path in Settings.")
             self.sidebar.set_active(2) # Go to settings
             self.stack.setCurrentIndex(2)
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
        self.move_list_panel.refresh()
        self.analysis_panel.refresh()

    def on_analysis_error(self, error_msg):
        self.statusBar().showMessage(f"Analysis failed: {error_msg}")
        logger.error(f"Analysis error: {error_msg}")
        QMessageBox.critical(self, "Analysis Error", error_msg)

    def keyPressEvent(self, event):
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
        
        else:
            super().keyPressEvent(event)

    def on_move_selected(self, index):
        self.board_widget.set_position(index)
        self.move_list_panel.select_move(index)
        
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
