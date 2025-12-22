from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QListWidget, QListWidgetItem, 
                             QPushButton, QHBoxLayout, QLabel, QAbstractItemView)
from PyQt6.QtCore import Qt
from ..styles import Styles
from ..gui_utils import create_button

class GameSelectionDialog(QDialog):
    def __init__(self, games_data, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Game")
        self.resize(500, 400)
        self.games_data = games_data
        self.selected_game_data = None
        
        self.setup_ui()
        self.populate_list()
        
    def setup_ui(self):
        self.setStyleSheet(Styles.get_theme())
        layout = QVBoxLayout(self)
        
        # Header
        lbl_header = QLabel(f"Found {len(self.games_data)} recent games. Select one to load:")
        lbl_header.setStyleSheet(f"color: {Styles.COLOR_TEXT_PRIMARY}; font-size: 14px; font-weight: bold;")
        layout.addWidget(lbl_header)
        
        # List
        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.list_widget.setStyleSheet(f"""
            QListWidget {{
                background-color: {Styles.COLOR_SURFACE};
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 6px;
                font-size: 14px;
            }}
            QListWidget::item {{
                padding: 10px;
                border-bottom: 1px solid {Styles.COLOR_SURFACE_LIGHT};
            }}
            QListWidget::item:selected {{
                background-color: {Styles.COLOR_ACCENT};
                color: white;
            }}
        """)
        self.list_widget.itemDoubleClicked.connect(self.accept_selection)
        layout.addWidget(self.list_widget)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self.btn_cancel = create_button("Cancel", style="secondary", on_click=self.reject)
        btn_layout.addWidget(self.btn_cancel)
        
        self.btn_load = create_button("Load Game", style="primary", on_click=self.accept_selection)
        btn_layout.addWidget(self.btn_load)
        
        layout.addLayout(btn_layout)
        
    def populate_list(self):
        import datetime
        
        for i, game in enumerate(self.games_data):
            # Extract details
            white = game.get("white", {}).get("username", "?")
            white_rating = game.get("white", {}).get("rating", "?")
            black = game.get("black", {}).get("username", "?")
            black_rating = game.get("black", {}).get("rating", "?")
            
            # Result
            # result is usually in pgn headers, but here we might have it in game dict
            w_res = game.get("white", {}).get("result", "")
            b_res = game.get("black", {}).get("result", "")
            
            result_str = ""
            if w_res == "win": result_str = "1-0"
            elif b_res == "win": result_str = "0-1"
            elif any(x in w_res for x in ["agreed", "repetition", "stalemate", "insufficient"]) or \
                 any(x in b_res for x in ["agreed", "repetition", "stalemate", "insufficient"]):
                result_str = "1/2-1/2"
                
            # Time class
            time_class = game.get("time_class", "").capitalize()
            
            # Date
            end_time = game.get("end_time", 0)
            date_str = datetime.datetime.fromtimestamp(end_time).strftime('%Y-%m-%d %H:%M')
            
            text = f"{date_str} | {time_class} | {result_str}\n{white} ({white_rating}) vs {black} ({black_rating})"
            
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, i)
            self.list_widget.addItem(item)
            
        if self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(0)

    def accept_selection(self):
        row = self.list_widget.currentRow()
        if row >= 0:
            index = self.list_widget.item(row).data(Qt.ItemDataRole.UserRole)
            self.selected_game_data = self.games_data[index]
            self.accept()

