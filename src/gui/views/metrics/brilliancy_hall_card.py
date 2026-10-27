"""
Brilliancy Hall Card.
Executive showcase listing Brilliant (!!) moves played across analyzed games.
Strictly displays moves classified as 'Brilliant' with pagination and interactive game loading.
"""

import os

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.gui.components import (
    Button,
    ButtonSize,
    ButtonVariant,
    PaginationBar,
    StatusBadge,
)
from src.gui.styles import Styles
from src.gui.utils.gui_utils import resolve_asset
from src.gui.views.metrics.base_card import MetricCard


class ClickableFrame(QFrame):
    """QFrame subclass emitting a signal on left click."""

    clicked = pyqtSignal()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class BrilliancyHallCard(MetricCard):
    """
    Card displaying an interactive list of all Brilliant moves.
    Filters strictly for classification == 'Brilliant' (excluding 'Great').

    Features:
    - Total Brilliancies count badge in header.
    - Uses authentic brilliant.svg icon.
    - Two-line responsive layout preventing text overflow or clipping.
    - Interactive rows that emit move_selected(game_id, move_index) on click.
    - Clean pagination (4 moves per page) with prev/next navigation.
    - Clean empty state when no brilliant moves have occurred.
    """

    move_selected = pyqtSignal(str, int)  # Emits (game_id, move_index)

    PAGE_SIZE = 4

    def __init__(self, parent=None):
        self.stats: dict = {}
        self.current_page: int = 0

        self.action_badge = StatusBadge("0 Brilliancies", tone="neutral")

        super().__init__(
            "Brilliancy Hall",
            parent=parent,
            min_height=340,
            action_widget=self.action_badge,
        )

    def set_stats(self, stats: dict):
        self.stats = stats or {}
        self.current_page = 0
        self._render_view()

    def _render_view(self):
        raw_brilliancies = self.stats.get("brilliancies", [])
        # Strictly filter for classification == 'Brilliant'
        brilliants = [b for b in raw_brilliancies if b.get("classification") == "Brilliant"]
        count = len(brilliants)

        # Update header badge
        badge_text = f"{count} Brilliancy" if count == 1 else f"{count} Brilliancies"
        self.action_badge.set_text(badge_text)
        self.action_badge.set_tone("brilliant" if count > 0 else "neutral")
        self.action_badge.set_weight(700 if count > 0 else 600)

        if not brilliants:
            self.show_empty("No brilliant moves found in selected games.", stretch=1)
            return

        main_vbox = self.new_content(spacing=8).layout()

        total_pages = max(1, (count + self.PAGE_SIZE - 1) // self.PAGE_SIZE)
        self.current_page = max(0, min(self.current_page, total_pages - 1))

        start_idx = self.current_page * self.PAGE_SIZE
        end_idx = min(start_idx + self.PAGE_SIZE, count)
        page_items = brilliants[start_idx:end_idx]

        # List container for the current page items
        list_container = QWidget()
        list_container.setStyleSheet("background: transparent;")
        list_vbox = QVBoxLayout(list_container)
        list_vbox.setContentsMargins(0, 0, 0, 0)
        list_vbox.setSpacing(8)

        for b in page_items:
            row = self._create_brilliancy_row(b)
            list_vbox.addWidget(row)

        list_vbox.addStretch()
        main_vbox.addWidget(list_container, stretch=1)

        # Pagination Bar
        if total_pages > 1:
            pagination_bar = PaginationBar(
                page=self.current_page,
                total_pages=total_pages,
                prev_text="◀ Prev",
                next_text="Next ▶",
            )
            pagination_bar.prev_clicked.connect(self._go_prev_page)
            pagination_bar.next_clicked.connect(self._go_next_page)
            self.btn_prev = pagination_bar.prev_btn
            self.lbl_page = pagination_bar.label
            self.btn_next = pagination_bar.next_btn
            main_vbox.addWidget(pagination_bar)

        self.set_content(self.content_widget)

    def _go_prev_page(self):
        if self.current_page > 0:
            self.current_page -= 1
            self._render_view()

    def _go_next_page(self):
        raw_brilliancies = self.stats.get("brilliancies", [])
        brilliants = [b for b in raw_brilliancies if b.get("classification") == "Brilliant"]
        total_pages = max(1, (len(brilliants) + self.PAGE_SIZE - 1) // self.PAGE_SIZE)
        if self.current_page < total_pages - 1:
            self.current_page += 1
            self._render_view()

    def _create_brilliancy_row(self, b: dict) -> QFrame:
        san = b.get("san", "")
        move_num = b.get("move_number", "")
        move_str = f"{move_num}. {san}" if move_num and not san.startswith(str(move_num)) else san

        opp = b.get("opponent", "Unknown Opponent")
        elo = b.get("opponent_elo", "")
        opp_str = f"vs {opp} ({elo})" if elo else f"vs {opp}"

        date_str = b.get("date", "")
        opening = b.get("opening_name", "")

        meta_parts = [opp_str]
        if opening:
            meta_parts.append(opening)
        if date_str:
            meta_parts.append(date_str)
        meta_str = " • ".join(meta_parts)

        game_id = b.get("game_id", "")
        ply = b.get("ply")
        if ply is not None and int(ply) > 0:
            move_index = int(ply) - 1
        else:
            m_num = int(move_num) if str(move_num).isdigit() else 1
            user_color = str(b.get("user_color", "white")).lower()
            move_index = (m_num - 1) * 2 if user_color == "white" else (m_num - 1) * 2 + 1

        row = ClickableFrame()
        row.setObjectName("brilliancy_row")
        row.setCursor(Qt.CursorShape.PointingHandCursor)
        row.setStyleSheet(f"""
            QFrame#brilliancy_row {{
                background-color: {Styles.COLOR_SURFACE_LIGHT};
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 8px;
            }}
            QFrame#brilliancy_row:hover {{
                background-color: {Styles.COLOR_SURFACE};
                border: 1px solid {Styles.COLOR_BRILLIANT};
            }}
        """)
        row.setToolTip(f"{move_str} in {meta_str}\nClick to view move on Analysis Board.")

        r_layout = QHBoxLayout(row)
        r_layout.setContentsMargins(12, 8, 12, 8)
        r_layout.setSpacing(12)

        # 1. Authentic Brilliant SVG Icon
        lbl_icon = QLabel()
        icon_path = resolve_asset("brilliant.svg")
        if icon_path and os.path.exists(icon_path):
            pixmap = QPixmap(icon_path).scaled(
                26,
                26,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            lbl_icon.setPixmap(pixmap)
        else:
            lbl_icon.setText("!!")
            lbl_icon.setStyleSheet(f"""
                background-color: {Styles.COLOR_BRILLIANT};
                color: white;
                font-weight: 800;
                font-size: 11px;
                border-radius: 4px;
                padding: 3px 6px;
            """)
        lbl_icon.setFixedSize(26, 26)
        lbl_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_icon.setStyleSheet("border: none; background: transparent;")
        r_layout.addWidget(lbl_icon)

        # 2. Text Stack (Line 1: Move notation, Line 2: Opponent • Opening • Date)
        text_container = QWidget()
        text_container.setStyleSheet("background: transparent; border: none;")
        text_layout = QVBoxLayout(text_container)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(2)

        lbl_move = QLabel(move_str)
        lbl_move.setStyleSheet(f"""
            color: {Styles.COLOR_TEXT_PRIMARY};
            font-weight: 700;
            font-size: 14px;
            border: none;
            background: transparent;
        """)
        text_layout.addWidget(lbl_move)

        lbl_meta = QLabel(meta_str)
        lbl_meta.setStyleSheet(f"""
            color: {Styles.COLOR_TEXT_SECONDARY};
            font-size: 11px;
            font-weight: 500;
            border: none;
            background: transparent;
        """)
        lbl_meta.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        text_layout.addWidget(lbl_meta)

        r_layout.addWidget(text_container, stretch=1)

        # 3. Analyze Action Button
        btn_analyze = Button(
            "Analyze →",
            ButtonVariant.OUTLINED,
            ButtonSize.SM,
            accent=Styles.COLOR_BRILLIANT,
        )
        btn_analyze.setFixedHeight(24)
        r_layout.addWidget(btn_analyze)

        # Wire click handler on both the row and the analyze button
        def on_click():
            if game_id:
                self.move_selected.emit(game_id, move_index)

        row.clicked.connect(on_click)
        btn_analyze.clicked.connect(on_click)

        return row

    def refresh_styles(self):
        super().refresh_styles()
        if self.stats:
            self._render_view()
