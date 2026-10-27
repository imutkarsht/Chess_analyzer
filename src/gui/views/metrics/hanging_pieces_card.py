"""
Hanging Pieces and Board Awareness Card.
Visualizes defensive vulnerabilities (dropped pieces & blunders) alongside
tactical vigilance (capitalization on opponent free pieces).
Structured dual-pillar layout with zero duplication and zero cryptic fractions.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
)

from src.gui.components import MiniBar, StatusBadge
from src.gui.styles import Styles
from src.gui.views.metrics.base_card import MetricCard


class HangingPiecesCard(MetricCard):
    """
    Card visualizing piece safety and tactical awareness:
    - Left Pillar: Defensive Leaks (Pieces dropped by user, blunders caused, worst piece blindspots).
    - Right Pillar: Tactical Vigilance (Capitalization rate on opponent free pieces, integrated progress bar).
    """

    drill_down_requested = pyqtSignal(str, str)  # (category, subcategory)

    PIECE_CONFIG: dict[str, tuple[str, str]] = {
        "pawn": ("fa5s.chess-pawn", "Pawn"),
        "knight": ("fa5s.chess-knight", "Knight"),
        "bishop": ("fa5s.chess-bishop", "Bishop"),
        "rook": ("fa5s.chess-rook", "Rook"),
        "queen": ("fa5s.chess-queen", "Queen"),
    }

    def __init__(self, parent=None):
        self.stats: dict = {}

        self.action_badge = StatusBadge("Board Awareness", tone="neutral")

        super().__init__(
            "Piece Safety & Awareness",
            parent=parent,
            min_height=320,
            action_widget=self.action_badge,
        )

    def _render_view(self):
        h_stats = self.stats.get("hanging_stats", {})
        total_games = self.stats.get("total", 0)

        total_hung = h_stats.get("total_hung", 0)
        hanging_blunders = h_stats.get("hanging_blunders", 0)
        by_piece = h_stats.get("by_piece", {})

        opp_captured = h_stats.get("opponent_hanging_captured", 0)
        opp_missed = h_stats.get("opponent_hanging_missed", 0)
        captured_by_piece = h_stats.get("captured_by_piece", {})

        if total_games == 0:
            self.show_empty("No games available for piece safety analysis.")
            return

        main_vbox = self.new_content(spacing=12).layout()
        pillars_row = QHBoxLayout()
        pillars_row.setSpacing(14)

        hung_per_game = (total_hung / total_games) if total_games > 0 else 0.0
        hung_sub = (
            f"{hung_per_game:.1f} per game • Caused {hanging_blunders} blunders"
            if total_games > 1
            else f"Caused {hanging_blunders} blunders"
        )

        pillars_row.addWidget(
            self._build_piece_pillar(
                object_name="leak_pillar",
                title="DEFENSIVE LEAKS",
                icon_name="fa5s.shield-alt",
                icon_color=Styles.COLOR_BLUNDER if total_hung > 0 else Styles.COLOR_BEST,
                hero_text=f"{total_hung} Dropped",
                hero_tooltip="Click to inspect all dropped piece positions",
                hero_color=Styles.COLOR_TEXT_PRIMARY,
                hero_category="hung_pieces",
                hero_subtitle=hung_sub,
                section_title="DROPPED BY PIECE",
                piece_counts=by_piece,
                share_total=total_hung,
                bar_color=Styles.COLOR_BLUNDER,
                row_category="hung_pieces",
                row_tooltip_template="Click to inspect {count} dropped {name} positions",
            )
        )

        total_opp_hanging = opp_captured + opp_missed
        cap_rate = (opp_captured / total_opp_hanging * 100) if total_opp_hanging > 0 else 0.0
        bar_pct_color = (
            Styles.COLOR_BEST
            if cap_rate >= 70
            else (Styles.COLOR_GOOD if cap_rate >= 50 else Styles.COLOR_INACCURACY)
        )
        vig_sub = (
            f"{opp_captured} of {total_opp_hanging} seized • {opp_missed} missed"
            if total_opp_hanging > 0
            else "No opponent hanging pieces recorded"
        )

        pillars_row.addWidget(
            self._build_piece_pillar(
                object_name="vigilance_pillar",
                title="TACTICAL VIGILANCE",
                icon_name="fa5s.crosshairs",
                icon_color=Styles.COLOR_BEST,
                hero_text=(
                    f"{cap_rate:.0f}% Capitalized" if total_opp_hanging > 0 else "N/A"
                ),
                hero_tooltip="Click to inspect all opponent hanging pieces punished",
                hero_color=(
                    bar_pct_color if total_opp_hanging > 0 else Styles.COLOR_TEXT_PRIMARY
                ),
                hero_category="opp_captured",
                hero_subtitle=vig_sub,
                section_title="FREE PIECES PUNISHED",
                piece_counts=captured_by_piece,
                share_total=opp_captured,
                bar_color=Styles.COLOR_BEST,
                row_category="opp_captured",
                row_tooltip_template=(
                    "Click to inspect {count} punished opponent {name} positions"
                ),
                hero_bar=(
                    int(cap_rate),
                    bar_pct_color if total_opp_hanging > 0 else "transparent",
                ),
            )
        )

        main_vbox.addLayout(pillars_row)
        self.set_content(self.content_widget)

    def _build_piece_pillar(
        self,
        *,
        object_name: str,
        title: str,
        icon_name: str,
        icon_color: str,
        hero_text: str,
        hero_tooltip: str,
        hero_color: str,
        hero_category: str,
        hero_subtitle: str,
        section_title: str,
        piece_counts: dict[str, int],
        share_total: int,
        bar_color: str,
        row_category: str,
        row_tooltip_template: str,
        hero_bar: tuple[int, str] | None = None,
    ) -> QFrame:
        pillar = QFrame()
        pillar.setObjectName(object_name)
        pillar.setStyleSheet(f"""
            QFrame#{object_name} {{
                background-color: {Styles.COLOR_SURFACE_LIGHT};
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 8px;
            }}
        """)
        layout = QVBoxLayout(pillar)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        header = QHBoxLayout()
        header.setSpacing(8)
        pixmap = self._icon_pixmap(icon_name, icon_color, 14)
        if pixmap is not None:
            icon_lbl = QLabel()
            icon_lbl.setPixmap(pixmap)
            icon_lbl.setStyleSheet("border: none; background: transparent;")
            header.addWidget(icon_lbl)

        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(f"""
            color: {Styles.COLOR_TEXT_SECONDARY};
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 0.5px;
            border: none;
            background: transparent;
        """)
        header.addWidget(title_lbl)
        header.addStretch()
        layout.addLayout(header)

        hero = QLabel(hero_text)
        hero.setCursor(Qt.CursorShape.PointingHandCursor)
        hero.setToolTip(hero_tooltip)
        hero.mousePressEvent = lambda _event: self.drill_down_requested.emit(
            hero_category, "all"
        )
        hero.setStyleSheet(f"""
            color: {hero_color};
            font-size: 22px;
            font-weight: 800;
            border: none;
            background: transparent;
        """)
        layout.addWidget(hero)

        subtitle = QLabel(hero_subtitle)
        subtitle.setStyleSheet(f"""
            color: {Styles.COLOR_TEXT_SECONDARY};
            font-size: 11px;
            border: none;
            background: transparent;
        """)
        layout.addWidget(subtitle)

        if hero_bar is not None:
            value, chunk_color = hero_bar
            layout.addWidget(
                MiniBar(value, chunk_color, height=5, radius=2)
            )

        divider = QFrame()
        divider.setFixedHeight(1)
        divider.setStyleSheet(f"background-color: {Styles.COLOR_BORDER}; margin: 2px 0;")
        layout.addWidget(divider)

        section_lbl = QLabel(section_title)
        section_lbl.setStyleSheet(f"""
            color: {Styles.COLOR_TEXT_MUTED};
            font-size: 10px;
            font-weight: 700;
            letter-spacing: 0.4px;
            border: none;
            background: transparent;
        """)
        layout.addWidget(section_lbl)

        piece_list = QVBoxLayout()
        piece_list.setSpacing(5)
        sorted_pieces = sorted(
            self.PIECE_CONFIG.keys(),
            key=lambda piece: piece_counts.get(piece, 0),
            reverse=True,
        )
        for piece_key in sorted_pieces:
            piece_icon, piece_name = self.PIECE_CONFIG[piece_key]
            count = piece_counts.get(piece_key, 0)
            share = (count / share_total * 100) if share_total > 0 else 0.0
            piece_list.addWidget(
                self._create_piece_row(
                    icon_name=piece_icon,
                    piece_name=piece_name,
                    count=count,
                    share=share,
                    bar_color=bar_color,
                    category=row_category,
                    piece_key=piece_key,
                    tooltip=row_tooltip_template.format(count=count, name=piece_name),
                )
            )
        layout.addLayout(piece_list)
        return pillar

    def _create_piece_row(
        self,
        *,
        icon_name: str,
        piece_name: str,
        count: int,
        share: float,
        bar_color: str,
        category: str,
        piece_key: str,
        tooltip: str,
    ) -> QFrame:
        row = QFrame()
        row.setCursor(Qt.CursorShape.PointingHandCursor)
        row.setToolTip(tooltip)
        row.setStyleSheet(f"""
            QFrame {{
                background: transparent;
                border-radius: 4px;
            }}
            QFrame:hover {{
                background-color: {Styles.COLOR_SURFACE};
            }}
        """)
        row.mousePressEvent = lambda _event, key=piece_key: self.drill_down_requested.emit(
            category, key
        )

        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(4, 2, 4, 2)
        row_layout.setSpacing(6)

        pixmap = self._icon_pixmap(icon_name, Styles.COLOR_TEXT_SECONDARY, 12)
        if pixmap is not None:
            icon_lbl = QLabel()
            icon_lbl.setPixmap(pixmap)
            icon_lbl.setStyleSheet("border: none; background: transparent;")
            row_layout.addWidget(icon_lbl)

        name_lbl = QLabel(piece_name)
        name_lbl.setStyleSheet(f"""
            color: {Styles.COLOR_TEXT_PRIMARY};
            font-size: 11px;
            font-weight: 600;
            border: none;
            background: transparent;
        """)
        name_lbl.setFixedWidth(60)
        row_layout.addWidget(name_lbl)

        row_layout.addWidget(
            MiniBar(
                int(share),
                bar_color if count > 0 else "transparent",
                height=4,
                radius=2,
            )
        )

        count_lbl = QLabel(f"{count}")
        count_lbl.setFixedWidth(24)
        count_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        count_lbl.setStyleSheet(f"""
            color: {Styles.COLOR_TEXT_PRIMARY if count > 0 else Styles.COLOR_TEXT_MUTED};
            font-size: 11px;
            font-weight: 700;
            border: none;
            background: transparent;
        """)
        row_layout.addWidget(count_lbl)
        return row

    @staticmethod
    def _icon_pixmap(icon_name: str, color: str, size: int) -> QPixmap | None:
        try:
            import qtawesome as qta

            return qta.icon(icon_name, color=color).pixmap(size, size)
        except Exception:
            return None
