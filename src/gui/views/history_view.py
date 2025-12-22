from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QMessageBox, QStyle
from PyQt6.QtCore import pyqtSignal, Qt
from ..game_list import GameListWidget
from ..styles import Styles
from ..gui_utils import create_button
from ...backend.game_history import GameHistoryManager
from ...backend.models import GameAnalysis, GameMetadata
import json
import logging

class HistoryView(QWidget):
    game_selected = pyqtSignal(object) # Emits GameAnalysis object

    def __init__(self, config_manager=None):
        super().__init__()
        self.config_manager = config_manager
        self.history_manager = GameHistoryManager()
        self.games = []
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(20, 20, 20, 20)
        self.layout.setSpacing(20)
        
        # Header Row
        header_layout = QHBoxLayout()
        
        # Title
        header_lbl = QLabel("Game History")
        header_lbl.setStyleSheet(f"font-size: 24px; font-weight: bold; color: {Styles.COLOR_TEXT_PRIMARY};")
        header_layout.addWidget(header_lbl)
        
        header_layout.addStretch()
        
        # Refresh Button (Top-Right)
        self.btn_refresh = create_button("Refresh", style="secondary", on_click=self.load_history)
        header_layout.addWidget(self.btn_refresh)
        
        self.layout.addLayout(header_layout)
        
        # Game List
        self.game_list = GameListWidget()
        self.game_list.game_selected.connect(self.on_game_selected)
        self.layout.addWidget(self.game_list)
        
        # Bottom Buttons
        btn_layout = QHBoxLayout()
        
        # Import/Export (Bottom-Left)
        self.btn_export = create_button(" Export Games", style="export", on_click=self.export_games)
        self.btn_export.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton))
        btn_layout.addWidget(self.btn_export)
        
        self.btn_import = create_button(" Import Games", style="import", on_click=self.import_games)
        self.btn_import.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton))
        btn_layout.addWidget(self.btn_import)
        
        btn_layout.addStretch()
        
        # Clear History (Bottom-Right)
        self.btn_clear = create_button("Clear History", style="secondary", on_click=self.clear_history)
        self.btn_clear.setStyleSheet(f"background-color: {Styles.COLOR_BLUNDER}; color: white; border: none; padding: 8px 16px; border-radius: 4px;")
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
                    event=g_dict["event"],
                    white_elo=g_dict.get("white_elo"),
                    black_elo=g_dict.get("black_elo"),
                    time_control=g_dict.get("time_control"),
                    eco=g_dict.get("eco"),
                    opening=g_dict.get("opening"),
                    termination=g_dict.get("termination"),
                    source=g_dict.get("source", "file")
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
            
            usernames = []
            if self.config_manager:
                chesscom = self.config_manager.get("chesscom_username", "")
                lichess = self.config_manager.get("lichess_username", "")
                usernames = [u for u in [chesscom, lichess] if u]
                
            self.game_list.set_games(self.games, usernames)
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

    def export_games(self):
        try:
            from PyQt6.QtWidgets import QFileDialog
            import csv
            
            file_name, _ = QFileDialog.getSaveFileName(self, "Export Games", "games.csv", "CSV Files (*.csv)")
            if not file_name:
                return
                
            history_games = self.history_manager.get_all_games()
            if not history_games:
                QMessageBox.information(self, "No Games", "No games to export.")
                return

            # Determine fields. We'll use database keys as headers.
            # Sample first game to get keys, but ensure consistent order
            fieldnames = ["id", "white", "black", "result", "date", "event", "white_elo", "black_elo", 
                          "time_control", "eco", "termination", "opening", "source", "pgn", "summary_json", "timestamp", "starting_fen"]
            
            with open(file_name, mode='w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                
                for game_dict in history_games:
                    # Filter dict to only fieldnames (in case of extras)
                    row = {k: game_dict.get(k) for k in fieldnames}
                    writer.writerow(row)
                    
            QMessageBox.information(self, "Success", f"Exported {len(history_games)} games to {file_name}.")
            
        except Exception as e:
            logging.error(f"Export failed: {e}")
            QMessageBox.critical(self, "Export Error", f"Failed to export games: {e}")

    def import_games(self):
        try:
            from PyQt6.QtWidgets import QFileDialog
            import csv
            import time
            
            file_name, _ = QFileDialog.getOpenFileName(self, "Import Games", "", "CSV Files (*.csv)")
            if not file_name:
                return
                
            imported_count = 0
            skipped_count = 0
            
            with open(file_name, mode='r', newline='', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                
                for row in reader:
                    game_id = row.get("id")
                    if not game_id:
                        continue # Skip invalid rows
                        
                    # Check existence
                    if self.history_manager.game_exists(game_id):
                        skipped_count += 1
                        continue
                        
                    
                    try:
                        summary = {}
                        if row.get("summary_json"):
                            summary = json.loads(row.get("summary_json"))
                            
                        metadata = GameMetadata(
                            white=row.get("white"),
                            black=row.get("black"),
                            result=row.get("result"),
                            date=row.get("date"),
                            event=row.get("event"),
                            white_elo=row.get("white_elo"),
                            black_elo=row.get("black_elo"),
                            time_control=row.get("time_control"),
                            eco=row.get("eco"),
                            termination=row.get("termination"),
                            opening=row.get("opening"),
                            starting_fen=row.get("starting_fen"),
                            source=row.get("source", "file")
                        )
                        
                        game = GameAnalysis(
                            game_id=game_id,
                            metadata=metadata,
                            pgn_content=row.get("pgn"),
                            summary=summary
                        )
                        
                        self.history_manager.save_game(game, row.get("pgn"))
                        imported_count += 1
                        
                    except Exception as row_e:
                        logging.warning(f"Failed to parse row {game_id}: {row_e}")
                        
            self.load_history()
            QMessageBox.information(self, "Import Complete", f"Imported: {imported_count}\nSkipped (Existing): {skipped_count}")
            
        except Exception as e:
            logging.error(f"Import failed: {e}")
            QMessageBox.critical(self, "Import Error", f"Failed to import games: {e}")

