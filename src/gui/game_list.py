import os
import sys
from PyQt6.QtWidgets import (QListWidget, QListWidgetItem, QVBoxLayout, QWidget, QLabel, 
                             QHBoxLayout, QFrame)
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QColor, QPixmap
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

        # Source Icon
        source = getattr(game.metadata, "source", "file")
        
        # Robust path finding
        # 1. Try relative to this file (development)
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        assets_dir = os.path.join(base_dir, "assets")
        
        # 2. Try relative to CWD (fallback)
        if not os.path.exists(assets_dir):
             assets_dir = os.path.join(os.getcwd(), "assets")
             
        # Check assets/icons first, then assets/
        icons_dir = os.path.join(assets_dir, "icons")
        if os.path.exists(icons_dir):
            icon_path = os.path.join(icons_dir, f"{source}.png")
        else:
            icon_path = os.path.join(assets_dir, f"{source}.png")
        
        # Fallback to file.png if specific source icon missing
        if not os.path.exists(icon_path):
            # Try finding file.png in icons dir too
            if os.path.exists(icons_dir):
                fallback_path = os.path.join(icons_dir, "file.png")
                if os.path.exists(fallback_path):
                    icon_path = fallback_path
                else:
                    icon_path = os.path.join(assets_dir, "file.png")
            else:
                icon_path = os.path.join(assets_dir, "file.png")
            
            logger.debug(f"Icon not found for {source}, falling back to {icon_path}")
            
        icon_label = QLabel()
        icon_pixmap = None
        
        if os.path.exists(icon_path):
             icon_pixmap = QPixmap(icon_path)
        else:
            logger.warning(f"No icon found for source {source}. Searched at {assets_dir}")
        
        if icon_pixmap:
            icon_label.setPixmap(icon_pixmap.scaled(20, 20, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            header_layout.addWidget(icon_label)
        else:
            # Text fallback if icon missing
            fallback_label = QLabel(f"[{source}]")
            fallback_label.setStyleSheet(f"color: {Styles.COLOR_TEXT_SECONDARY}; font-size: 11px; font-weight: bold;")
            header_layout.addWidget(fallback_label)
        
        w_elo = f" ({game.metadata.white_elo})" if game.metadata.white_elo else ""
        b_elo = f" ({game.metadata.black_elo})" if game.metadata.black_elo else ""
        
        players_label = QLabel(f"<b>{game.metadata.white}{w_elo}</b> vs <b>{game.metadata.black}{b_elo}</b>")
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
        
        # Details: Date, Event, Move Count
        move_count = ""
        if hasattr(game, 'moves') and game.moves:
            # game.moves contains all half-moves (ply)
            # Convert to full moves: (num_half_moves + 1) // 2
            num_ply = len(game.moves)
            full_moves = (num_ply + 1) // 2
            move_count = f" • {full_moves} moves"
        elif hasattr(game, 'pgn_content') and game.pgn_content:
            # Estimate from PGN - find the highest move number
            # Only look for moves after the PGN headers end (after ]]
            import re
            pgn_text = game.pgn_content
            # Try to find where headers end
            header_end = pgn_text.rfind(']')
            if header_end > 0:
                pgn_text = pgn_text[header_end:]
            # Match move numbers (1-3 digits only to exclude years)
            matches = re.findall(r'(?:^|\s)(\d{1,3})\.', pgn_text)
            if matches:
                # Filter to reasonable move numbers (under 500)
                valid_moves = [int(m) for m in matches if int(m) < 500]
                if valid_moves:
                    highest_move = max(valid_moves)
                    move_count = f" • ~{highest_move} moves"
        
        details_text = f"{game.metadata.date} • {game.metadata.event}{move_count}"
        details_label = QLabel(details_text)
        details_label.setStyleSheet(f"""
            color: {Styles.COLOR_TEXT_SECONDARY}; 
            font-size: 13px;
            font-family: 'Segoe UI', 'Inter', sans-serif;
        """)
        layout.addWidget(details_label)
        
        # Card styling
        self.setStyleSheet(f"""
            QWidget {{
                background-color: transparent;
            }}
            QLabel {{
                background-color: transparent;
            }}
        """)
        
        # Enforce minimum height
        self.setMinimumHeight(85)

    def sizeHint(self):
        return self.minimumSizeHint()

class GameListWidget(QWidget):
    game_selected = pyqtSignal(object)  # Emits GameAnalysis object

    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        
        self.title_label = QLabel("Games")
        self._apply_title_style()
        self.layout.addWidget(self.title_label)
        
        self.list_widget = QListWidget()
        self.list_widget.setFrameShape(QFrame.Shape.NoFrame)
        self.list_widget.setSpacing(0)
        self._apply_list_style()
        self.list_widget.itemClicked.connect(self.on_item_clicked)
        self.layout.addWidget(self.list_widget)
        self.games = []
        self.usernames = []
    
    def _apply_title_style(self):
        self.title_label.setStyleSheet(f"""
            padding: 16px 20px;
            font-weight: 600;
            font-size: 16px;
            color: {Styles.COLOR_TEXT_PRIMARY};
            background-color: {Styles.COLOR_SURFACE};
            border-bottom: 2px solid {Styles.COLOR_ACCENT};
        """)
    
    def _apply_list_style(self):
        self.list_widget.setStyleSheet(f"""
            QListWidget {{
                background-color: {Styles.COLOR_BACKGROUND};
                border: none;
                outline: none;
            }}
            QListWidget::item {{
                background-color: {Styles.COLOR_BACKGROUND};
                border: none;
                border-bottom: 1px solid {Styles.COLOR_SURFACE_LIGHT};
                padding: 0px;
                margin: 0px;
            }}
            QListWidget::item:hover {{
                background-color: {Styles.COLOR_SURFACE};
            }}
            QListWidget::item:selected {{
                background-color: {Styles.COLOR_SURFACE};
                border-left: 3px solid {Styles.COLOR_ACCENT};
            }}
        """)
    
    def refresh_styles(self):
        """Refresh styles for dynamic theme updates."""
        self._apply_title_style()
        self._apply_list_style()

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
