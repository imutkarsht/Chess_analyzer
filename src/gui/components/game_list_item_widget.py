"""
Game List Item Widget - Renders a clean, modern desktop card with mini board thumbnail,
player details, speed category badges, accuracy stats, and human-readable termination text.
Supports both "detailed" card view and "compact" list row view.
"""
import os
import re
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QPixmap, QIcon
from PyQt6.QtSvgWidgets import QSvgWidget
import chess
import chess.svg

from ..styles import Styles
from ...utils.logger import logger
from ...utils.path_utils import get_resource_path
from ...utils.config import ConfigManager
from ..theme.palette import BOARD_THEMES

try:
    import qtawesome as qta
    HAS_QTAWESOME = True
except ImportError:
    HAS_QTAWESOME = False
    logger.warning("qtawesome not installed. Using text fallbacks for icons.")


class GameListItemWidget(QWidget):
    """A modern, desktop-class game card supporting Detailed and Compact view modes."""

    delete_requested = pyqtSignal(str)   # emits game_id

    # Standard starting FEN
    _STANDARD_START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"

    def __init__(self, game, usernames=None, view_mode="detailed"):
        super().__init__()
        self._game = game
        self.view_mode = view_mode

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 2 if view_mode == "compact" else 4, 0, 2 if view_mode == "compact" else 4)
        root_layout.setSpacing(0)

        self.card_frame = QFrame()
        self.card_frame.setObjectName("GameCard")

        if view_mode == "compact":
            self._build_compact_ui(game, usernames, root_layout)
        else:
            self._build_detailed_ui(game, usernames, root_layout)

    def _build_compact_ui(self, game, usernames, root_layout):
        """Build compact single-row list item layout (Lichess/Chess.com table style)."""
        self.card_frame.setStyleSheet(f"""
            QFrame#GameCard {{
                background-color: {Styles.COLOR_SURFACE_CARD};
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 6px;
                padding: 10px 14px;
            }}
            QFrame#GameCard:hover {{
                border-color: {Styles.COLOR_ACCENT};
                background-color: {Styles.COLOR_SURFACE};
            }}
            QFrame#GameCard QLabel {{
                background: transparent;
                border: none;
            }}
        """)

        card_layout = QHBoxLayout(self.card_frame)
        card_layout.setContentsMargins(12, 8, 12, 8)
        card_layout.setSpacing(12)

        # 1. Source & Speed Icon
        source = getattr(game.metadata, "source", "file")
        source_icon = self._create_source_icon(source)
        if source_icon:
            card_layout.addWidget(source_icon)

        speed_cat = getattr(game.metadata, "speed_category", None) or self._classify_time_control(game.metadata.time_control)
        formatted_tc = self._format_time_control(game.metadata.time_control)
        tc_display = f"{speed_cat} {formatted_tc}".strip() if formatted_tc else speed_cat
        tc_icon = self._get_time_control_icon(game.metadata.time_control)
        tc_widget = self._create_meta_item(tc_icon, tc_display)
        tc_widget.setFixedWidth(130)
        card_layout.addWidget(tc_widget)

        # 2. Players & Result (Fixed width container for aligned opening column)
        w_elo = f" ({game.metadata.white_elo})" if game.metadata.white_elo else ""
        b_elo = f" ({game.metadata.black_elo})" if game.metadata.black_elo else ""
        result_text = game.metadata.result

        players_widget = QWidget()
        players_widget.setFixedWidth(220)
        players_widget.setStyleSheet("background: transparent; border: none;")
        players_layout = QVBoxLayout(players_widget)
        players_layout.setContentsMargins(0, 0, 0, 0)
        players_layout.setSpacing(2)

        # White player row
        w_row = QHBoxLayout()
        w_row.setContentsMargins(0, 0, 0, 0)
        w_row.setSpacing(4)
        w_lbl = QLabel(f"<b>{game.metadata.white}</b>{w_elo}")
        w_lbl.setStyleSheet(f"color: {Styles.COLOR_TEXT_PRIMARY}; font-size: 12px; background: transparent; border: none;")
        w_row.addWidget(w_lbl)
        if result_text == "1-0":
            crown = self._create_winner_crown()
            if crown:
                w_row.addWidget(crown)
        w_row.addStretch()

        # Black player row
        b_row = QHBoxLayout()
        b_row.setContentsMargins(0, 0, 0, 0)
        b_row.setSpacing(4)
        b_lbl = QLabel(f"<b>{game.metadata.black}</b>{b_elo}")
        b_lbl.setStyleSheet(f"color: {Styles.COLOR_TEXT_PRIMARY}; font-size: 12px; background: transparent; border: none;")
        b_row.addWidget(b_lbl)
        if result_text == "0-1":
            crown = self._create_winner_crown()
            if crown:
                b_row.addWidget(crown)
        b_row.addStretch()

        players_layout.addLayout(w_row)
        players_layout.addLayout(b_row)
        card_layout.addWidget(players_widget)

        # 3. Opening Name (aligned)
        opening = game.metadata.opening or ""
        eco = game.metadata.eco or ""
        opening_text = f"{eco}: {opening}" if eco and opening else (opening or eco)
        op_lbl = QLabel(opening_text if opening_text else "-")
        op_lbl.setStyleSheet(f"color: {Styles.COLOR_TEXT_SECONDARY}; font-size: 11px; background: transparent; border: none;")
        op_lbl.setToolTip(opening_text)
        card_layout.addWidget(op_lbl, stretch=1)

        # 4. Result Badge
        result_color = self._get_result_color(result_text, game.metadata, usernames)
        result_label = QLabel(result_text)
        result_label.setStyleSheet(f"""
            color: {result_color}; 
            font-weight: bold; 
            font-size: 12px;
            padding: 2px 8px;
            background-color: {Styles.COLOR_SURFACE_LIGHT};
            border: 1px solid {Styles.COLOR_BORDER};
            border-radius: 4px;
        """)
        card_layout.addWidget(result_label)

        # 5. Accuracy (if analyzed)
        if hasattr(game, 'summary') and game.summary:
            white_acc = game.summary.get('white', {}).get('accuracy') if isinstance(game.summary.get('white'), dict) else game.summary.get('white_accuracy')
            black_acc = game.summary.get('black', {}).get('accuracy') if isinstance(game.summary.get('black'), dict) else game.summary.get('black_accuracy')
            if white_acc is not None and black_acc is not None:
                acc_widget = self._create_meta_item('fa5s.bullseye', f"{white_acc:.0f}% / {black_acc:.0f}%")
                card_layout.addWidget(acc_widget)

        # 6. Date & Move Count
        if game.metadata.date:
            date_lbl = QLabel(game.metadata.date)
            date_lbl.setStyleSheet(f"color: {Styles.COLOR_TEXT_MUTED}; font-size: 11px; background: transparent; border: none;")
            card_layout.addWidget(date_lbl)

        move_count = self._get_move_count(game)
        if move_count:
            moves_lbl = QLabel(f"{move_count}m")
            moves_lbl.setStyleSheet(f"color: {Styles.COLOR_TEXT_MUTED}; font-size: 11px; background: transparent; border: none;")
            card_layout.addWidget(moves_lbl)

        # 7. Delete button
        del_btn = QPushButton()
        del_btn.setFixedSize(22, 22)
        del_btn.setToolTip("Delete game")
        if HAS_QTAWESOME:
            del_btn.setIcon(qta.icon("fa5s.trash-alt", color=Styles.COLOR_TEXT_MUTED))
        else:
            del_btn.setText("🗑")
        del_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: none;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: {Styles.COLOR_SURFACE_LIGHT};
                border: 1px solid {Styles.COLOR_BLUNDER};
            }}
        """)
        game_id = getattr(game, 'game_id', None)
        del_btn.clicked.connect(lambda: game_id and self.delete_requested.emit(game_id))
        card_layout.addWidget(del_btn)

        root_layout.addWidget(self.card_frame)

    def _build_detailed_ui(self, game, usernames, root_layout):
        """Build detailed card layout with mini board thumbnail."""
        self.card_frame.setStyleSheet(f"""
            QFrame#GameCard {{
                background-color: {Styles.COLOR_SURFACE_CARD};
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 10px;
                padding: 8px 14px;
            }}
            QFrame#GameCard:hover {{
                border-color: {Styles.COLOR_ACCENT};
            }}
            QFrame#GameCard QLabel {{
                background: transparent;
                border: none;
            }}
        """)

        card_layout = QHBoxLayout(self.card_frame)
        card_layout.setContentsMargins(12, 10, 12, 10)
        card_layout.setSpacing(14)

        # ===== LEFT: Mini Chessboard Thumbnail =====
        mini_board = self._create_mini_board_widget(game)
        card_layout.addWidget(mini_board, 0, Qt.AlignmentFlag.AlignVCenter)

        # ===== RIGHT: Main Card Content (3 rows) =====
        content_layout = QVBoxLayout()
        content_layout.setSpacing(6)

        # --- ROW 1: Players, Source, Winner Crown, Result Badge ---
        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)

        source = getattr(game.metadata, "source", "file")
        icon_label = self._create_source_icon(source)
        if icon_label:
            header_layout.addWidget(icon_label)

        w_elo = f" ({game.metadata.white_elo})" if game.metadata.white_elo else ""
        b_elo = f" ({game.metadata.black_elo})" if game.metadata.black_elo else ""
        result_text = game.metadata.result

        # White player
        white_label = QLabel(f"<b>{game.metadata.white}</b>{w_elo}")
        white_label.setStyleSheet(f"color: {Styles.COLOR_TEXT_PRIMARY}; font-size: 14px; background: transparent; border: none;")
        header_layout.addWidget(white_label)

        if result_text == "1-0":
            crown_label = self._create_winner_crown()
            if crown_label:
                header_layout.addWidget(crown_label)

        vs_label = QLabel("vs")
        vs_label.setStyleSheet(f"color: {Styles.COLOR_TEXT_MUTED}; font-size: 12px; margin: 0 4px; background: transparent; border: none;")
        header_layout.addWidget(vs_label)

        # Black player
        black_label = QLabel(f"<b>{game.metadata.black}</b>{b_elo}")
        black_label.setStyleSheet(f"color: {Styles.COLOR_TEXT_PRIMARY}; font-size: 14px; background: transparent; border: none;")
        header_layout.addWidget(black_label)

        if result_text == "0-1":
            crown_label = self._create_winner_crown()
            if crown_label:
                header_layout.addWidget(crown_label)

        header_layout.addStretch()

        # Result badge
        result_color = self._get_result_color(result_text, game.metadata, usernames)
        result_label = QLabel(result_text)
        result_label.setStyleSheet(f"""
            color: {result_color}; 
            font-weight: bold; 
            font-size: 13px;
            padding: 3px 10px;
            background-color: {Styles.COLOR_SURFACE_LIGHT};
            border: 1px solid {Styles.COLOR_BORDER};
            border-radius: 6px;
        """)
        header_layout.addWidget(result_label)

        # Delete button on card
        del_btn = QPushButton()
        del_btn.setFixedSize(26, 26)
        del_btn.setToolTip("Delete game")
        if HAS_QTAWESOME:
            del_btn.setIcon(qta.icon("fa5s.trash-alt", color=Styles.COLOR_TEXT_MUTED))
        else:
            del_btn.setText("🗑")
        del_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: none;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: {Styles.COLOR_SURFACE_LIGHT};
                border: 1px solid {Styles.COLOR_BLUNDER};
            }}
        """)
        game_id = getattr(game, 'game_id', None)
        del_btn.clicked.connect(lambda: game_id and self.delete_requested.emit(game_id))
        header_layout.addWidget(del_btn)

        content_layout.addLayout(header_layout)

        # --- ROW 2: Opening Name & ECO Code ---
        opening = game.metadata.opening or ""
        eco = game.metadata.eco or ""
        if opening or eco:
            opening_layout = QHBoxLayout()
            opening_layout.setSpacing(6)

            book_icon = QLabel()
            icon_path = get_resource_path("assets/images/book.svg")
            if os.path.exists(icon_path):
                book_icon.setPixmap(QIcon(icon_path).pixmap(14, 14))
            elif HAS_QTAWESOME:
                book_icon.setPixmap(qta.icon('fa5s.book-open', color=Styles.COLOR_TEXT_MUTED).pixmap(14, 14))
            book_icon.setFixedWidth(14)
            book_icon.setStyleSheet("background: transparent; border: none;")
            opening_layout.addWidget(book_icon)

            opening_text = f"{eco}: {opening}" if eco and opening else (opening or eco)
            opening_label = QLabel(opening_text)
            opening_label.setStyleSheet(f"""
                color: {Styles.COLOR_TEXT_SECONDARY}; 
                font-size: 12px;
                font-weight: 500;
                background: transparent;
                border: none;
            """)
            opening_label.setToolTip(opening_text)
            opening_layout.addWidget(opening_label, 1)

            content_layout.addLayout(opening_layout)

        # --- ROW 3: Metadata Badges (Speed Category, Date, Moves, Termination, Accuracy) ---
        meta_layout = QHBoxLayout()
        meta_layout.setSpacing(12)

        # Speed Category Badge
        speed_cat = getattr(game.metadata, "speed_category", None) or self._classify_time_control(game.metadata.time_control)
        formatted_tc = self._format_time_control(game.metadata.time_control)
        speed_display = f"{speed_cat} {formatted_tc}".strip() if formatted_tc and formatted_tc not in ("-", "?") else speed_cat
        tc_icon = self._get_time_control_icon(game.metadata.time_control)
        tc_widget = self._create_meta_item(tc_icon, speed_display)
        meta_layout.addWidget(tc_widget)

        # Date
        if game.metadata.date:
            date_widget = self._create_meta_item('fa5s.calendar-alt', game.metadata.date)
            meta_layout.addWidget(date_widget)

        # Chess960 badge
        if self._is_chess960(game):
            c960_widget = self._create_meta_item("assets/images/chess960.svg", "Chess960")
            meta_layout.addWidget(c960_widget)

        # Move count
        move_count = self._get_move_count(game)
        if move_count:
            moves_widget = self._create_meta_item('fa5s.chess-pawn', f"{move_count} moves")
            meta_layout.addWidget(moves_widget)

        # Human-Readable Termination Description
        term_desc = getattr(game.metadata, "termination_description", None)
        term_mode = getattr(game.metadata, "termination_mode", None)
        if not term_desc or term_desc.lower() == "normal":
            from src.backend.storage.termination_detector import TerminationDetector
            term_mode, term_desc = TerminationDetector.detect_termination(
                headers={"Result": game.metadata.result, "White": game.metadata.white, "Black": game.metadata.black, "Termination": game.metadata.termination or ""},
                moves=getattr(game, "moves", []) or [],
                starting_fen=game.metadata.starting_fen,
                chess960=self._is_chess960(game)
            )

        if term_desc and term_desc.lower() != "normal":
            term_icon = self._get_termination_icon(term_mode or term_desc)
            term_widget = self._create_meta_item(term_icon, term_desc)
            meta_layout.addWidget(term_widget)

        meta_layout.addStretch()

        # Accuracy (if analyzed)
        if hasattr(game, 'summary') and game.summary:
            white_acc = game.summary.get('white', {}).get('accuracy') if isinstance(game.summary.get('white'), dict) else game.summary.get('white_accuracy')
            black_acc = game.summary.get('black', {}).get('accuracy') if isinstance(game.summary.get('black'), dict) else game.summary.get('black_accuracy')
            if white_acc is not None and black_acc is not None:
                acc_text = f"{white_acc:.0f}% / {black_acc:.0f}%"
                acc_widget = self._create_meta_item('fa5s.bullseye', acc_text)
                meta_layout.addWidget(acc_widget)

        content_layout.addLayout(meta_layout)
        card_layout.addLayout(content_layout, stretch=1)
        root_layout.addWidget(self.card_frame)

    # ===== HELPER METHODS =====
    def _create_mini_board_widget(self, game) -> QWidget:
        """Create a compact 100x100 SVG mini chessboard matching the user's configured board theme."""
        board = chess.Board(chess960=self._is_chess960(game))
        last_move_obj = None

        if hasattr(game, 'moves') and game.moves:
            last_move = game.moves[-1]
            try:
                board.set_fen(last_move.fen_before)
                move_obj = chess.Move.from_uci(last_move.uci)
                board.push(move_obj)
                last_move_obj = move_obj
            except Exception:
                pass

        theme_name = ConfigManager().get("board_theme", "Green")
        board_theme = BOARD_THEMES.get(theme_name, BOARD_THEMES["Green"])
        dark_color = board_theme["dark"] if board_theme["dark"] != "dynamic" else "#769656"
        light_color = board_theme["light"]

        colors = {
            "square light": light_color,
            "square dark": dark_color,
        }

        svg_str = chess.svg.board(
            board=board,
            size=100,
            coordinates=False,
            lastmove=last_move_obj,
            colors=colors
        )

        svg_widget = QSvgWidget()
        svg_widget.load(svg_str.encode('utf-8'))
        svg_widget.setFixedSize(100, 100)
        svg_widget.setStyleSheet(f"""
            QSvgWidget {{
                border-radius: 6px;
                border: 1px solid {Styles.COLOR_BORDER};
                background-color: {Styles.COLOR_SURFACE};
            }}
        """)
        return svg_widget

    def _create_source_icon(self, source):
        lbl = QLabel()
        lbl.setFixedSize(18, 18)
        lbl.setScaledContents(True)
        lbl.setStyleSheet("background: transparent; border: none;")

        src_lower = str(source).lower().strip()
        if "lichess" in src_lower:
            src_name = "lichess"
        elif "chesscom" in src_lower or "chess.com" in src_lower or src_lower == "chess":
            src_name = "chesscom"
        else:
            src_name = "file"

        filename = f"{src_name}.png"
        icon_path = get_resource_path(os.path.join("assets", "icons", filename))

        if os.path.exists(icon_path):
            lbl.setPixmap(QPixmap(icon_path))
            return lbl

        if HAS_QTAWESOME:
            icon_name = "fa5s.file-alt"
            if src_name == "chesscom":
                icon_name = "fa5s.chess-pawn"
            elif src_name == "lichess":
                icon_name = "fa5s.chess-knight"
            lbl.setPixmap(qta.icon(icon_name, color=Styles.COLOR_TEXT_SECONDARY).pixmap(18, 18))
            return lbl

        return None

    def _create_winner_crown(self):
        lbl = QLabel()
        lbl.setFixedSize(16, 16)
        lbl.setScaledContents(True)
        lbl.setStyleSheet("background: transparent; border: none;")

        icon_path = get_resource_path(os.path.join("assets", "images", "winner_crown.svg"))
        if os.path.exists(icon_path):
            lbl.setPixmap(QPixmap(icon_path))
            return lbl

        if HAS_QTAWESOME:
            lbl.setPixmap(qta.icon('fa5s.crown', color='#EAB308').pixmap(16, 16))
            return lbl

        lbl.setText("👑")
        return lbl

    def _create_meta_item(self, icon, text):
        container = QWidget()
        container.setStyleSheet("background: transparent; border: none;")
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        icon_lbl = QLabel()
        icon_lbl.setFixedSize(14, 14)
        icon_lbl.setStyleSheet("background: transparent; border: none;")

        if isinstance(icon, str) and icon.endswith(".svg"):
            icon_path = get_resource_path(icon)
            if os.path.exists(icon_path):
                icon_lbl.setPixmap(QPixmap(icon_path).scaled(14, 14, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            elif HAS_QTAWESOME:
                icon_lbl.setPixmap(qta.icon('fa5s.clock', color=Styles.COLOR_TEXT_MUTED).pixmap(14, 14))
        elif isinstance(icon, str) and HAS_QTAWESOME:
            icon_lbl.setPixmap(qta.icon(icon, color=Styles.COLOR_TEXT_MUTED).pixmap(14, 14))
        else:
            icon_lbl.setText("•")

        layout.addWidget(icon_lbl)

        text_lbl = QLabel(str(text))
        text_lbl.setStyleSheet(f"color: {Styles.COLOR_TEXT_MUTED}; font-size: 12px; background: transparent; border: none;")
        layout.addWidget(text_lbl)

        return container

    def _get_result_color(self, result_text, metadata, usernames):
        if not usernames:
            if result_text == "1-0":
                return Styles.COLOR_BEST
            elif result_text == "0-1":
                return Styles.COLOR_BLUNDER
            return Styles.COLOR_TEXT_SECONDARY

        user_is_white = metadata.white.lower() in [u.lower() for u in usernames]
        user_is_black = metadata.black.lower() in [u.lower() for u in usernames]

        if result_text == "1-0":
            return Styles.COLOR_BEST if user_is_white else Styles.COLOR_BLUNDER
        elif result_text == "0-1":
            return Styles.COLOR_BEST if user_is_black else Styles.COLOR_BLUNDER
        elif result_text == "1/2-1/2":
            return Styles.COLOR_TEXT_SECONDARY

        return Styles.COLOR_TEXT_SECONDARY

    def _format_time_control(self, time_control):
        if not time_control or time_control in ("-", "?"):
            return ""

        tc = time_control.strip()
        match = re.match(r"^(\d+)(?:\+(\d+))?$", tc)
        if match:
            try:
                base_seconds = int(match.group(1))
                increment = int(match.group(2)) if match.group(2) else 0

                if base_seconds < 60:
                    base_str = f"{base_seconds}s"
                elif base_seconds % 60 == 0:
                    base_str = str(base_seconds // 60)
                else:
                    base_str = f"{base_seconds / 60:.1f}".rstrip('0').rstrip('.')

                if increment > 0:
                    return f"{base_str}+{increment}"
                else:
                    return base_str
            except ValueError:
                pass

        return time_control

    def _get_time_control_icon(self, time_control):
        tc_type = self._classify_time_control(time_control)
        return f"assets/images/{tc_type}.svg"

    def _classify_time_control(self, time_control):
        if not time_control or time_control in ("-", "?", "*", ""):
            return "Classical"

        match = re.match(r"^(\d+)(?:\+(\d+))?$", time_control.strip())
        if match:
            try:
                base_seconds = int(match.group(1))
                increment = int(match.group(2)) if match.group(2) else 0
                total_time = base_seconds + 40 * increment

                if total_time < 30:
                    return "UltraBullet"
                elif total_time < 180:
                    return "Bullet"
                elif total_time < 600:
                    return "Blitz"
                elif total_time < 1800:
                    return "Rapid"
                else:
                    return "Classical"
            except ValueError:
                pass

        tc_lower = time_control.lower()
        if "ultrabullet" in tc_lower:
            return "UltraBullet"
        elif "bullet" in tc_lower:
            return "Bullet"
        elif "blitz" in tc_lower:
            return "Blitz"
        elif "rapid" in tc_lower:
            return "Rapid"
        elif any(k in tc_lower for k in ("classical", "daily", "correspondence")):
            return "Classical"

        return "Blitz"

    def _is_chess960(self, game) -> bool:
        headers = getattr(game.metadata, 'headers', {}) or {}
        variant = headers.get("Variant", "").lower()
        if any(k in variant for k in ("960", "fischer", "random", "frc")):
            return True

        for key in ("Event", "Site"):
            val = headers.get(key, "").lower()
            if "960" in val or "frc" in val or "fischer" in val:
                return True

        fen = game.metadata.starting_fen
        if fen and fen.split()[0:4] != self._STANDARD_START_FEN.split()[0:4]:
            return True

        return False

    def _get_termination_icon(self, termination):
        term_lower = str(termination).lower()
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
