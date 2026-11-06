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
    QVBoxLayout,
    QWidget,
)

from src.constants import DEFAULT_BOARD_THEME
from src.gui.components import (
    Button,
    ButtonSize,
    ButtonVariant,
    Label,
    StatusBadge,
    TextRole,
    TextTone,
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
            f"font-size: 13px; color: {Styles.COLOR_TEXT_PRIMARY}; "
            "background: transparent; border: none;"
        )
        row1.addWidget(match_lbl)

        # Result badge (Win/Loss/Draw)
        result = self.item.get("result", "*")
        res_tone = self._get_result_tone(result, user_color.lower())
        res_lbl = StatusBadge(
            result,
            res_tone,
            font_size=11,
            padding="2px 8px",
            radius=4,
        )
        row1.addWidget(res_lbl)

        # Speed category badge
        speed = self.item.get("speed_category", "")
        if speed:
            speed_lbl = StatusBadge(
                speed,
                "neutral",
                font_size=11,
                padding="2px 7px",
                radius=4,
            )
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

        move_badge = StatusBadge(
            move_display,
            "neutral",
            mono=True,
            font_size=13,
            weight=700,
            padding="3px 8px",
            radius=6,
        )
        row2.addWidget(move_badge)

        # Classification / Motif Badge
        classification = self.item.get("classification") or ""
        if classification:
            if classification in ("Clean Game", "Clean"):
                class_tone = TextTone.BEST
            elif self.item.get("is_game"):
                class_tone = TextTone.ACCENT
            else:
                try:
                    class_tone = TextTone(classification.lower())
                except ValueError:
                    class_tone = TextTone.PRIMARY
            class_badge = StatusBadge(
                classification,
                class_tone,
                font_size=11,
                padding="3px 8px",
                radius=4,
            )
            row2.addWidget(class_badge)

        # Context detail text (Eval drop, hung piece, motif description)
        desc_text = self._build_description_text()
        if desc_text:
            desc_lbl = Label(
                desc_text,
                role=TextRole.CAPTION,
                tone=TextTone.SECONDARY,
            )
            row2.addWidget(desc_lbl)

        row2.addStretch()
        content_layout.addLayout(row2)

        # Row 3: Opening Name
        opening = self.item.get("opening", "")
        if opening:
            op_lbl = Label(
                opening,
                role=TextRole.MICRO,
                tone=TextTone.MUTED,
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
            date_lbl = Label(
                date_str,
                role=TextRole.MICRO,
                tone=TextTone.MUTED,
            )
            date_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
            right_layout.addWidget(date_lbl)

        right_layout.addStretch()

        action_text = self.item.get("action_text") or (
            "Analyze Game →" if self.item.get("is_game") else "Analyze Move →"
        )
        btn_action = Button(
            action_text,
            ButtonVariant.OUTLINED,
            ButtonSize.SM,
            on_click=self._trigger_selection,
        )
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

    def _get_result_tone(self, result: str, user_color: str) -> TextTone:
        if result == "1-0":
            return (
                TextTone.RESULT_WIN
                if user_color == "white"
                else TextTone.RESULT_LOSS
            )
        if result == "0-1":
            return (
                TextTone.RESULT_WIN
                if user_color == "black"
                else TextTone.RESULT_LOSS
            )
        return TextTone.RESULT_DRAW

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

        theme_name = ConfigManager().get("board_theme", DEFAULT_BOARD_THEME)
        board_theme = BOARD_THEMES.get(theme_name, BOARD_THEMES[DEFAULT_BOARD_THEME])
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
