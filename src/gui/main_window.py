import sys
import os
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QSplitter, QFileDialog, QMenuBar, QMenu,
                             QToolBar, QStatusBar, QMessageBox, QInputDialog, QDialog,
                             QListWidget, QListWidgetItem, QPushButton)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QIcon

from .board_widget import BoardWidget
from .game_list import GameListWidget
from .analysis_view import AnalysisViewWidget
from .graph_widget import GraphWidget
from .analysis_worker import AnalysisWorker
from ..backend.pgn_parser import PGNParser
from ..backend.analyzer import Analyzer
from ..backend.engine import EngineManager
from ..backend.chess_com_api import ChessComAPI
from .styles import Styles

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Chess Analyzer Pro")
        self.resize(1200, 800)
        
        # State
        self.games = []
        self.current_game = None
        self.engine_path = "stockfish" # Default, needs config
        self.analyzer = Analyzer(EngineManager(self.engine_path))

        # UI Setup
        self.setup_ui()
        self.setup_menu()
        
        # Apply Theme
        self.setStyleSheet(Styles.DARK_THEME)

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
        
        # Left Pane: Game List
        self.game_list = GameListWidget()
        self.game_list.game_selected.connect(self.load_game)
        splitter.addWidget(self.game_list)
        
        # Center Pane: Board
        self.board_widget = BoardWidget()
        splitter.addWidget(self.board_widget)
        
        # Right Pane: Analysis
        self.analysis_view = AnalysisViewWidget()
        self.analysis_view.move_selected.connect(self.board_widget.set_position)
        
        # Connect Control Signals
        self.analysis_view.first_clicked.connect(self.go_first)
        self.analysis_view.prev_clicked.connect(self.go_prev)
        self.analysis_view.next_clicked.connect(self.go_next)
        self.analysis_view.last_clicked.connect(self.go_last)
        self.analysis_view.last_clicked.connect(self.go_last)
        self.analysis_view.flip_clicked.connect(self.flip_board)
        self.analysis_view.cache_toggled.connect(self.on_cache_toggled)
        
        # Analysis Layout (Graph + Table)
        analysis_container = QWidget()
        analysis_layout = QVBoxLayout(analysis_container)
        analysis_layout.setContentsMargins(0, 0, 0, 0)
        analysis_layout.setSpacing(0)
        
        self.graph_widget = GraphWidget()
        analysis_layout.addWidget(self.graph_widget)
        analysis_layout.addWidget(self.analysis_view)
        
        # Set stretch factors for analysis layout
        analysis_layout.setStretch(0, 1) # Graph
        analysis_layout.setStretch(1, 2) # Table
        
        splitter.addWidget(analysis_container)
        
        # Set initial sizes
        splitter.setSizes([250, 650, 400])

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
        
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Analysis Menu
        analysis_menu = menubar.addMenu("Analysis")
        analyze_action = QAction("Analyze Game", self)
        analyze_action.triggered.connect(self.start_analysis)
        analysis_menu.addAction(analyze_action)
        
        # Settings Menu
        settings_menu = menubar.addMenu("Settings")
        config_action = QAction("Configure Engine...", self)
        config_action.triggered.connect(self.configure_engine)
        settings_menu.addAction(config_action)

    def open_pgn(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Open PGN File", "", "PGN Files (*.pgn);;All Files (*)")
        if file_name:
            try:
                self.games = PGNParser.parse_pgn_file(file_name)
                self.game_list.set_games(self.games)
                if self.games:
                    self.load_game(self.games[0])
            except Exception as e:
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
                            self.game_list.set_games(self.games)
                            if self.games:
                                self.load_game(self.games[0])
            except Exception as e:
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
                    self.game_list.set_games(self.games)
                    if self.games:
                        self.load_game(self.games[0])
                    self.statusBar().showMessage("Game loaded.")
                else:
                    QMessageBox.warning(self, "Error", "Could not fetch game data.")
                    self.statusBar().showMessage("Error fetching game.")
                    
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load game: {e}")
                self.statusBar().showMessage("Error fetching game.")

    def load_game(self, game):
        self.current_game = game
        self.board_widget.load_game(game)
        self.analysis_view.set_game(game)
        self.graph_widget.clear()

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
        self.current_game = game
        self.analysis_view.refresh()
        self.graph_widget.plot_game(game)

    def on_analysis_error(self, error_msg):
        self.statusBar().showMessage(f"Analysis failed: {error_msg}")
        QMessageBox.critical(self, "Analysis Error", error_msg)

    def configure_engine(self):
        # Cross-platform filter: Executables on Windows, all files on Linux (since they don't always have extensions)
        filter_str = "Executables (*.exe);;All Files (*)" if os.name == 'nt' else "All Files (*)"
        path, _ = QFileDialog.getOpenFileName(self, "Select Stockfish Binary", "", filter_str)
        if path:
            self.engine_path = path
            self.analyzer = Analyzer(EngineManager(self.engine_path))
            QMessageBox.information(self, "Settings", f"Engine path set to: {path}")

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
                self.board_widget.set_position(new_index)
                self.analysis_view.select_move(new_index)
        
        elif event.key() == Qt.Key.Key_Right:
            # Go forward
            new_index = min(total_moves - 1, current_index + 1)
            if new_index != current_index:
                self.board_widget.set_position(new_index)
                self.analysis_view.select_move(new_index)
        
        else:
            super().keyPressEvent(event)

    def go_first(self):
        if self.current_game:
            self.board_widget.set_position(-1)
            self.analysis_view.select_move(-1)

    def go_prev(self):
        if self.current_game:
            current = self.board_widget.current_move_index
            new_index = max(-1, current - 1)
            self.board_widget.set_position(new_index)
            self.analysis_view.select_move(new_index)

    def go_next(self):
        if self.current_game:
            current = self.board_widget.current_move_index
            total = len(self.current_game.moves)
            new_index = min(total - 1, current + 1)
            self.board_widget.set_position(new_index)
            self.analysis_view.select_move(new_index)

    def go_last(self):
        if self.current_game:
            total = len(self.current_game.moves)
            self.board_widget.set_position(total - 1)
            self.analysis_view.select_move(total - 1)

    def flip_board(self):
        self.board_widget.flip_board()

    def on_cache_toggled(self, checked):
        self.analyzer.config["use_cache"] = checked

