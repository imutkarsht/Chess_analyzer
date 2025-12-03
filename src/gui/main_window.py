import os
import json
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QSplitter, QFileDialog, QMenuBar,
                             QStatusBar, QMessageBox, QInputDialog, QDialog,
                             QListWidget, QListWidgetItem, QPushButton, QLineEdit, QLabel)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QIcon

from .board_widget import BoardWidget
from .game_list import GameListWidget
from .analysis_view import MoveListPanel, AnalysisPanel, CapturedPiecesWidget, GameControlsWidget
from .metrics_widget import MetricsWidget
from .analysis_worker import AnalysisWorker
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
        self.resize(1300, 850) # Increased size for better layout
        
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

        # UI Setup
        self.setup_ui()
        self.setup_menu()
        
        # Apply Theme
        self.setStyleSheet(Styles.DARK_THEME)
        
        # Load History
        self.load_history()

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Splitter for resizable panes
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(2)
        main_layout.addWidget(splitter)
        
        # --- Left Pane: Game List + Move List ---
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)
        
        # Game List (Top) - REMOVED
        # self.game_list = GameListWidget()
        # self.game_list.game_selected.connect(self.load_game)
        # left_layout.addWidget(self.game_list, stretch=1)
        
        # Move List Panel (Bottom)
        self.move_list_panel = MoveListPanel(self.engine_path)
        self.move_list_panel.move_selected.connect(self.on_move_selected)
        left_layout.addWidget(self.move_list_panel, stretch=2)
        
        splitter.addWidget(left_widget)
        
        # --- Center Pane: Board Area ---
        center_widget = QWidget()
        center_layout = QVBoxLayout(center_widget)
        center_layout.setContentsMargins(10, 10, 10, 10) # Reduced margins
        center_layout.setSpacing(10)
        
        # Game Info Label (Top)
        self.game_info_label = QLabel("No Game Loaded")
        self.game_info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.game_info_label.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {Styles.COLOR_TEXT_PRIMARY}; padding: 5px;")
        center_layout.addWidget(self.game_info_label)
        
        # Captured Pieces (Below Info)
        self.captured_widget = CapturedPiecesWidget()
        center_layout.addWidget(self.captured_widget)
        
        # Board (Center)
        self.board_widget = BoardWidget()
        center_layout.addWidget(self.board_widget)
        
        # Controls (Bottom)
        self.controls = GameControlsWidget()
        self.controls.first_clicked.connect(self.go_first)
        self.controls.prev_clicked.connect(self.go_prev)
        self.controls.next_clicked.connect(self.go_next)
        self.controls.last_clicked.connect(self.go_last)
        self.controls.flip_clicked.connect(self.flip_board)
        center_layout.addWidget(self.controls)
        
        splitter.addWidget(center_widget)
        
        # --- Right Pane: Analysis (Graph + Report) ---
        self.analysis_panel = AnalysisPanel()
        self.analysis_panel.cache_toggled.connect(self.on_cache_toggled)
        
        # Connect MoveListPanel lines update to AnalysisPanel
        self.move_list_panel.lines_updated.connect(self.analysis_panel.update_lines)
        
        splitter.addWidget(self.analysis_panel)
        
        # Set initial sizes (Left, Center, Right)
        # Give Center (Board) the most space
        splitter.setSizes([250, 600, 350])

    def setup_menu(self):
        menubar = self.menuBar()
        
        # File Menu
        file_menu = menubar.addMenu("File")
        
        open_action = QAction("Open PGN...", self)
        open_action.triggered.connect(self.open_pgn)
        file_menu.addAction(open_action)
        
        chess_com_action = QAction("Load from Chess.com User...", self)
        chess_com_action.triggered.connect(self.load_from_chess_com)
        file_menu.addAction(chess_com_action)
        
        url_action = QAction("Load from Chess.com URL...", self)
        url_action.triggered.connect(self.load_from_url)
        file_menu.addAction(url_action)
        
        history_action = QAction("History...", self)
        history_action.triggered.connect(self.show_history)
        file_menu.addAction(history_action)
        
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Analysis Menu
        analysis_menu = menubar.addMenu("Analysis")
        analyze_action = QAction("Analyze Game", self)
        analyze_action.triggered.connect(self.start_analysis)
        analysis_menu.addAction(analyze_action)
        
        metrics_action = QAction("Show Metrics", self)
        metrics_action.triggered.connect(self.show_metrics)
        analysis_menu.addAction(metrics_action)
        
        # Settings Menu
        settings_menu = menubar.addMenu("Settings")
        
        config_action = QAction("Configure Engine...", self)
        config_action.triggered.connect(self.configure_engine)
        settings_menu.addAction(config_action)
        
        gemini_action = QAction("Configure Gemini API...", self)
        gemini_action.triggered.connect(self.configure_gemini)
        settings_menu.addAction(gemini_action)
        
        clear_cache_action = QAction("Clear Analysis Cache", self)
        clear_cache_action.triggered.connect(self.clear_cache)
        settings_menu.addAction(clear_cache_action)
        
        clear_all_action = QAction("Clear All Data", self)
        clear_all_action.triggered.connect(self.clear_all_data)
        settings_menu.addAction(clear_all_action)

    def load_history(self):
        """Loads games from history database."""
        try:
            history_games = self.history_manager.get_all_games()
            self.games = []
            for g_dict in history_games:
                metadata = GameMetadata(
                    white=g_dict["white"],
                    black=g_dict["black"],
                    result=g_dict["result"],
                    date=g_dict["date"],
                    event=g_dict["event"]
                )
                
                summary = {}
                if g_dict["summary_json"]:
                    try:
                        summary = json.loads(g_dict["summary_json"])
                    except:
                        pass
                        
                game = GameAnalysis(
                    game_id=g_dict["id"],
                    metadata=metadata,
                    pgn_content=g_dict["pgn"],
                    summary=summary
                )
                self.games.append(game)
                
            # self.game_list.set_games(self.games)
            if self.games:
                logger.info(f"Loaded {len(self.games)} games from history.")
        except Exception as e:
            logger.error(f"Failed to load history: {e}", exc_info=True)

    def show_history(self):
        """Shows the game history in a dialog."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Game History")
        dialog.resize(500, 600)
        layout = QVBoxLayout(dialog)
        
        # Re-use GameListWidget
        game_list = GameListWidget()
        game_list.set_games(self.games)
        
        def on_game_selected(game):
            self.load_game(game)
            dialog.accept()
            
        game_list.game_selected.connect(on_game_selected)
        layout.addWidget(game_list)
        
        btn_layout = QHBoxLayout()
        
        clear_btn = QPushButton("Clear History")
        clear_btn.setStyleSheet(f"background-color: {Styles.COLOR_BLUNDER}; color: white;")
        clear_btn.clicked.connect(lambda: self.clear_history_data(game_list))
        btn_layout.addWidget(clear_btn)
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        btn_layout.addWidget(close_btn)
        
        layout.addLayout(btn_layout)
        
        dialog.exec()

    def clear_history_data(self, game_list_widget):
        reply = QMessageBox.question(
            self, 
            "Clear History", 
            "Are you sure you want to clear all game history? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.history_manager.clear_history()
            self.games = []
            game_list_widget.set_games([])
            QMessageBox.information(self, "Success", "Game history cleared.")

    def clear_all_data(self):
        reply = QMessageBox.question(
            self, 
            "Clear All Data", 
            "Are you sure you want to clear ALL data (History + Analysis Cache)? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.history_manager.clear_history()
            self.analyzer.cache.clear_cache()
            self.games = []
            QMessageBox.information(self, "Success", "All data cleared.")

    def clear_cache(self):
        reply = QMessageBox.question(
            self, 
            "Clear Cache", 
            "Are you sure you want to clear the analysis cache? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.analyzer.cache.clear_cache()
            QMessageBox.information(self, "Success", "Analysis cache cleared.")

    def open_pgn(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Open PGN File", "", "PGN Files (*.pgn);;All Files (*)")
        if file_name:
            logger.info(f"Loading PGN file: {file_name}")
            try:
                self.games = PGNParser.parse_pgn_file(file_name)
                # self.game_list.set_games(self.games)
                if self.games:
                    self.load_game(self.games[0])
                    logger.info(f"Loaded {len(self.games)} games.")
                else:
                    logger.warning("No games found in PGN file.")
            except Exception as e:
                logger.error(f"Failed to parse PGN: {e}", exc_info=True)
                QMessageBox.critical(self, "Error", f"Failed to parse PGN: {e}")

    def load_from_chess_com(self):
        username, ok = QInputDialog.getText(self, "Chess.com Import", "Enter Chess.com Username:")
        if ok and username:
            try:
                self.statusBar().showMessage(f"Fetching games for {username}...")
                games_data = ChessComAPI.get_last_games(username)
                self.statusBar().showMessage("Games fetched.")
                
                if not games_data:
                    QMessageBox.information(self, "No Games", "No recent games found for this user.")
                    return
                
                # Show selection dialog
                dialog = QDialog(self)
                dialog.setWindowTitle("Select Game")
                dialog.resize(400, 300)
                layout = QVBoxLayout(dialog)
                
                list_widget = QListWidget()
                for game in games_data:
                    white = game.get("white", {}).get("username", "?")
                    black = game.get("black", {}).get("username", "?")
                    result = "Draw"
                    if game.get("white", {}).get("result") == "win":
                        result = "1-0"
                    elif game.get("black", {}).get("result") == "win":
                        result = "0-1"
                        
                    time_control = game.get("time_control", "?")
                    item_text = f"{white} vs {black} ({result}) [{time_control}]"
                    item = QListWidgetItem(item_text)
                    item.setData(Qt.ItemDataRole.UserRole, game.get("pgn"))
                    list_widget.addItem(item)
                
                layout.addWidget(list_widget)
                
                btn_load = QPushButton("Load")
                btn_load.clicked.connect(dialog.accept)
                layout.addWidget(btn_load)
                
                if dialog.exec() == QDialog.DialogCode.Accepted:
                    selected_items = list_widget.selectedItems()
                    if selected_items:
                        pgn_text = selected_items[0].data(Qt.ItemDataRole.UserRole)
                        if pgn_text:
                            # Parse PGN string
                            self.games = PGNParser.parse_pgn_text(pgn_text)
                            # self.game_list.set_games(self.games)
                            if self.games:
                                self.load_game(self.games[0])
            except Exception as e:
                logger.error(f"Failed to load games from Chess.com: {e}", exc_info=True)
                QMessageBox.critical(self, "Error", f"Failed to load games: {e}")
                self.statusBar().showMessage("Error fetching games.")

    def load_from_url(self):
        url, ok = QInputDialog.getText(self, "Load Game from URL", "Enter Chess.com Game URL:")
        if ok and url:
            game_id = ChessComAPI.extract_game_id(url)
            if not game_id:
                QMessageBox.warning(self, "Invalid URL", "Could not extract game ID from the URL.")
                return
                
            try:
                self.statusBar().showMessage(f"Fetching game {game_id}...")
                game_data = ChessComAPI.get_game_by_id(game_id, url)
                
                if game_data and "pgn" in game_data:
                    self.games = PGNParser.parse_pgn_text(game_data["pgn"])
                    # self.game_list.set_games(self.games)
                    if self.games:
                        self.load_game(self.games[0])
                    self.statusBar().showMessage("Game loaded.")
                else:
                    QMessageBox.warning(self, "Error", "Could not fetch game data.")
                    self.statusBar().showMessage("Error fetching game.")
                    
            except Exception as e:
                logger.error(f"Failed to load game from URL: {e}", exc_info=True)
                QMessageBox.critical(self, "Error", f"Failed to load game: {e}")
                self.statusBar().showMessage("Error fetching game.")

    def load_game(self, game):
        # If game has no moves but has PGN content (loaded from history), parse it
        if not game.moves and game.pgn_content:
            try:
                parsed_games = PGNParser.parse_pgn_text(game.pgn_content)
                if parsed_games:
                    # Update moves from parsed game
                    game.moves = parsed_games[0].moves
                    # Keep the original summary and metadata if they are better? 
                    # Actually parsed game metadata might be better or same.
                    # But we want to keep the ID and Summary from DB.
            except Exception as e:
                logger.error(f"Failed to parse PGN for history game: {e}")
                QMessageBox.warning(self, "Error", "Failed to load game moves.")
                return

        self.current_game = game
        
        # Update Game Info Label
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
        self.captured_widget.update_captured(None) # Reset captured
        logger.info(f"Game loaded: {game.metadata.white} vs {game.metadata.black}")

    def start_analysis(self):
        if not self.current_game:
            return
        
        # Check if engine exists
        import shutil
        is_in_path = shutil.which(self.engine_path) is not None
        is_file = os.path.exists(self.engine_path) and os.path.isfile(self.engine_path)
        
        if not (is_in_path or is_file):
             reply = QMessageBox.question(
                 self, 
                 "Engine Not Found", 
                 f"Stockfish engine not found at '{self.engine_path}'.\n\nWould you like to locate the Stockfish executable now?",
                 QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
             )
             if reply == QMessageBox.StandardButton.Yes:
                 self.configure_engine()
                 # Re-check after configuration
                 if not (os.path.exists(self.engine_path) and os.path.isfile(self.engine_path)):
                     return
             else:
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

    def show_metrics(self):
        if not self.games:
            QMessageBox.information(self, "Metrics", "No games available for analysis.")
            return
            
        dialog = QDialog(self)
        dialog.setWindowTitle("Analysis Metrics")
        dialog.resize(900, 700)
        layout = QVBoxLayout(dialog)
        
        metrics_widget = MetricsWidget(self.games)
        
        layout.addWidget(metrics_widget)
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)
        
        dialog.exec()

    def configure_engine(self):
        # Cross-platform filter: Executables on Windows, all files on Linux (since they don't always have extensions)
        filter_str = "Executables (*.exe);;All Files (*)" if os.name == 'nt' else "All Files (*)"
        path, _ = QFileDialog.getOpenFileName(self, "Select Stockfish Binary", "", filter_str)
        if path:
            self.engine_path = path
            self.config_manager.set("engine_path", path)
            self.analyzer = Analyzer(EngineManager(self.engine_path))
            # Update MoveListPanel engine
            self.move_list_panel.update_engine_path(self.engine_path)
            QMessageBox.information(self, "Settings", f"Engine path set to: {path}")

    def configure_gemini(self):
        current_key = self.config_manager.get("gemini_api_key", "")
        key, ok = QInputDialog.getText(self, "Configure Gemini API", 
                                     "Enter your Google Gemini API Key:\n(Get one at aistudio.google.com)",
                                     QLineEdit.EchoMode.Password, current_key)
        if ok:
            self.config_manager.set("gemini_api_key", key)
            # Update AnalysisPanel service
            self.analysis_panel.gemini_service.configure(key)
            QMessageBox.information(self, "Settings", "Gemini API Key saved.")

    def keyPressEvent(self, event):
        if not self.current_game:
            super().keyPressEvent(event)
            return

        current_index = self.board_widget.current_move_index
        total_moves = len(self.current_game.moves)
        
        if event.key() == Qt.Key.Key_Left:
            # Go back
            new_index = max(-1, current_index - 1)
            if new_index != current_index:
                self.on_move_selected(new_index)
        
        elif event.key() == Qt.Key.Key_Right:
            # Go forward
            new_index = min(total_moves - 1, current_index + 1)
            if new_index != current_index:
                self.on_move_selected(new_index)
        
        else:
            super().keyPressEvent(event)

    def on_move_selected(self, index):
        self.board_widget.set_position(index)
        self.move_list_panel.select_move(index)
        
        # Update captured pieces
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
            
            # Play Sound
            if 0 <= index < len(moves):
                move = moves[index]
                san = move.san
                if "#" in san or "mate" in san.lower(): # Mate
                    self.resource_manager.play_sound("game_end")
                elif "+" in san: # Check
                    self.resource_manager.play_sound("check")
                elif "x" in san: # Capture
                    self.resource_manager.play_sound("capture")
                elif "O-O" in san: # Castle (Short or Long)
                    self.resource_manager.play_sound("castle")
                else:
                    self.resource_manager.play_sound("move")
            elif index == -1:
                pass

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
