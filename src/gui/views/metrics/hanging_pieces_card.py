"""
Hanging Pieces and Tactical Awareness Card.
Displays robust tracking of undefended pieces dropped vs opponent hanging pieces capitalized on,
with piece-type breakdown and tactical vigilance insights.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

from src.gui.styles import Styles
from src.gui.views.metrics.base_card import MetricCard


class HangingPiecesCard(MetricCard):
    """
    Card visualizing piece safety and tactical awareness:
    1. Pieces Hung: Undefended pieces dropped without tactical compensation.
    2. Captured When Hanging: Opponent hanging pieces capitalized on.
    3. Piece Vulnerability Breakdown: Distribution across piece types.
    """

    PIECE_ICONS: dict[str, tuple[str, str]] = {
        "pawn": ("fa5s.chess-pawn", "P"),
        "knight": ("fa5s.chess-knight", "N"),
        "bishop": ("fa5s.chess-bishop", "B"),
        "rook": ("fa5s.chess-rook", "R"),
        "queen": ("fa5s.chess-queen", "Q"),
    }

    def __init__(self, parent=None):
        self.stats: dict = {}
        self.content_widget: QWidget | None = None

        self.action_badge = QLabel("Board Awareness")
        self.action_badge.setStyleSheet(f"""
            background-color: {Styles.COLOR_SURFACE_LIGHT};
            color: {Styles.COLOR_TEXT_SECONDARY};
            font-size: 11px;
            font-weight: 600;
            border: 1px solid {Styles.COLOR_BORDER};
            border-radius: 6px;
            padding: 3px 8px;
        """)

        super().__init__(
            "Piece Safety & Hanging Pieces",
            parent=parent,
            min_height=320,
            action_widget=self.action_badge,
        )

    def set_stats(self, stats: dict):
        self.stats = stats or {}
        self._render_view()

    def _render_view(self):
        if self.content_widget:
            self.card_layout.removeWidget(self.content_widget)
            self.content_widget.deleteLater()
            self.content_widget = None

        h_stats = self.stats.get("hanging_stats", {})
        total_games = self.stats.get("total", 0)

        total_hung = h_stats.get("total_hung", 0)
        hanging_blunders = h_stats.get("hanging_blunders", 0)
        by_piece = h_stats.get("by_piece", {})

        opp_captured = h_stats.get("opponent_hanging_captured", 0)
        opp_missed = h_stats.get("opponent_hanging_missed", 0)
        captured_by_piece = h_stats.get("captured_by_piece", {})

        self.content_widget = QWidget()
        self.content_widget.setStyleSheet("background: transparent;")
        main_vbox = QVBoxLayout(self.content_widget)
        main_vbox.setContentsMargins(0, 0, 0, 0)
        main_vbox.setSpacing(12)

        if total_games == 0:
            empty_lbl = QLabel("No games available for piece safety analysis.")
            empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_lbl.setStyleSheet(f"""
                color: {Styles.COLOR_TEXT_SECONDARY};
                font-size: 12px;
                padding: 40px 10px;
                background: transparent;
            """)
            main_vbox.addWidget(empty_lbl)
            self.set_content(self.content_widget)
            return

        # ═══════════════════════════════════════════════════════════════
        #  1. TOP ROW: 2 EXECUTIVE HERO PILLARS
        # ═══════════════════════════════════════════════════════════════
        hero_row = QHBoxLayout()
        hero_row.setSpacing(12)

        # Pillar 1: Pieces Hung (Dropped)
        hung_pillar = QFrame()
        hung_pillar.setObjectName("hung_pillar")
        hung_pillar.setStyleSheet(f"""
            QFrame#hung_pillar {{
                background-color: {Styles.COLOR_SURFACE_LIGHT};
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 10px;
            }}
        """)
        h_layout = QVBoxLayout(hung_pillar)
        h_layout.setContentsMargins(14, 12, 14, 12)
        h_layout.setSpacing(6)

        h_top = QHBoxLayout()
        h_tile = QFrame()
        h_tile.setFixedSize(28, 28)
        h_tile.setStyleSheet(f"""
            background-color: {Styles.COLOR_SURFACE};
            border-radius: 6px;
            border: 1px solid {Styles.COLOR_BORDER};
        """)
        h_tile_layout = QVBoxLayout(h_tile)
        h_tile_layout.setContentsMargins(0, 0, 0, 0)
        h_tile_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        try:
            import qtawesome as qta

            ic_h = QLabel()
            ic_h.setPixmap(qta.icon("fa5s.shield-alt", color=Styles.COLOR_TEXT_SECONDARY).pixmap(14, 14))
            ic_h.setStyleSheet("border: none; background: transparent;")
            h_tile_layout.addWidget(ic_h)
        except Exception:
            pass
        h_top.addWidget(h_tile)

        lbl_hung_title = QLabel("Pieces Hung")
        lbl_hung_title.setStyleSheet(f"""
            color: {Styles.COLOR_TEXT_PRIMARY};
            font-weight: 700;
            font-size: 13px;
            border: none;
            background: transparent;
        """)
        h_top.addWidget(lbl_hung_title)
        h_top.addStretch()
        h_layout.addLayout(h_top)

        lbl_hung_val = QLabel(str(total_hung))
        lbl_hung_val.setStyleSheet(f"""
            color: {Styles.COLOR_TEXT_PRIMARY};
            font-size: 26px;
            font-weight: 800;
            border: none;
            background: transparent;
        """)
        h_layout.addWidget(lbl_hung_val)

        hung_per_game = (total_hung / total_games) if total_games > 0 else 0.0
        hung_sub = (
            f"{hung_per_game:.1f} per game • {hanging_blunders} blunders caused"
            if total_games > 1
            else f"{hanging_blunders} blunder caused"
        )
        lbl_hung_sub = QLabel(hung_sub)
        lbl_hung_sub.setStyleSheet(f"""
            color: {Styles.COLOR_TEXT_SECONDARY};
            font-size: 11px;
            font-weight: 500;
            border: none;
            background: transparent;
        """)
        h_layout.addWidget(lbl_hung_sub)
        hero_row.addWidget(hung_pillar)

        # Pillar 2: Captured When Hanging
        cap_pillar = QFrame()
        cap_pillar.setObjectName("cap_pillar")
        cap_pillar.setStyleSheet(f"""
            QFrame#cap_pillar {{
                background-color: {Styles.COLOR_SURFACE_LIGHT};
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 10px;
            }}
        """)
        c_layout = QVBoxLayout(cap_pillar)
        c_layout.setContentsMargins(14, 12, 14, 12)
        c_layout.setSpacing(6)

        c_top = QHBoxLayout()
        c_tile = QFrame()
        c_tile.setFixedSize(28, 28)
        c_tile.setStyleSheet(f"""
            background-color: {Styles.COLOR_SURFACE};
            border-radius: 6px;
            border: 1px solid {Styles.COLOR_BORDER};
        """)
        c_tile_layout = QVBoxLayout(c_tile)
        c_tile_layout.setContentsMargins(0, 0, 0, 0)
        c_tile_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        try:
            import qtawesome as qta

            ic_c = QLabel()
            ic_c.setPixmap(qta.icon("fa5s.crosshairs", color=Styles.COLOR_BEST).pixmap(14, 14))
            ic_c.setStyleSheet("border: none; background: transparent;")
            c_tile_layout.addWidget(ic_c)
        except Exception:
            pass
        c_top.addWidget(c_tile)

        lbl_cap_title = QLabel("Captured When Hanging")
        lbl_cap_title.setStyleSheet(f"""
            color: {Styles.COLOR_TEXT_PRIMARY};
            font-weight: 700;
            font-size: 13px;
            border: none;
            background: transparent;
        """)
        c_top.addWidget(lbl_cap_title)
        c_top.addStretch()
        c_layout.addLayout(c_top)

        lbl_cap_val = QLabel(str(opp_captured))
        lbl_cap_val.setStyleSheet(f"""
            color: {Styles.COLOR_TEXT_PRIMARY};
            font-size: 26px;
            font-weight: 800;
            border: none;
            background: transparent;
        """)
        c_layout.addWidget(lbl_cap_val)

        total_opp_hanging = opp_captured + opp_missed
        cap_rate = (opp_captured / total_opp_hanging * 100) if total_opp_hanging > 0 else 0.0
        cap_sub = (
            f"{cap_rate:.0f}% seized • {opp_missed} missed"
            if total_opp_hanging > 0
            else "Capitalized on opponent errors"
        )
        lbl_cap_sub = QLabel(cap_sub)
        lbl_cap_sub.setStyleSheet(f"""
            color: {Styles.COLOR_TEXT_SECONDARY};
            font-size: 11px;
            font-weight: 500;
            border: none;
            background: transparent;
        """)
        c_layout.addWidget(lbl_cap_sub)
        hero_row.addWidget(cap_pillar)

        main_vbox.addLayout(hero_row)

        # ═══════════════════════════════════════════════════════════════
        #  2. MIDDLE SECTION: PIECE BREAKDOWN (VULNERABILITY)
        # ═══════════════════════════════════════════════════════════════
        breakdown_box = QFrame()
        breakdown_box.setObjectName("breakdown_box")
        breakdown_box.setStyleSheet(f"""
            QFrame#breakdown_box {{
                background-color: {Styles.COLOR_SURFACE_LIGHT};
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 8px;
                padding: 10px 12px;
            }}
        """)
        b_layout = QVBoxLayout(breakdown_box)
        b_layout.setContentsMargins(12, 10, 12, 10)
        b_layout.setSpacing(8)

        b_header = QHBoxLayout()
        b_title = QLabel("Piece Breakdown (Hung vs Punished)")
        b_title.setStyleSheet(f"""
            color: {Styles.COLOR_TEXT_PRIMARY};
            font-weight: 700;
            font-size: 12px;
            border: none;
            background: transparent;
        """)
        b_header.addWidget(b_title)
        b_header.addStretch()

        b_legend = QLabel(f"<span style='color:{Styles.COLOR_TEXT_SECONDARY};'>Hung</span> • <span style='color:{Styles.COLOR_BEST};'>Captured</span>")
        b_legend.setStyleSheet("font-size: 10px; font-weight: 600; border: none; background: transparent;")
        b_header.addWidget(b_legend)
        b_layout.addLayout(b_header)

        # 5 Piece Badges Row
        pieces_row = QHBoxLayout()
        pieces_row.setSpacing(8)

        for p_key in ("pawn", "knight", "bishop", "rook", "queen"):
            icon_name, short_code = self.PIECE_ICONS.get(p_key, ("fa5s.chess", p_key[:1].upper()))
            hung_count = by_piece.get(p_key, 0)
            cap_count = captured_by_piece.get(p_key, 0)

            p_pill = QFrame()
            p_pill.setObjectName("piece_pill")
            p_pill.setStyleSheet(f"""
                QFrame#piece_pill {{
                    background-color: {Styles.COLOR_SURFACE};
                    border: 1px solid {Styles.COLOR_BORDER};
                    border-radius: 6px;
                    padding: 6px 8px;
                }}
            """)
            pill_layout = QVBoxLayout(p_pill)
            pill_layout.setContentsMargins(6, 4, 6, 4)
            pill_layout.setSpacing(4)
            pill_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

            p_top = QHBoxLayout()
            p_top.setSpacing(4)
            p_top.setAlignment(Qt.AlignmentFlag.AlignCenter)
            try:
                import qtawesome as qta

                p_ic = QLabel()
                p_ic.setPixmap(qta.icon(icon_name, color=Styles.COLOR_TEXT_SECONDARY).pixmap(12, 12))
                p_ic.setStyleSheet("border: none; background: transparent;")
                p_top.addWidget(p_ic)
            except Exception:
                pass

            p_name = QLabel(p_key.capitalize())
            p_name.setStyleSheet(f"""
                color: {Styles.COLOR_TEXT_PRIMARY};
                font-weight: 600;
                font-size: 11px;
                border: none;
                background: transparent;
            """)
            p_top.addWidget(p_name)
            pill_layout.addLayout(p_top)

            # Stat counts: hung vs captured
            cnt_row = QHBoxLayout()
            cnt_row.setSpacing(6)
            cnt_row.setAlignment(Qt.AlignmentFlag.AlignCenter)

            h_cnt_lbl = QLabel(f"{hung_count}")
            h_cnt_lbl.setStyleSheet(f"""
                color: {Styles.COLOR_TEXT_PRIMARY};
                font-weight: 700;
                font-size: 12px;
                border: none;
                background: transparent;
            """)
            cnt_row.addWidget(h_cnt_lbl)

            slash_lbl = QLabel("/")
            slash_lbl.setStyleSheet(f"color: {Styles.COLOR_TEXT_MUTED}; font-size: 10px; border: none;")
            cnt_row.addWidget(slash_lbl)

            c_cnt_lbl = QLabel(f"{cap_count}")
            c_cnt_lbl.setStyleSheet(f"""
                color: {Styles.COLOR_BEST};
                font-weight: 700;
                font-size: 12px;
                border: none;
                background: transparent;
            """)
            cnt_row.addWidget(c_cnt_lbl)

            pill_layout.addLayout(cnt_row)
            pieces_row.addWidget(p_pill)

        b_layout.addLayout(pieces_row)
        main_vbox.addWidget(breakdown_box)

        # ═══════════════════════════════════════════════════════════════
        #  3. BOTTOM VIGILANCE PROGRESS & INSIGHT
        # ═══════════════════════════════════════════════════════════════
        # Capture conversion bar
        if total_opp_hanging > 0:
            bar_container = QFrame()
            bar_container.setObjectName("awareness_bar_box")
            bar_container.setStyleSheet(f"""
                QFrame#awareness_bar_box {{
                    background-color: {Styles.COLOR_SURFACE_LIGHT};
                    border: 1px solid {Styles.COLOR_BORDER};
                    border-radius: 6px;
                    padding: 8px 10px;
                }}
            """)
            bar_layout = QVBoxLayout(bar_container)
            bar_layout.setContentsMargins(8, 6, 8, 6)
            bar_layout.setSpacing(4)

            bar_header = QHBoxLayout()
            bar_title = QLabel("Tactical Vigilance (Free Pieces Punished)")
            bar_title.setStyleSheet(f"""
                color: {Styles.COLOR_TEXT_PRIMARY};
                font-size: 11px;
                font-weight: 600;
                border: none;
                background: transparent;
            """)
            bar_header.addWidget(bar_title)
            bar_header.addStretch()

            bar_pct = QLabel(f"{cap_rate:.0f}%")
            bar_pct_color = Styles.COLOR_BEST if cap_rate >= 70 else (Styles.COLOR_GOOD if cap_rate >= 50 else Styles.COLOR_INACCURACY)
            bar_pct.setStyleSheet(f"""
                color: {bar_pct_color};
                font-size: 11px;
                font-weight: 700;
                border: none;
                background: transparent;
            """)
            bar_header.addWidget(bar_pct)
            bar_layout.addLayout(bar_header)

            pbar = QProgressBar()
            pbar.setRange(0, 100)
            pbar.setValue(int(cap_rate))
            pbar.setTextVisible(False)
            pbar.setFixedHeight(5)
            pbar.setStyleSheet(f"""
                QProgressBar {{
                    background-color: {Styles.COLOR_SURFACE};
                    border: none;
                    border-radius: 2px;
                }}
                QProgressBar::chunk {{
                    background-color: {bar_pct_color};
                    border-radius: 2px;
                }}
            """)
            bar_layout.addWidget(pbar)
            main_vbox.addWidget(bar_container)

        self.set_content(self.content_widget)

    def refresh_styles(self):
        super().refresh_styles()
        if hasattr(self, "action_badge"):
            self.action_badge.setStyleSheet(f"""
                background-color: {Styles.COLOR_SURFACE_LIGHT};
                color: {Styles.COLOR_TEXT_SECONDARY};
                font-size: 11px;
                font-weight: 600;
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 6px;
                padding: 3px 8px;
            """)
        if self.stats:
            self._render_view()

