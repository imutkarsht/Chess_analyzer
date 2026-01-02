from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QMessageBox, QStyle, QComboBox, QLineEdit, QPushButton
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QIcon
from ..game_list import GameListWidget
from ..styles import Styles
from ..gui_utils import create_button, create_combobox
from ...backend.game_history import GameHistoryManager
from ...backend.models import GameAnalysis, GameMetadata
import json
import logging
import re

try:
    import qtawesome as qta
    HAS_QTAWESOME = True
except ImportError:
    HAS_QTAWESOME = False

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
        
        # Filter Row
        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(16)
        
        # Search Bar
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search by player, opening, event...")
        self.search_input.setStyleSheet(f"""
            QLineEdit {{
                padding: 8px 12px;
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 6px;
                background-color: {Styles.COLOR_SURFACE_LIGHT};
                color: {Styles.COLOR_TEXT_PRIMARY};
                font-size: 13px;
                min-width: 250px;
            }}
            QLineEdit:focus {{
                border: 1px solid {Styles.COLOR_ACCENT};
            }}
        """)
        self.search_input.textChanged.connect(self.apply_filters)
        filter_layout.addWidget(self.search_input)
        
        filter_layout.addSpacing(20)
        
        # Filter By Label
        filter_label = QLabel("Filter by:")
        filter_label.setStyleSheet(f"color: {Styles.COLOR_TEXT_SECONDARY}; font-size: 13px;")
        filter_layout.addWidget(filter_label)
        
        # Result Filter
        result_label = QLabel("Result:")
        result_label.setStyleSheet(f"color: {Styles.COLOR_TEXT_PRIMARY}; font-size: 13px;")
        filter_layout.addWidget(result_label)
        
        self.result_filter = create_combobox(
            items=["All", "Wins", "Losses", "Draws"],
            on_change=self.apply_filters
        )
        self.result_filter.setMinimumWidth(100)
        filter_layout.addWidget(self.result_filter)
        
        # Source Filter
        source_label = QLabel("Source:")
        source_label.setStyleSheet(f"color: {Styles.COLOR_TEXT_PRIMARY}; font-size: 13px;")
        filter_layout.addWidget(source_label)
        
        self.source_filter = create_combobox(
            items=["All", "Chess.com", "Lichess", "File"],
            on_change=self.apply_filters
        )
        self.source_filter.setMinimumWidth(100)
        filter_layout.addWidget(self.source_filter)
        
        filter_layout.addStretch()
        
        # Sort Dropdown
        sort_label = QLabel("Sort by:")
        sort_label.setStyleSheet(f"color: {Styles.COLOR_TEXT_PRIMARY}; font-size: 13px;")
        filter_layout.addWidget(sort_label)
        
        self.sort_dropdown = create_combobox(
            items=["Newest First", "Oldest First", "Most Moves", "Fewest Moves"],
            on_change=self.apply_filters
        )
        self.sort_dropdown.setMinimumWidth(130)
        filter_layout.addWidget(self.sort_dropdown)
        
        self.layout.addLayout(filter_layout)
        
        # Game List
        self.game_list = GameListWidget()
        self.game_list.game_selected.connect(self.on_game_selected)
        self.layout.addWidget(self.game_list)
        
        # Bottom Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)
        
        # Export Button
        self.btn_export = self._create_icon_button("Export", "fa5s.file-export", self.export_games)
        btn_layout.addWidget(self.btn_export)
        
        # Import Button
        self.btn_import = self._create_icon_button("Import", "fa5s.file-import", self.import_games)
        btn_layout.addWidget(self.btn_import)
        
        btn_layout.addStretch()
        
        # Clear History (Danger action)
        self.btn_clear = self._create_icon_button("Clear History", "fa5s.trash-alt", self.clear_history, danger=True)
        btn_layout.addWidget(self.btn_clear)
        
        self.layout.addLayout(btn_layout)
        
        # Load initial data
        self.load_history()
    
    def _create_icon_button(self, text, icon_name, callback, danger=False):
        """Create a styled button with qtawesome icon."""
        btn = QPushButton(f"  {text}")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        
        if HAS_QTAWESOME:
            icon_color = Styles.COLOR_BLUNDER if danger else Styles.COLOR_TEXT_SECONDARY
            btn.setIcon(qta.icon(icon_name, color=icon_color))
        
        if danger:
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent;
                    color: {Styles.COLOR_BLUNDER};
                    border: 1px solid {Styles.COLOR_BLUNDER};
                    padding: 8px 16px;
                    border-radius: 6px;
                    font-size: 13px;
                }}
                QPushButton:hover {{
                    background-color: {Styles.COLOR_BLUNDER};
                    color: white;
                }}
            """)
        else:
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {Styles.COLOR_SURFACE_LIGHT};
                    color: {Styles.COLOR_TEXT_PRIMARY};
                    border: 1px solid {Styles.COLOR_BORDER};
                    padding: 8px 16px;
                    border-radius: 6px;
                    font-size: 13px;
                }}
                QPushButton:hover {{
                    background-color: {Styles.COLOR_SURFACE};
                    border-color: {Styles.COLOR_ACCENT};
                }}
            """)
        
        btn.clicked.connect(callback)
        return btn

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
            
            self.usernames = []
            if self.config_manager:
                chesscom = self.config_manager.get("chesscom_username", "")
                lichess = self.config_manager.get("lichess_username", "")
                self.usernames = [u for u in [chesscom, lichess] if u]
            
            # Apply filters after loading
            self.apply_filters()
        except Exception as e:
            logging.error(f"Failed to load history: {e}")

    def apply_filters(self):
        """Apply search, filter, and sort settings to the game list."""
        search_query = self.search_input.text().strip().lower()
        result_filter = self.result_filter.currentText()
        source_filter = self.source_filter.currentText()
        sort_option = self.sort_dropdown.currentText()
        
        filtered_games = self.games.copy()
        
        # Apply Search Filter first
        if search_query:
            filtered_games = self._filter_by_search(filtered_games, search_query)
        
        # Apply Result Filter
        if result_filter != "All":
            filtered_games = self._filter_by_result(filtered_games, result_filter)
        
        # Apply Source Filter
        if source_filter != "All":
            filtered_games = self._filter_by_source(filtered_games, source_filter)
        
        # Apply Sorting
        filtered_games = self._sort_games(filtered_games, sort_option)
        
        self.game_list.set_games(filtered_games, self.usernames)
    
    def _filter_by_search(self, games, query):
        """Filter games by search query matching player names, opening, event, or date."""
        filtered = []
        
        for game in games:
            # Get searchable fields
            white = (game.metadata.white or "").lower()
            black = (game.metadata.black or "").lower()
            opening = (game.metadata.opening or "").lower()
            event = (game.metadata.event or "").lower()
            date = (game.metadata.date or "").lower()
            eco = (game.metadata.eco or "").lower()
            
            # Check if query matches any field
            if (query in white or 
                query in black or 
                query in opening or 
                query in event or 
                query in date or
                query in eco):
                filtered.append(game)
        
        return filtered
    
    def _filter_by_result(self, games, result_filter):
        """Filter games by result (wins/losses/draws from user perspective)."""
        filtered = []
        usernames_lower = [u.lower() for u in self.usernames] if self.usernames else []
        
        for game in games:
            result = game.metadata.result
            white = game.metadata.white.lower() if game.metadata.white else ""
            black = game.metadata.black.lower() if game.metadata.black else ""
            
            # Determine user color
            user_is_white = white in usernames_lower
            user_is_black = black in usernames_lower
            
            if result_filter == "Wins":
                if (result == "1-0" and user_is_white) or (result == "0-1" and user_is_black):
                    filtered.append(game)
            elif result_filter == "Losses":
                if (result == "0-1" and user_is_white) or (result == "1-0" and user_is_black):
                    filtered.append(game)
            elif result_filter == "Draws":
                if result == "1/2-1/2":
                    filtered.append(game)
        
        return filtered
    
    def _filter_by_source(self, games, source_filter):
        """Filter games by source platform."""
        source_map = {
            "Chess.com": "chesscom",
            "Lichess": "lichess",
            "File": "file"
        }
        target_source = source_map.get(source_filter, "")
        
        return [g for g in games if getattr(g.metadata, 'source', 'file') == target_source]
    
    def _sort_games(self, games, sort_option):
        """Sort games based on selected option."""
        if sort_option == "Newest First":
            # Sort by timestamp descending (default order from DB)
            return games  # Already sorted by timestamp DESC
        elif sort_option == "Oldest First":
            return list(reversed(games))
        elif sort_option == "Most Moves" or sort_option == "Fewest Moves":
            # Calculate move count for sorting
            def get_move_count(game):
                if hasattr(game, 'moves') and game.moves:
                    return (len(game.moves) + 1) // 2
                elif hasattr(game, 'pgn_content') and game.pgn_content:
                    moves = re.findall(r'(?:^|\s)(\d{1,3})\.\s+[A-Za-z]', game.pgn_content, re.MULTILINE)
                    if moves:
                        move_nums = [int(m) for m in moves if int(m) <= 500]
                        if move_nums:
                            return max(move_nums)
                return 0
            
            reverse = (sort_option == "Most Moves")
            return sorted(games, key=get_move_count, reverse=reverse)
        
        return games

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

