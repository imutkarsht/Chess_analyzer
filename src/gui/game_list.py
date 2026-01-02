"""
Game List Widget - Clean, modern game card display.
"""
import os
import re
from PyQt6.QtWidgets import (QListWidget, QListWidgetItem, QVBoxLayout, QWidget, QLabel, 
                             QHBoxLayout, QFrame)
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QPixmap
from .styles import Styles
from ..utils.logger import logger

try:
    import qtawesome as qta
    HAS_QTAWESOME = True
except ImportError:
    HAS_QTAWESOME = False
    logger.warning("qtawesome not installed. Using text fallbacks for icons.")


class GameListItemWidget(QWidget):
    """A clean, modern game card for the history list."""
    
    def __init__(self, game, usernames=None):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(6)
        
        # ===== ROW 1: Players and Result =====
        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)

        # Source Icon (from assets)
        source = getattr(game.metadata, "source", "file")
        icon_label = self._create_source_icon(source)
        if icon_label:
            header_layout.addWidget(icon_label)
        
        # Player names
        w_elo = f" ({game.metadata.white_elo})" if game.metadata.white_elo else ""
        b_elo = f" ({game.metadata.black_elo})" if game.metadata.black_elo else ""
        
        players_label = QLabel(f"<b>{game.metadata.white}{w_elo}</b>  vs  <b>{game.metadata.black}{b_elo}</b>")
        players_label.setStyleSheet(f"color: {Styles.COLOR_TEXT_PRIMARY}; font-size: 14px;")
        header_layout.addWidget(players_label)
        
        header_layout.addStretch()
        
        # Result with color coding
        result_text = game.metadata.result
        result_color = self._get_result_color(result_text, game.metadata, usernames)
            
        result_label = QLabel(result_text)
        result_label.setStyleSheet(f"""
            color: {result_color}; 
            font-weight: bold; 
            font-size: 14px;
            padding: 2px 8px;
            background-color: {Styles.COLOR_SURFACE_LIGHT};
            border-radius: 4px;
        """)
        header_layout.addWidget(result_label)
        
        layout.addLayout(header_layout)
        
        # ===== ROW 2: Opening (if available) =====
        opening = game.metadata.opening or ""
        eco = game.metadata.eco or ""
        
        if opening or eco:
            opening_layout = QHBoxLayout()
            opening_layout.setSpacing(6)
            opening_layout.setContentsMargins(0, 0, 0, 0)
            
            # Book icon - use muted color
            if HAS_QTAWESOME:
                book_icon = QLabel()
                book_icon.setPixmap(qta.icon('fa5s.book-open', color=Styles.COLOR_TEXT_MUTED).pixmap(12, 12))
                book_icon.setFixedWidth(16)
                opening_layout.addWidget(book_icon)
            
            opening_text = f"{eco}: {opening}" if eco and opening else (opening or eco)
            opening_label = QLabel(opening_text)
            opening_label.setStyleSheet(f"""
                color: {Styles.COLOR_TEXT_MUTED}; 
                font-size: 12px;
                font-style: italic;
            """)
            opening_label.setToolTip(opening_text)
            opening_layout.addWidget(opening_label, 1)
            
            layout.addLayout(opening_layout)
        
        # ===== ROW 3: Metadata (Date, Time Control, Moves, Termination) =====
        meta_layout = QHBoxLayout()
        meta_layout.setSpacing(12)
        
        # Date
        if game.metadata.date:
            date_widget = self._create_meta_item('fa5s.calendar-alt', game.metadata.date)
            meta_layout.addWidget(date_widget)
        
        # Time Control
        time_control = game.metadata.time_control
        if time_control:
            tc_widget = self._create_meta_item('fa5s.clock', time_control)
            meta_layout.addWidget(tc_widget)
        
        # Move count
        move_count = self._get_move_count(game)
        if move_count:
            moves_widget = self._create_meta_item('fa5s.chess-pawn', f"{move_count} moves")
            meta_layout.addWidget(moves_widget)
        
        # Termination
        termination = game.metadata.termination
        if termination:
            term_icon = self._get_termination_icon(termination)
            term_widget = self._create_meta_item(term_icon, termination)
            meta_layout.addWidget(term_widget)
        
        meta_layout.addStretch()
        
        # Accuracy (if analyzed) - use subtle accent
        if hasattr(game, 'summary') and game.summary:
            white_acc = game.summary.get('white_accuracy')
            black_acc = game.summary.get('black_accuracy')
            
            if white_acc is not None and black_acc is not None:
                acc_text = f"{white_acc:.0f}% / {black_acc:.0f}%"
                acc_widget = self._create_meta_item('fa5s.bullseye', acc_text)
                meta_layout.addWidget(acc_widget)
        
        layout.addLayout(meta_layout)
        
        # ===== ROW 4: Event (if meaningful) =====
        skip_events = ["?", "Live Chess", "Rated Bullet game", "Rated Blitz game", 
                       "Rated Rapid game", "rated bullet game", "rated blitz game", 
                       "rated rapid game", "Casual Bullet game", "Casual Blitz game"]
        if game.metadata.event and game.metadata.event not in skip_events:
            event_layout = QHBoxLayout()
            event_layout.setSpacing(6)
            event_layout.setContentsMargins(0, 0, 0, 0)
            
            if HAS_QTAWESOME:
                trophy_icon = QLabel()
                trophy_icon.setPixmap(qta.icon('fa5s.trophy', color=Styles.COLOR_TEXT_MUTED).pixmap(11, 11))
                trophy_icon.setFixedWidth(14)
                event_layout.addWidget(trophy_icon)
            
            event_label = QLabel(game.metadata.event)
            event_label.setStyleSheet(f"color: {Styles.COLOR_TEXT_MUTED}; font-size: 11px;")
            event_layout.addWidget(event_label)
            event_layout.addStretch()
            
            layout.addLayout(event_layout)
        
        # Card styling
        self.setStyleSheet(f"""
            QWidget {{
                background-color: transparent;
            }}
            QLabel {{
                background-color: transparent;
            }}
        """)
        
        self.setMinimumHeight(90)
    
    def _create_source_icon(self, source):
        """Create source platform icon from assets."""
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        assets_dir = os.path.join(base_dir, "assets")
        
        if not os.path.exists(assets_dir):
            assets_dir = os.path.join(os.getcwd(), "assets")
             
        icons_dir = os.path.join(assets_dir, "icons")
        icon_path = os.path.join(icons_dir, f"{source}.png") if os.path.exists(icons_dir) else os.path.join(assets_dir, f"{source}.png")
        
        if not os.path.exists(icon_path):
            fallback_path = os.path.join(icons_dir, "file.png") if os.path.exists(icons_dir) else os.path.join(assets_dir, "file.png")
            if os.path.exists(fallback_path):
                icon_path = fallback_path
            else:
                return None
            
        icon_label = QLabel()
        if os.path.exists(icon_path):
            icon_pixmap = QPixmap(icon_path)
            icon_label.setPixmap(icon_pixmap.scaled(16, 16, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        return icon_label
    
    def _create_meta_item(self, icon_name, text, color=None):
        """Create a metadata item with icon and text."""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        
        text_color = color or Styles.COLOR_TEXT_SECONDARY
        
        if HAS_QTAWESOME:
            icon_label = QLabel()
            icon_label.setPixmap(qta.icon(icon_name, color=text_color).pixmap(12, 12))
            layout.addWidget(icon_label)
        
        text_label = QLabel(text)
        text_label.setStyleSheet(f"color: {text_color}; font-size: 11px;")
        layout.addWidget(text_label)
        
        return widget
    
    def _get_result_color(self, result_text, metadata, usernames):
        """Determine result color based on user perspective."""
        if not usernames:
            if result_text == "1-0":
                return Styles.COLOR_BEST 
            elif result_text == "0-1":
                return Styles.COLOR_BLUNDER 
            return Styles.COLOR_TEXT_SECONDARY
        
        white = (metadata.white or "").lower()
        black = (metadata.black or "").lower()
        known_users = [u.lower() for u in usernames]
        
        user_is_white = white in known_users
        user_is_black = black in known_users
        
        if result_text == "1-0":
            return Styles.COLOR_BEST if user_is_white else Styles.COLOR_BLUNDER
        elif result_text == "0-1":
            return Styles.COLOR_BEST if user_is_black else Styles.COLOR_BLUNDER
        elif result_text == "1/2-1/2":
            return Styles.COLOR_TEXT_SECONDARY
        
        return Styles.COLOR_TEXT_SECONDARY
    
    def _get_termination_icon(self, termination):
        """Return icon name based on termination type."""
        term_lower = termination.lower()
        if "checkmate" in term_lower or "mate" in term_lower:
            return "fa5s.chess-king"
        elif "resign" in term_lower:
            return "fa5s.flag"
        elif "time" in term_lower:
            return "fa5s.hourglass-end"
        elif "abandon" in term_lower:
            return "fa5s.door-open"
        elif "draw" in term_lower or "stalemate" in term_lower or "repetition" in term_lower:
            return "fa5s.handshake"
        return "fa5s.circle"
    
    def _get_move_count(self, game):
        """Extract move count from game."""
        if hasattr(game, 'moves') and game.moves:
            num_ply = len(game.moves)
            return (num_ply + 1) // 2
        elif hasattr(game, 'pgn_content') and game.pgn_content:
            pgn = game.pgn_content
            moves = re.findall(r'(?:^|\s)(\d{1,3})\.\s+[A-Za-z]', pgn, re.MULTILINE)
            if moves:
                move_nums = [int(m) for m in moves if int(m) <= 500]
                if move_nums:
                    return max(move_nums)
        return None

    def sizeHint(self):
        return self.minimumSizeHint()


class GameListWidget(QWidget):
    """Container widget for the game list."""
    game_selected = pyqtSignal(object)

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
            self.game_selected.emit(self.games[index])
