"""
Game List Widget - Clean, modern game card display.
"""
import os
import re
from PyQt6.QtWidgets import (QListWidget, QListWidgetItem, QVBoxLayout, QWidget, QLabel,
                             QHBoxLayout, QFrame, QPushButton)
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QPixmap, QIcon
from .styles import Styles
from ..utils.logger import logger
from ..utils.path_utils import get_resource_path

try:
    import qtawesome as qta
    HAS_QTAWESOME = True
except ImportError:
    HAS_QTAWESOME = False
    logger.warning("qtawesome not installed. Using text fallbacks for icons.")


class GameListItemWidget(QWidget):
    """A clean, modern game card for the history list."""

    from PyQt6.QtCore import pyqtSignal as _pyqtSignal
    delete_requested = _pyqtSignal(str)   # emits game_id

    def __init__(self, game, usernames=None):
        super().__init__()
        self._game = game   # kept for context menu access
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
        
        # Player names & ELO
        w_elo = f" ({game.metadata.white_elo})" if game.metadata.white_elo else ""
        b_elo = f" ({game.metadata.black_elo})" if game.metadata.black_elo else ""
        result_text = game.metadata.result
        
        # White player
        white_label = QLabel(f"<b>{game.metadata.white}{w_elo}</b>")
        white_label.setStyleSheet(f"color: {Styles.COLOR_TEXT_PRIMARY}; font-size: 14px;")
        header_layout.addWidget(white_label)
        
        if result_text == "1-0":
            crown_label = self._create_winner_crown()
            if crown_label:
                header_layout.addWidget(crown_label)
                
        # "vs" separator
        vs_label = QLabel("vs")
        vs_label.setStyleSheet(f"color: {Styles.COLOR_TEXT_MUTED}; font-size: 12px; margin: 0 4px;")
        header_layout.addWidget(vs_label)
        
        # Black player
        black_label = QLabel(f"<b>{game.metadata.black}{b_elo}</b>")
        black_label.setStyleSheet(f"color: {Styles.COLOR_TEXT_PRIMARY}; font-size: 14px;")
        header_layout.addWidget(black_label)
        
        if result_text == "0-1":
            crown_label = self._create_winner_crown()
            if crown_label:
                header_layout.addWidget(crown_label)
        
        header_layout.addStretch()
        
        # Result with color coding
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
            
            # Book icon - use custom book SVG or fallback to qtawesome
            book_icon = QLabel()
            icon_path = get_resource_path("assets/images/book.svg")
            if os.path.exists(icon_path):
                book_icon.setPixmap(QIcon(icon_path).pixmap(16, 16))
            elif HAS_QTAWESOME:
                book_icon.setPixmap(qta.icon('fa5s.book-open', color=Styles.COLOR_TEXT_MUTED).pixmap(16, 16))
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
        tc_icon = self._get_time_control_icon(time_control)
        tc_text = self._format_time_control(time_control)
        tc_widget = self._create_meta_item(tc_icon, tc_text)
        meta_layout.addWidget(tc_widget)

        # Chess960 variant badge (separate from time control)
        if self._is_chess960(game):
            c960_widget = self._create_meta_item(
                "assets/images/chess960.svg", "Chess960"
            )
            meta_layout.addWidget(c960_widget)
        
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
            white_acc = None
            black_acc = None
            if isinstance(game.summary, dict):
                # Try nested dictionary format first (default format from analyzer.py)
                if 'white' in game.summary and isinstance(game.summary['white'], dict):
                    white_acc = game.summary['white'].get('accuracy')
                else:
                    white_acc = game.summary.get('white_accuracy')
                    
                if 'black' in game.summary and isinstance(game.summary['black'], dict):
                    black_acc = game.summary['black'].get('accuracy')
                else:
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
    
    def _create_winner_crown(self):
        """Create a winner crown icon label."""
        icon_path = get_resource_path("assets/images/winner-crown.svg")
        if os.path.exists(icon_path):
            crown_label = QLabel()
            crown_label.setPixmap(QIcon(icon_path).pixmap(14, 14))
            crown_label.setToolTip("Winner")
            return crown_label
        return None

    def _create_meta_item(self, icon, text, color=None):
        """Create a metadata item with icon and text."""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        
        text_color = color or Styles.COLOR_TEXT_SECONDARY
        
        icon_label = QLabel()
        icon_pixmap = None
        
        if isinstance(icon, QIcon):
            if not icon.isNull():
                icon_pixmap = icon.pixmap(16, 16)
        elif isinstance(icon, str):
            if icon.endswith('.svg') or icon.endswith('.png'):
                # Try to load local SVG/image
                icon_path = get_resource_path(icon)
                if os.path.exists(icon_path):
                    icon_pixmap = QIcon(icon_path).pixmap(16, 16)
            elif HAS_QTAWESOME and icon.startswith('fa5s.'):
                icon_pixmap = qta.icon(icon, color=text_color).pixmap(16, 16)
                
        if icon_pixmap and not icon_pixmap.isNull():
            icon_label.setPixmap(icon_pixmap)
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
    
    def _format_time_control(self, time_control):
        """Format time control string from seconds to minutes (e.g. 180+2 -> 3+2, 600 -> 10)."""
        if not time_control or time_control in ("-", "?"):
            return time_control
            
        match = re.match(r"^(\d+)(?:\+(\d+))?$", time_control.strip())
        if match:
            try:
                base_seconds = int(match.group(1))
                increment = int(match.group(2)) if match.group(2) else 0
                
                # Format base time
                if base_seconds < 60:
                    base_str = f"{base_seconds}s"
                elif base_seconds % 60 == 0:
                    base_str = str(base_seconds // 60)
                else:
                    base_str = f"{base_seconds / 60:.1f}".rstrip('0').rstrip('.')
                
                # Format increment
                if increment > 0:
                    return f"{base_str}+{increment}"
                else:
                    return base_str
            except ValueError:
                pass
                
        return time_control

    def _get_time_control_icon(self, time_control):
        """Map time control string to a local SVG icon path."""
        tc_type = self._classify_time_control(time_control)
        return f"assets/images/{tc_type}.svg"

    def _classify_time_control(self, time_control):
        """Classify time control into bullet, blitz, rapid, or classical.

        Thresholds match Chess.com / Lichess conventions:
          Bullet   < 3 min  total (base + 40 × increment)
          Blitz    < 10 min total
          Rapid    < 30 min total
          Classical ≥ 30 min total, or no / unknown time control

        Example: 2+1 → 120 + 40 = 160 s → bullet  ✓
                 3+0 → 180 s → blitz  ✓
        """
        if not time_control or time_control in ("-", "?", "*", ""):
            return "classical"

        # Standard numeric format: "<base_sec>" or "<base_sec>+<inc_sec>"
        match = re.match(r"^(\d+)(?:\+(\d+))?$", time_control.strip())
        if match:
            try:
                base_seconds = int(match.group(1))
                increment = int(match.group(2)) if match.group(2) else 0

                # Estimate total time over a 40-move game
                total_time = base_seconds + 40 * increment

                if total_time < 180:    # < 3 min  → bullet
                    return "bullet"
                elif total_time < 600:  # < 10 min → blitz
                    return "blitz"
                elif total_time < 1800: # < 30 min → rapid
                    return "rapid"
                else:
                    return "classical"
            except ValueError:
                pass

        # Keyword fallback (e.g. Lichess exports "bullet", "blitz", etc.)
        tc_lower = time_control.lower()
        if "bullet" in tc_lower:
            return "bullet"
        elif "blitz" in tc_lower:
            return "blitz"
        elif "rapid" in tc_lower:
            return "rapid"
        elif any(k in tc_lower for k in ("classical", "daily", "correspondence", "unlimited", "infinite")):
            return "classical"

        # Unknown format — treat as classical (no time pressure assumed)
        return "classical"

    # Standard starting FEN (Chess960 games differ from this)
    _STANDARD_START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"

    def _is_chess960(self, game) -> bool:
        """Return True if this game is Chess960 / Fischer Random Chess.

        Detection order:
          1. PGN Variant tag contains '960' or 'fischer' or 'random'
          2. Event / Site tag contains 'Chess960' or 'FRC'
          3. A starting FEN is present AND it differs from the standard
             starting position (SetUp + FEN header in PGN).
        """
        headers = getattr(game.metadata, 'headers', {}) or {}

        # 1. Explicit Variant header
        variant = headers.get("Variant", "").lower()
        if any(k in variant for k in ("960", "fischer", "random", "frc")):
            return True

        # 2. Event / Site hint
        for key in ("Event", "Site"):
            val = headers.get(key, "").lower()
            if "960" in val or "frc" in val or "fischer" in val:
                return True

        # 3. Non-standard starting position
        fen = game.metadata.starting_fen
        if fen and fen.split()[0:4] != self._STANDARD_START_FEN.split()[0:4]:
            return True

        return False

    def _get_termination_icon(self, termination):
        """Return icon name based on termination type."""
        term_lower = termination.lower()
        if "checkmate" in term_lower or "mate" in term_lower:
            return "assets/images/checkmate.svg"
        elif "resign" in term_lower:
            return "assets/images/resign.svg"
        elif "time" in term_lower or "timeout" in term_lower or "forfeit" in term_lower:
            return "assets/images/timeout.svg"
        elif "abandon" in term_lower:
            return "fa5s.door-open"
        elif "draw" in term_lower or "stalemate" in term_lower or "repetition" in term_lower:
            return "assets/images/draw_black.svg"
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

    def contextMenuEvent(self, event):
        """Right-click context menu with a Delete option."""
        from PyQt6.QtWidgets import QMenu
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background-color: {Styles.COLOR_SURFACE};
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 6px;
                padding: 4px;
            }}
            QMenu::item {{
                color: {Styles.COLOR_TEXT_PRIMARY};
                padding: 8px 20px;
                border-radius: 4px;
                font-size: 13px;
            }}
            QMenu::item:selected {{
                background-color: {Styles.COLOR_BLUNDER};
                color: white;
            }}
        """)
        act_delete = menu.addAction("🗑  Delete from history")
        chosen = menu.exec(event.globalPos())
        if chosen is act_delete:
            game_id = getattr(self._game, 'game_id', None)
            if game_id:
                self.delete_requested.emit(game_id)

class GameListWidget(QWidget):
    """Container widget for the game list with pagination (10 games per page)."""

    game_selected = pyqtSignal(object)
    _PAGE_SIZE = 10

    def __init__(self):
        super().__init__()
        self._all_games: list = []
        self._current_page: int = 0
        self.usernames: list = []

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Header ──────────────────────────────────────────────────────────
        self.title_label = QLabel("Games")
        self._apply_title_style()
        root.addWidget(self.title_label)

        # ── List ─────────────────────────────────────────────────────────────
        self.list_widget = QListWidget()
        self.list_widget.setFrameShape(QFrame.Shape.NoFrame)
        self.list_widget.setSpacing(0)
        self._apply_list_style()
        self.list_widget.itemClicked.connect(self._on_item_clicked)
        root.addWidget(self.list_widget, stretch=1)

        # ── Pagination bar ───────────────────────────────────────────────────
        self._pagination_bar = QWidget()
        self._pagination_bar.setFixedHeight(52)
        self._pagination_bar.setStyleSheet(
            f"background-color: {Styles.COLOR_SURFACE}; border-top: 1px solid {Styles.COLOR_BORDER};"
        )
        self._page_bar_layout = QHBoxLayout(self._pagination_bar)
        self._page_bar_layout.setContentsMargins(16, 0, 16, 0)
        self._page_bar_layout.setSpacing(6)
        root.addWidget(self._pagination_bar)

        # Alias kept for history_view.py refresh_styles() call
        self.layout = root

        self._render_page()

    # ── Public API ────────────────────────────────────────────────────────────

    def set_games(self, games, usernames=None):
        """Replace the game list and jump back to page 1."""
        self._all_games = list(games)
        if usernames is not None:
            self.usernames = usernames
        self._current_page = 0
        self._render_page()

    @property
    def games(self):
        """Compatibility shim — callers that read .games get the full list."""
        return self._all_games

    @games.setter
    def games(self, value):
        self._all_games = list(value)

    # ── Rendering ─────────────────────────────────────────────────────────────

    def _total_pages(self) -> int:
        if not self._all_games:
            return 1
        import math
        return math.ceil(len(self._all_games) / self._PAGE_SIZE)

    def _render_page(self):
        """Populate the list widget with the current page's games."""
        self.list_widget.clear()

        start = self._current_page * self._PAGE_SIZE
        end = start + self._PAGE_SIZE
        page_games = self._all_games[start:end]

        for game in page_games:
            item = QListWidgetItem(self.list_widget)
            widget = GameListItemWidget(game, self.usernames)
            widget.delete_requested.connect(self._on_delete_requested)
            item.setSizeHint(widget.sizeHint())
            self.list_widget.addItem(item)
            self.list_widget.setItemWidget(item, widget)

        self._rebuild_pagination()

    def _rebuild_pagination(self):
        """Rebuild the pagination button bar to reflect the current state."""
        # Clear existing widgets
        while self._page_bar_layout.count():
            child = self._page_bar_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        total = self._total_pages()
        current = self._current_page

        # ── Page counter label (left) ────────────────────────────────────────
        start = current * self._PAGE_SIZE + 1
        end = min(start + self._PAGE_SIZE - 1, len(self._all_games))
        total_games = len(self._all_games)

        if total_games == 0:
            counter_text = "No games"
        else:
            counter_text = f"{start}–{end} of {total_games}"

        counter = QLabel(counter_text)
        counter.setStyleSheet(
            f"color: {Styles.COLOR_TEXT_SECONDARY}; font-size: 12px;"
            " background: transparent; border: none;"
        )
        self._page_bar_layout.addWidget(counter)
        self._page_bar_layout.addStretch()

        # ── Prev button ──────────────────────────────────────────────────────
        btn_prev = self._make_page_btn("‹ Prev", enabled=(current > 0))
        btn_prev.clicked.connect(self._go_prev)
        self._page_bar_layout.addWidget(btn_prev)

        # ── Page number buttons (show up to 5 around current) ────────────────
        window = 2
        lo = max(0, current - window)
        hi = min(total - 1, current + window)

        if lo > 0:
            self._page_bar_layout.addWidget(self._make_page_num_btn(0))
            if lo > 1:
                self._page_bar_layout.addWidget(self._make_ellipsis())

        for p in range(lo, hi + 1):
            self._page_bar_layout.addWidget(self._make_page_num_btn(p))

        if hi < total - 1:
            if hi < total - 2:
                self._page_bar_layout.addWidget(self._make_ellipsis())
            self._page_bar_layout.addWidget(self._make_page_num_btn(total - 1))

        # ── Next button ──────────────────────────────────────────────────────
        btn_next = self._make_page_btn("Next ›", enabled=(current < total - 1))
        btn_next.clicked.connect(self._go_next)
        self._page_bar_layout.addWidget(btn_next)

    # ── Navigation ────────────────────────────────────────────────────────────

    def _on_delete_requested(self, game_id: str):
        """Delete a single game from history after confirmation."""
        from PyQt6.QtWidgets import QMessageBox
        from ..backend.game_history import GameHistoryManager

        reply = QMessageBox.question(
            self,
            "Delete Game",
            "Remove this game from history? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            GameHistoryManager().delete_game(game_id)
        except Exception as e:
            from ..utils.logger import logger
            logger.error(f"Failed to delete game {game_id}: {e}")
            return

        # Remove from the local list and re-render without reloading from DB
        self._all_games = [g for g in self._all_games if g.game_id != game_id]

        # Stay on the current page unless it no longer exists
        max_page = max(0, self._total_pages() - 1)
        if self._current_page > max_page:
            self._current_page = max_page

        self._render_page()

    def _go_prev(self):
        if self._current_page > 0:
            self._current_page -= 1
            self._render_page()

    def _go_next(self):
        if self._current_page < self._total_pages() - 1:
            self._current_page += 1
            self._render_page()

    def _go_to_page(self, page: int):
        if 0 <= page < self._total_pages():
            self._current_page = page
            self._render_page()

    # ── Button factories ──────────────────────────────────────────────────────

    def _make_page_btn(self, text: str, enabled: bool) -> QPushButton:
        btn = QPushButton(text)
        btn.setFixedHeight(30)
        btn.setEnabled(enabled)
        btn.setCursor(Qt.CursorShape.PointingHandCursor if enabled else Qt.CursorShape.ArrowCursor)
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Styles.COLOR_SURFACE_LIGHT if enabled else 'transparent'};
                color: {Styles.COLOR_TEXT_PRIMARY if enabled else Styles.COLOR_TEXT_MUTED};
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 6px;
                padding: 0 12px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {Styles.COLOR_ACCENT};
                color: {Styles.COLOR_TEXT_PRIMARY};
                border-color: {Styles.COLOR_ACCENT};
            }}
            QPushButton:disabled {{
                opacity: 0.4;
            }}
        """)
        return btn

    def _make_page_num_btn(self, page: int) -> QPushButton:
        is_current = (page == self._current_page)
        btn = QPushButton(str(page + 1))
        btn.setFixedSize(30, 30)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Styles.COLOR_ACCENT if is_current else Styles.COLOR_SURFACE_LIGHT};
                color: {Styles.COLOR_TEXT_PRIMARY};
                border: 1px solid {Styles.COLOR_ACCENT if is_current else Styles.COLOR_BORDER};
                border-radius: 6px;
                font-size: 12px;
                font-weight: {'700' if is_current else '400'};
            }}
            QPushButton:hover {{
                background-color: {Styles.COLOR_ACCENT};
                border-color: {Styles.COLOR_ACCENT};
            }}
        """)
        btn.clicked.connect(lambda _, p=page: self._go_to_page(p))
        return btn

    def _make_ellipsis(self) -> QLabel:
        lbl = QLabel("…")
        lbl.setFixedSize(20, 30)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet(
            f"color: {Styles.COLOR_TEXT_MUTED}; font-size: 13px;"
            " background: transparent; border: none;"
        )
        return lbl

    # ── Style refresh ─────────────────────────────────────────────────────────

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
        self._pagination_bar.setStyleSheet(
            f"background-color: {Styles.COLOR_SURFACE}; border-top: 1px solid {Styles.COLOR_BORDER};"
        )
        self._rebuild_pagination()

    # ── Click handling ────────────────────────────────────────────────────────

    def _on_item_clicked(self, item):
        index = self.list_widget.row(item)
        absolute_index = self._current_page * self._PAGE_SIZE + index
        if 0 <= absolute_index < len(self._all_games):
            self.game_selected.emit(self._all_games[absolute_index])
