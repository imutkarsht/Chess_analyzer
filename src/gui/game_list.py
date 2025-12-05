from PyQt6.QtWidgets import (QListWidget, QListWidgetItem, QVBoxLayout, QWidget, QLabel, 
                             QHBoxLayout, QFrame)
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QColor
from PyQt6.QtGui import QColor
from .styles import Styles
from ..utils.logger import logger

class GameListItemWidget(QWidget):
    def __init__(self, game, usernames=None):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 15, 20, 15)
        layout.setSpacing(8)
        
        # Header: Players and Result
        header_layout = QHBoxLayout()
        
        players_label = QLabel(f"<b>{game.metadata.white}</b> vs <b>{game.metadata.black}</b>")
        players_label.setStyleSheet(f"color: {Styles.COLOR_TEXT_PRIMARY}; font-size: 16px;")
        header_layout.addWidget(players_label)
        
        header_layout.addStretch()
        
        result_text = game.metadata.result
        result_color = Styles.COLOR_TEXT_SECONDARY
        
        # Determine user color and win/loss
        user_color = None
        if usernames:
            white = game.metadata.white.lower()
            black = game.metadata.black.lower()
            known_users = [u.lower() for u in usernames]
            
            if white in known_users:
                user_color = 'white'
            elif black in known_users:
                user_color = 'black'
        
        if user_color:
            if result_text == "1-0":
                if user_color == 'white':
                    result_color = Styles.COLOR_BEST # Green (Win)
                else:
                    result_color = Styles.COLOR_BLUNDER # Red (Loss)
            elif result_text == "0-1":
                if user_color == 'black':
                    result_color = Styles.COLOR_BEST # Green (Win)
                else:
                    result_color = Styles.COLOR_BLUNDER # Red (Loss)
            elif result_text == "1/2-1/2":
                result_color = Styles.COLOR_TEXT_SECONDARY # Grey
        else:
            # Fallback if user not identified
            if result_text == "1-0":
                result_color = Styles.COLOR_BEST 
            elif result_text == "0-1":
                result_color = Styles.COLOR_BLUNDER 
            elif result_text == "1/2-1/2":
                result_color = Styles.COLOR_TEXT_SECONDARY
            
        result_label = QLabel(result_text)
        result_label.setStyleSheet(f"color: {result_color}; font-weight: bold; font-size: 14px;")
        header_layout.addWidget(result_label)
        
        layout.addLayout(header_layout)
        
        # Details: Date, Event
        details_text = f"{game.metadata.date} • {game.metadata.event}"
        details_label = QLabel(details_text)
        details_label.setStyleSheet(f"color: {Styles.COLOR_TEXT_SECONDARY}; font-size: 13px;")
        layout.addWidget(details_label)
        
        # Enforce minimum height
        self.setMinimumHeight(80)

    def sizeHint(self):
        return self.minimumSizeHint()

class GameListWidget(QWidget):
    game_selected = pyqtSignal(object) # Emits GameAnalysis object

    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        
        title_label = QLabel("Games")
        title_label.setStyleSheet(f"padding: 15px; font-weight: bold; color: {Styles.COLOR_TEXT_PRIMARY}; background-color: {Styles.COLOR_SURFACE}; border-bottom: 1px solid {Styles.COLOR_BORDER}; font-size: 16px;")
        self.layout.addWidget(title_label)
        
        self.list_widget = QListWidget()
        self.list_widget.setFrameShape(QFrame.Shape.NoFrame)
        self.list_widget.setStyleSheet(f"""
            QListWidget {{
                background-color: {Styles.COLOR_BACKGROUND};
                border: none;
            }}
            QListWidget::item {{
                border-bottom: 1px solid {Styles.COLOR_BORDER};
            }}
            QListWidget::item:selected {{
                background-color: {Styles.COLOR_SURFACE_LIGHT};
            }}
        """)
        self.list_widget.itemClicked.connect(self.on_item_clicked)
        self.layout.addWidget(self.list_widget)
        self.games = []
        self.usernames = []

    def set_games(self, games, usernames=None):
        self.games = games
        if usernames:
            self.usernames = usernames
            
        self.list_widget.clear()
        for game in games:
            item = QListWidgetItem(self.list_widget)
            widget = GameListItemWidget(game, self.usernames)
            item.setSizeHint(widget.sizeHint())
            self.list_widget.addItem(item)
            self.list_widget.setItemWidget(item, widget)

    def on_item_clicked(self, item):
        index = self.list_widget.row(item)
        if 0 <= index < len(self.games):
            logger.debug(f"Game selected from list at index: {index}")
            self.game_selected.emit(self.games[index])
