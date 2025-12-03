from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QMessageBox
from PyQt6.QtCore import pyqtSignal, Qt
from .game_list import GameListWidget
from .styles import Styles
from ..backend.game_history import GameHistoryManager
from ..backend.models import GameAnalysis, GameMetadata
import json
import logging

class HistoryView(QWidget):
    game_selected = pyqtSignal(object) # Emits GameAnalysis object

    def __init__(self):
        super().__init__()
        self.history_manager = GameHistoryManager()
        self.games = []
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(20, 20, 20, 20)
        self.layout.setSpacing(20)
        
        # Header
        header = QLabel("Game History")
        header.setStyleSheet(f"font-size: 24px; font-weight: bold; color: {Styles.COLOR_TEXT_PRIMARY};")
        self.layout.addWidget(header)
        
        # Game List
        self.game_list = GameListWidget()
        self.game_list.game_selected.connect(self.on_game_selected)
        self.layout.addWidget(self.game_list)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        self.btn_refresh = QPushButton("Refresh")
        self.btn_refresh.setStyleSheet(Styles.get_control_button_style())
        self.btn_refresh.clicked.connect(self.load_history)
        btn_layout.addWidget(self.btn_refresh)
        
        btn_layout.addStretch()
        
        self.btn_clear = QPushButton("Clear History")
        self.btn_clear.setStyleSheet(f"background-color: {Styles.COLOR_BLUNDER}; color: white; border: none; padding: 8px 16px; border-radius: 4px;")
        self.btn_clear.clicked.connect(self.clear_history)
        btn_layout.addWidget(self.btn_clear)
        
        self.layout.addLayout(btn_layout)
        
        # Load initial data
        self.load_history()

    def load_history(self):
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
            
            self.game_list.set_games(self.games)
        except Exception as e:
            logging.error(f"Failed to load history: {e}")

    def on_game_selected(self, game):
        self.game_selected.emit(game)

    def clear_history(self):
        reply = QMessageBox.question(
            self, 
            "Clear History", 
            "Are you sure you want to clear all game history? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.history_manager.clear_history()
            self.load_history()
