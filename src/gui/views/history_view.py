from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QStyle, QComboBox, QLineEdit, QPushButton, QFrame
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QIcon
from src.gui.components.game_list_widget import GameListWidget
from src.gui.styles import Styles
from src.gui.utils.gui_utils import create_button, create_combobox
from src.backend.storage.game_history import GameHistoryManager
from src.backend.storage.models import GameAnalysis, GameMetadata, MoveAnalysis
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
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        
        # Header Bar Container
        self.header_bar = QFrame()
        self.header_bar.setStyleSheet(f"""
            QFrame {{
                background-color: {Styles.COLOR_BACKGROUND};
                border-bottom: 1px solid {Styles.COLOR_BORDER};
            }}
        """)
        header_layout = QHBoxLayout(self.header_bar)
        header_layout.setContentsMargins(24, 12, 24, 12)
        header_layout.setSpacing(8)
        
        # Title
        self.header_lbl = QLabel("Game History")
        self.header_lbl.setStyleSheet(f"font-size: 22px; font-weight: bold; color: {Styles.COLOR_TEXT_PRIMARY}; background: transparent; border: none;")
        header_layout.addWidget(self.header_lbl)
        
        header_layout.addStretch()

        # Action Buttons in Top Header (Import, Export, Clear, Refresh)
        self.btn_import = self._create_icon_button("Import", "fa5s.file-import", self.import_games)
        header_layout.addWidget(self.btn_import)

        self.btn_export = self._create_icon_button("Export", "fa5s.file-export", self.export_games)
        header_layout.addWidget(self.btn_export)

        self.btn_clear = self._create_icon_button("Clear", "fa5s.trash-alt", self.clear_history, danger=True)
        header_layout.addWidget(self.btn_clear)
        
        self.btn_refresh = create_button("Refresh", style="secondary", on_click=self.load_history, icon_name="fa5s.sync-alt")
        header_layout.addWidget(self.btn_refresh)
        
        self.layout.addWidget(self.header_bar)
        
        # Content Container Widget
        self.content_widget = QWidget()
        self.content_widget.setStyleSheet(f"background-color: {Styles.COLOR_BACKGROUND};")
        content_layout = QVBoxLayout(self.content_widget)
        content_layout.setContentsMargins(24, 16, 24, 16)
        content_layout.setSpacing(16)
        
        # Filter Row
        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(8)
        
        # Search Bar
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search player, opening, date...")
        self.search_input.setStyleSheet(f"""
            QLineEdit {{
                padding: 6px 10px;
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 6px;
                background-color: {Styles.COLOR_SURFACE_LIGHT};
                color: {Styles.COLOR_TEXT_PRIMARY};
                font-size: 13px;
                max-width: 220px;
            }}
            QLineEdit:focus {{
                border: 1px solid {Styles.COLOR_ACCENT};
            }}
        """)
        self.search_input.textChanged.connect(self.apply_filters)
        filter_layout.addWidget(self.search_input)
        
        filter_layout.addSpacing(6)
        
        # Result Filter
        self.result_label = QLabel("Result:")
        self.result_label.setStyleSheet(f"color: {Styles.COLOR_TEXT_PRIMARY}; font-size: 12px;")
        filter_layout.addWidget(self.result_label)
        
        self.result_filter = create_combobox(
            items=["All", "Wins", "Losses", "Draws"],
            on_change=self.apply_filters
        )
        self.result_filter.setMinimumWidth(80)
        filter_layout.addWidget(self.result_filter)

        # Type / Speed Category Filter
        self.type_label = QLabel("Type:")
        self.type_label.setStyleSheet(f"color: {Styles.COLOR_TEXT_PRIMARY}; font-size: 12px;")
        filter_layout.addWidget(self.type_label)

        self.type_filter = create_combobox(
            items=["All", "Rapid", "Blitz", "Bullet", "Classical", "UltraBullet"],
            on_change=self.apply_filters
        )
        self.type_filter.setMinimumWidth(90)
        filter_layout.addWidget(self.type_filter)
        
        # Source Filter
        self.source_label = QLabel("Source:")
        self.source_label.setStyleSheet(f"color: {Styles.COLOR_TEXT_PRIMARY}; font-size: 12px;")
        filter_layout.addWidget(self.source_label)
        
        self.source_filter = create_combobox(
            items=["All", "Chess.com", "Lichess", "File"],
            on_change=self.apply_filters
        )
        self.source_filter.setMinimumWidth(90)
        filter_layout.addWidget(self.source_filter)
        
        filter_layout.addStretch()
        
        # Sort Dropdown
        self.sort_label = QLabel("Sort:")
        self.sort_label.setStyleSheet(f"color: {Styles.COLOR_TEXT_PRIMARY}; font-size: 12px;")
        filter_layout.addWidget(self.sort_label)
        
        self.sort_dropdown = create_combobox(
            items=["Newest First", "Oldest First", "Most Moves", "Fewest Moves"],
            on_change=self.apply_filters
        )
        self.sort_dropdown.setMinimumWidth(115)
        filter_layout.addWidget(self.sort_dropdown)
        
        content_layout.addLayout(filter_layout)
        
        # Game List
        self.game_list = GameListWidget()
        self.game_list.game_selected.connect(self.on_game_selected)
        content_layout.addWidget(self.game_list)
        
        self.layout.addWidget(self.content_widget)
        
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
                    background-color: {Styles.COLOR_SURFACE_LIGHT};
                    color: {Styles.COLOR_BLUNDER};
                    border: 1px solid {Styles.COLOR_BORDER};
                    padding: 8px 16px;
                    border-radius: 6px;
                    font-size: 13px;
                }}
                QPushButton:hover {{
                    background-color: {Styles.COLOR_SURFACE};
                    color: {Styles.COLOR_BLUNDER};
                    border-color: {Styles.COLOR_ACCENT};
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
                    source=g_dict.get("source", "file"),
                    chess960=bool(g_dict.get("chess960", 0))
                )

                from src.backend.storage.pgn_parser import PGNParser
                from src.backend.storage.termination_detector import TerminationDetector

                metadata.speed_category = PGNParser._detect_speed_category(metadata.time_control, metadata.event)
                
                summary = {}
                if g_dict["summary_json"]:
                    try:
                        summary = json.loads(g_dict["summary_json"])
                    except:
                        pass
                        
                moves = []
                if g_dict.get("moves_json"):
                    try:
                        moves_data = json.loads(g_dict["moves_json"])
                        for md in moves_data:
                            move = MoveAnalysis(
                                move_number=md.get("move_number", 0),
                                ply=md.get("ply", 0),
                                san=md.get("san", ""),
                                uci=md.get("uci", ""),
                                fen_before=md.get("fen_before", ""),
                                eval_before_cp=md.get("eval_before_cp"),
                                eval_before_mate=md.get("eval_before_mate"),
                                best_move=md.get("best_move"),
                                best_eval_cp=md.get("best_eval_cp"),
                                best_eval_mate=md.get("best_eval_mate"),
                                pv=md.get("pv", []),
                                eval_after_cp=md.get("eval_after_cp"),
                                eval_after_mate=md.get("eval_after_mate"),
                                win_chance_before=md.get("win_chance_before", 0.5),
                                win_chance_after=md.get("win_chance_after", 0.5),
                                classification=md.get("classification", ""),
                                explanation=md.get("explanation", ""),
                                multi_pvs=md.get("multi_pvs", []),
                                is_book_move=md.get("is_book_move", False),
                                eco=md.get("eco", ""),
                                opening_name=md.get("opening_name", ""),
                                candidate_continuations=md.get("candidate_continuations", []),
                                time_left=md.get("time_left"),
                                time_spent=md.get("time_spent"),
                                raw_clk=md.get("raw_clk"),
                            )
                            moves.append(move)
                    except Exception as e:
                        logging.error(f"Failed to parse moves_json for game {g_dict['id']}: {e}")

                term_mode, term_desc = TerminationDetector.detect_termination(
                    headers={"Result": metadata.result, "White": metadata.white, "Black": metadata.black, "Termination": metadata.termination or ""},
                    moves=moves,
                    starting_fen=metadata.starting_fen,
                    chess960=metadata.chess960
                )
                metadata.termination_mode = term_mode
                metadata.termination_description = term_desc

                game = GameAnalysis(
                    game_id=g_dict["id"],
                    metadata=metadata,
                    pgn_content=g_dict["pgn"],
                    summary=summary,
                    moves=moves
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
        type_filter = self.type_filter.currentText()
        source_filter = self.source_filter.currentText()
        sort_option = self.sort_dropdown.currentText()
        
        filtered_games = self.games.copy()
        
        # Apply Search Filter first
        if search_query:
            filtered_games = self._filter_by_search(filtered_games, search_query)
        
        # Apply Result Filter
        if result_filter != "All":
            filtered_games = self._filter_by_result(filtered_games, result_filter)

        # Apply Type (Speed Category) Filter
        if type_filter != "All":
            filtered_games = self._filter_by_type(filtered_games, type_filter)
        
        # Apply Source Filter
        if source_filter != "All":
            filtered_games = self._filter_by_source(filtered_games, source_filter)
        
        # Apply Sorting
        filtered_games = self._sort_games(filtered_games, sort_option)
        
        self.game_list.set_games(filtered_games, self.usernames)

    def _filter_by_type(self, games, type_filter):
        """Filter games by speed category / game type."""
        from src.backend.storage.pgn_parser import PGNParser
        target = type_filter.lower()
        filtered = []
        for g in games:
            cat = getattr(g.metadata, 'speed_category', None) or PGNParser._detect_speed_category(g.metadata.time_control, g.metadata.event)
            if cat.lower() == target:
                filtered.append(g)
        return filtered
    
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
        from src.gui.utils.gui_utils import confirm_dialog
        if confirm_dialog(self,
                          "Clear History",
                          "Are you sure you want to clear all game history? This cannot be undone.",
                          confirm_label="Clear All"):
            self.history_manager.clear_history()
            self.load_history()

    def export_games(self):
        try:
            from PyQt6.QtWidgets import QFileDialog
            import csv
            from src.gui.components.toast import Toast
            
            file_name, _ = QFileDialog.getSaveFileName(self, "Export Games", "games.csv", "CSV Files (*.csv)")
            if not file_name:
                return
                
            history_games = self.history_manager.get_all_games()
            if not history_games:
                Toast.show_message(self.window(), "No games to export.", "warning")
                return

            # Determine fields. We'll use database keys as headers.
            # Sample first game to get keys, but ensure consistent order
            fieldnames = ["id", "white", "black", "result", "date", "event", "white_elo", "black_elo", 
                          "time_control", "eco", "termination", "opening", "source", "pgn", "summary_json", "moves_json", "timestamp", "starting_fen", "chess960"]
            
            with open(file_name, mode='w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                
                for game_dict in history_games:
                    row = {k: game_dict.get(k) for k in fieldnames}
                    writer.writerow(row)
                    
            Toast.show_message(self.window(), f"Exported {len(history_games)} games.", "success")
            
        except Exception as e:
            logging.error(f"Export failed: {e}")
            from src.gui.components.toast import Toast
            Toast.show_message(self.window(), f"Export failed: {e}", "error")

    def import_games(self):
        try:
            from PyQt6.QtWidgets import QFileDialog
            import csv
            from src.backend.storage.pgn_parser import PGNParser
            from src.gui.components.toast import Toast
            
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
                        continue
                        
                    if self.history_manager.game_exists(game_id):
                        skipped_count += 1
                        continue
                        
                    try:
                        summary = {}
                        if row.get("summary_json"):
                            try:
                                summary = json.loads(row.get("summary_json"))
                            except Exception:
                                pass

                        moves = []
                        if row.get("moves_json"):
                            try:
                                moves_data = json.loads(row.get("moves_json"))
                                for md in moves_data:
                                    moves.append(MoveAnalysis(
                                        move_number=md.get("move_number", 0),
                                        ply=md.get("ply", 0),
                                        san=md.get("san", ""),
                                        uci=md.get("uci", ""),
                                        fen_before=md.get("fen_before", ""),
                                        eval_before_cp=md.get("eval_before_cp"),
                                        eval_before_mate=md.get("eval_before_mate"),
                                        best_move=md.get("best_move"),
                                        best_eval_cp=md.get("best_eval_cp"),
                                        best_eval_mate=md.get("best_eval_mate"),
                                        pv=md.get("pv", []),
                                        eval_after_cp=md.get("eval_after_cp"),
                                        eval_after_mate=md.get("eval_after_mate"),
                                        win_chance_before=md.get("win_chance_before", 0.5),
                                        win_chance_after=md.get("win_chance_after", 0.5),
                                        classification=md.get("classification", ""),
                                        explanation=md.get("explanation", ""),
                                        multi_pvs=md.get("multi_pvs", []),
                                        is_book_move=md.get("is_book_move", False),
                                        eco=md.get("eco", ""),
                                        opening_name=md.get("opening_name", ""),
                                        candidate_continuations=md.get("candidate_continuations", []),
                                        time_left=md.get("time_left"),
                                        time_spent=md.get("time_spent"),
                                        raw_clk=md.get("raw_clk"),
                                    ))
                            except Exception:
                                pass

                        # Fallback: re-parse PGN text if moves list is empty
                        pgn_text = row.get("pgn")
                        if not moves and pgn_text:
                            parsed = PGNParser.parse_pgn_text(pgn_text)
                            if parsed and parsed[0].moves:
                                moves = parsed[0].moves

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
                            source=row.get("source", "file"),
                            chess960=row.get("chess960") == "1"
                        )
                        
                        game = GameAnalysis(
                            game_id=game_id,
                            metadata=metadata,
                            moves=moves,
                            pgn_content=pgn_text,
                            summary=summary
                        )
                        
                        self.history_manager.save_game(game, pgn_text)
                        imported_count += 1
                        
                    except Exception as row_e:
                        logging.warning(f"Failed to parse row {game_id}: {row_e}")
                        
            self.load_history()
            Toast.show_message(self.window(), f"Imported: {imported_count}, Skipped: {skipped_count}", "success")
            
        except Exception as e:
            logging.error(f"Import failed: {e}")
            from src.gui.components.toast import Toast
            Toast.show_message(self.window(), f"Import failed: {e}", "error")

    def refresh_styles(self):
        """Re-apply styles with the updated accent color."""
        # Refresh root widget background
        self.setStyleSheet(f"background-color: {Styles.COLOR_BACKGROUND};")

        # Refresh header bar style
        if hasattr(self, 'header_bar') and self.header_bar:
            self.header_bar.setStyleSheet(f"""
                QFrame {{
                    background-color: {Styles.COLOR_BACKGROUND};
                    border-bottom: 1px solid {Styles.COLOR_BORDER};
                }}
            """)

        # Refresh title label
        if hasattr(self, 'header_lbl') and self.header_lbl:
            self.header_lbl.setStyleSheet(f"font-size: 24px; font-weight: bold; color: {Styles.COLOR_TEXT_PRIMARY}; background: transparent; border: none;")
            
        # Refresh refresh button
        if hasattr(self, 'btn_refresh'):
            self.btn_refresh.setStyleSheet(Styles.get_control_button_style())
            
        # Refresh search input focus border
        if hasattr(self, 'search_input'):
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
            
        # Refresh filters dropdowns
        if hasattr(self, 'result_filter'):
            self.result_filter.setStyleSheet(Styles.get_combobox_style())
        if hasattr(self, 'source_filter'):
            self.source_filter.setStyleSheet(Styles.get_combobox_style())
        if hasattr(self, 'sort_dropdown'):
            self.sort_dropdown.setStyleSheet(Styles.get_combobox_style())
            
        # Refresh bottom buttons
        if hasattr(self, 'btn_export'):
            self.btn_export.setStyleSheet(f"""
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
        if hasattr(self, 'btn_import'):
            self.btn_import.setStyleSheet(f"""
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
        if hasattr(self, 'btn_clear'):
            self.btn_clear.setStyleSheet(f"""
                QPushButton {{
                    background-color: {Styles.COLOR_SURFACE_LIGHT};
                    color: {Styles.COLOR_BLUNDER};
                    border: 1px solid {Styles.COLOR_BORDER};
                    padding: 8px 16px;
                    border-radius: 6px;
                    font-size: 13px;
                }}
                QPushButton:hover {{
                    background-color: {Styles.COLOR_SURFACE};
                    color: {Styles.COLOR_BLUNDER};
                    border-color: {Styles.COLOR_ACCENT};
                }}
            """)
            
        # Cascade refresh to nested game list
        if hasattr(self, 'content_widget') and self.content_widget:
            self.content_widget.setStyleSheet(f"background-color: {Styles.COLOR_BACKGROUND};")
        if hasattr(self, 'game_list'):
            self.game_list.refresh_styles()
            
        if hasattr(self, 'filter_label') and self.filter_label:
            self.filter_label.setStyleSheet(f"color: {Styles.COLOR_TEXT_SECONDARY}; font-size: 13px;")
        for lbl_name in ('result_label', 'source_label', 'sort_label'):
            if hasattr(self, lbl_name):
                lbl = getattr(self, lbl_name)
                if lbl:
                    lbl.setStyleSheet(f"color: {Styles.COLOR_TEXT_PRIMARY}; font-size: 13px;")

