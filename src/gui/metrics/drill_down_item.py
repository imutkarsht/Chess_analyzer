"""
Drill-down occurrence list item widget.
Displays a mini SVG board thumbnail, game metadata, move detail with eval drop,
and an action button to navigate directly to the exact move in the Analysis view.
"""

from __future__ import annotations

from typing import Any

import chess
import chess.svg
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtSvgWidgets import QSvgWidget
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.gui.styles import Styles
from src.gui.theme.palette import BOARD_THEMES
from src.utils.config import ConfigManager


class DrillDownItemWidget(QFrame):
    """
    Card item representing a single tactical/game occurrence for drill-down.
    Clicking anywhere on the card emits position_selected(game_id, move_index).
    """

    position_selected = pyqtSignal(str, int)  # (game_id, move_index)

    def __init__(self, item: dict[str, Any], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("DrillDownCard")
        self.item = item
        self.game_id: str = item.get("game_id", "")
        # ply is 1-indexed, move_index in analysis board is 0-indexed
        ply = item.get("ply", 1)
        self.move_index: int = max(0, ply - 1)

        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(f"""
            QFrame#DrillDownCard {{
                background-color: {Styles.COLOR_SURFACE_CARD};
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 10px;
            }}
            QFrame#DrillDownCard:hover {{
                background-color: {Styles.COLOR_SURFACE};
                border-color: {Styles.COLOR_ACCENT};
            }}
        """)

        self._build_ui()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._trigger_selection()
        super().mousePressEvent(event)

    def _trigger_selection(self) -> None:
        if self.game_id:
            self.position_selected.emit(self.game_id, self.move_index)

    def _build_ui(self) -> None:
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(14, 12, 16, 12)
        main_layout.setSpacing(16)

        # 1. Left: Mini Board SVG in container
        mini_board = self._create_mini_board()
        main_layout.addWidget(mini_board, 0, Qt.AlignmentFlag.AlignVCenter)

        # 2. Center: Content Rows
        content_layout = QVBoxLayout()
        content_layout.setSpacing(6)
        content_layout.setContentsMargins(0, 0, 0, 0)

        # Row 1: Match & Opponent Context
        row1 = QHBoxLayout()
        row1.setSpacing(8)

        opp_name = self.item.get("opponent", "Opponent")
        opp_elo = self.item.get("opponent_elo", "")
        elo_str = (
            f" <span style='color: {Styles.COLOR_TEXT_MUTED}'>({opp_elo})</span>" if opp_elo else ""
        )
        user_color = self.item.get("user_color", "white").capitalize()

        match_lbl = QLabel(
            f"<b>vs {opp_name}</b>{elo_str} &nbsp;•&nbsp; "
            f"<span style='color: {Styles.COLOR_TEXT_SECONDARY}'>as {user_color}</span>"
        )
        match_lbl.setStyleSheet(
            Styles.get_label_style(size=13, color=Styles.COLOR_TEXT_PRIMARY)
            + " "
            + Styles.get_transparent_label_style()
        )
        row1.addWidget(match_lbl)

        # Result badge (Win/Loss/Draw)
        result = self.item.get("result", "*")
        res_color = self._get_result_color(result, user_color.lower())
        res_lbl = QLabel(result)
        res_lbl.setStyleSheet(Styles.get_result_badge_style(res_color, 11, "2px 8px", 4))
        row1.addWidget(res_lbl)

        # Speed category badge
        speed = self.item.get("speed_category", "")
        if speed:
            speed_lbl = QLabel(speed)
            speed_lbl.setStyleSheet(f"""
                QLabel {{
                    background-color: {Styles.COLOR_SURFACE_LIGHT};
                    color: {Styles.COLOR_TEXT_SECONDARY};
                    font-size: 11px;
                    font-weight: 600;
                    border: 1px solid {Styles.COLOR_BORDER};
                    border-radius: 4px;
                    padding: 2px 7px;
                }}
            """)
            row1.addWidget(speed_lbl)

        row1.addStretch()
        content_layout.addLayout(row1)

        # Row 2: Move & Turning Point Details
        row2 = QHBoxLayout()
        row2.setSpacing(8)

        move_display = self.item.get("move_display")
        if not move_display:
            move_num = self.item.get("move_number", (self.item.get("ply", 1) + 1) // 2)
            san = self.item.get("san", "")
            is_user_white = self.item.get("user_color", "white") == "white"
            move_prefix = f"{move_num}." if is_user_white else f"{move_num}..."
            move_display = (
                f"{move_prefix} {san}".strip() if san else f"Ply {self.item.get('ply', 1)}"
            )

        move_badge = QLabel(move_display)
        move_badge.setStyleSheet(f"""
            QLabel {{
                background-color: {Styles.COLOR_SURFACE_LIGHT};
                color: {Styles.COLOR_TEXT_PRIMARY};
                font-size: 13px;
                font-weight: 700;
                font-family: monospace, -apple-system, sans-serif;
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 6px;
                padding: 3px 8px;
            }}
        """)
        row2.addWidget(move_badge)

        # Classification / Motif Badge
        classification = self.item.get("classification") or ""
        if classification:
            if classification in ("Clean Game", "Clean"):
                class_color = Styles.COLOR_BEST
            elif self.item.get("is_game"):
                class_color = Styles.COLOR_ACCENT
            else:
                class_color = Styles.get_class_color(classification)
            class_badge = QLabel(classification)
            class_badge.setStyleSheet(Styles.get_result_badge_style(class_color, 11, "3px 8px", 4))
            row2.addWidget(class_badge)

        # Context detail text (Eval drop, hung piece, motif description)
        desc_text = self._build_description_text()
        if desc_text:
            desc_lbl = QLabel(desc_text)
            desc_lbl.setStyleSheet(
                Styles.get_label_style(size=12, color=Styles.COLOR_TEXT_SECONDARY)
                + " "
                + Styles.get_transparent_label_style()
            )
            row2.addWidget(desc_lbl)

        row2.addStretch()
        content_layout.addLayout(row2)

        # Row 3: Opening Name
        opening = self.item.get("opening", "")
        if opening:
            op_lbl = QLabel(opening)
            op_lbl.setStyleSheet(
                Styles.get_label_style(size=11, color=Styles.COLOR_TEXT_MUTED)
                + " "
                + Styles.get_transparent_label_style()
            )
            op_lbl.setToolTip(opening)
            content_layout.addWidget(op_lbl)

        main_layout.addLayout(content_layout, 1)

        # 3. Right: Date & "Analyze Move →" Action Column
        right_layout = QVBoxLayout()
        right_layout.setContentsMargins(0, 2, 0, 2)
        right_layout.setSpacing(6)
        right_layout.setAlignment(Qt.AlignmentFlag.AlignRight)

        date_str = self.item.get("date", "")
        if date_str:
            date_lbl = QLabel(date_str)
            date_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
            date_lbl.setStyleSheet(
                Styles.get_label_style(size=11, color=Styles.COLOR_TEXT_MUTED)
                + " "
                + Styles.get_transparent_label_style()
            )
            right_layout.addWidget(date_lbl)

        right_layout.addStretch()

        action_text = self.item.get("action_text") or (
            "Analyze Game →" if self.item.get("is_game") else "Analyze Move →"
        )
        btn_action = QPushButton(action_text)
        btn_action.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_action.setStyleSheet(f"""
            QPushButton {{
                background-color: {Styles.COLOR_SURFACE};
                color: {Styles.COLOR_ACCENT};
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 6px;
                padding: 6px 14px;
                font-size: 12px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {Styles.COLOR_ACCENT};
                color: #ffffff;
                border-color: {Styles.COLOR_ACCENT};
            }}
        """)
        btn_action.clicked.connect(self._trigger_selection)
        right_layout.addWidget(btn_action, 0, Qt.AlignmentFlag.AlignRight)

        main_layout.addLayout(right_layout, 0)

    def _build_description_text(self) -> str:
        parts: list[str] = []
        piece_name = self.item.get("piece_name")
        square = self.item.get("square")
        eval_drop = self.item.get("eval_drop")
        eval_before = self.item.get("eval_before_cp")
        eval_after = self.item.get("eval_after_cp")
        wp_drop = self.item.get("wp_drop")

        if piece_name and square:
            parts.append(f"Dropped {piece_name.capitalize()} on {square}")

        if eval_drop is not None and eval_before is not None and eval_after is not None:
            drop_str = (
                f"-{abs(eval_drop) / 100:.1f}" if eval_drop > 0 else f"+{abs(eval_drop) / 100:.1f}"
            )
            parts.append(f"Eval: {eval_before / 100:+.1f} → {eval_after / 100:+.1f} ({drop_str})")
        elif wp_drop is not None and wp_drop > 0.05:
            parts.append(f"Win % drop: -{wp_drop * 100:.0f}%")

        motif = self.item.get("motif")
        if motif and not piece_name:
            parts.append(f"Motif: {motif.replace('_', ' ').title()}")

        desc = self.item.get("description")
        if desc:
            parts.append(desc)

        return "  •  ".join(parts)

    def _get_result_color(self, result: str, user_color: str) -> str:
        if result == "1-0":
            return Styles.COLOR_RESULT_WIN if user_color == "white" else Styles.COLOR_RESULT_LOSS
        if result == "0-1":
            return Styles.COLOR_RESULT_WIN if user_color == "black" else Styles.COLOR_RESULT_LOSS
        return Styles.COLOR_RESULT_DRAW

    def _create_mini_board(self) -> QWidget:
        fen_before = self.item.get("fen_before", chess.STARTING_FEN)
        uci = self.item.get("uci", "")
        san = self.item.get("san", "")
        user_color = self.item.get("user_color", "white")

        board = chess.Board(fen_before)
        last_move_obj = None
        try:
            move_obj = chess.Move.from_uci(uci) if uci else board.parse_san(san)
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

        orientation = chess.WHITE if str(user_color).lower() == "white" else chess.BLACK

        svg_str = chess.svg.board(
            board=board,
            size=100,
            coordinates=False,
            lastmove=last_move_obj,
            orientation=orientation,
            colors=colors,
        )

        container = QFrame()
        container.setFixedSize(104, 104)
        container.setStyleSheet(f"""
            QFrame {{
                background-color: {Styles.COLOR_SURFACE};
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 8px;
            }}
        """)
        c_layout = QVBoxLayout(container)
        c_layout.setContentsMargins(1, 1, 1, 1)
        c_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        svg_widget = QSvgWidget()
        svg_widget.load(svg_str.encode("utf-8"))
        svg_widget.setFixedSize(100, 100)
        c_layout.addWidget(svg_widget)
        return container
