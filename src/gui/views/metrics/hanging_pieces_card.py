"""
Hanging Pieces and Board Awareness Card.
Visualizes defensive vulnerabilities (dropped pieces & blunders) alongside
tactical vigilance (capitalization on opponent free pieces).
Structured dual-pillar layout with zero duplication and zero cryptic fractions.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.gui.styles import Styles
from src.gui.views.metrics.base_card import MetricCard


class HangingPiecesCard(MetricCard):
    """
    Card visualizing piece safety and tactical awareness:
    - Left Pillar: Defensive Leaks (Pieces dropped by user, blunders caused, worst piece blindspots).
    - Right Pillar: Tactical Vigilance (Capitalization rate on opponent free pieces, integrated progress bar).
    """

    PIECE_CONFIG: dict[str, tuple[str, str]] = {
        "pawn": ("fa5s.chess-pawn", "Pawn"),
        "knight": ("fa5s.chess-knight", "Knight"),
        "bishop": ("fa5s.chess-bishop", "Bishop"),
        "rook": ("fa5s.chess-rook", "Rook"),
        "queen": ("fa5s.chess-queen", "Queen"),
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
            "Piece Safety & Awareness",
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
        #  DUAL PILLARS: DEFENSIVE LEAKS (LEFT) vs TACTICAL VIGILANCE (RIGHT)
        # ═══════════════════════════════════════════════════════════════
        pillars_row = QHBoxLayout()
        pillars_row.setSpacing(14)

        # -------------------------------------------------------------
        # Left Pillar: Defensive Leaks
        # -------------------------------------------------------------
        leak_pillar = QFrame()
        leak_pillar.setObjectName("leak_pillar")
        leak_pillar.setStyleSheet(f"""
            QFrame#leak_pillar {{
                background-color: {Styles.COLOR_SURFACE_LIGHT};
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 8px;
            }}
        """)
        l_layout = QVBoxLayout(leak_pillar)
        l_layout.setContentsMargins(14, 12, 14, 12)
        l_layout.setSpacing(8)

        # Header with Shield Icon
        l_top = QHBoxLayout()
        l_top.setSpacing(8)
        try:
            import qtawesome as qta

            ic_l = QLabel()
            ic_l.setPixmap(
                qta.icon(
                    "fa5s.shield-alt",
                    color=Styles.COLOR_BLUNDER if total_hung > 0 else Styles.COLOR_BEST,
                ).pixmap(14, 14)
            )
            ic_l.setStyleSheet("border: none; background: transparent;")
            l_top.addWidget(ic_l)
        except Exception:
            pass

        lbl_leak_title = QLabel("DEFENSIVE LEAKS")
        lbl_leak_title.setStyleSheet(f"""
            color: {Styles.COLOR_TEXT_SECONDARY};
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 0.5px;
            border: none;
            background: transparent;
        """)
        l_top.addWidget(lbl_leak_title)
        l_top.addStretch()
        l_layout.addLayout(l_top)

        # Hero Stat: Total Dropped
        lbl_hung_val = QLabel(f"{total_hung} Dropped")
        lbl_hung_val.setStyleSheet(f"""
            color: {Styles.COLOR_TEXT_PRIMARY};
            font-size: 22px;
            font-weight: 800;
            border: none;
            background: transparent;
        """)
        l_layout.addWidget(lbl_hung_val)

        hung_per_game = (total_hung / total_games) if total_games > 0 else 0.0
        hung_sub = (
            f"{hung_per_game:.1f} per game • Caused {hanging_blunders} blunders"
            if total_games > 1
            else f"Caused {hanging_blunders} blunders"
        )
        lbl_hung_sub = QLabel(hung_sub)
        lbl_hung_sub.setStyleSheet(f"""
            color: {Styles.COLOR_TEXT_SECONDARY};
            font-size: 11px;
            border: none;
            background: transparent;
        """)
        l_layout.addWidget(lbl_hung_sub)

        # Divider
        div_l = QFrame()
        div_l.setFixedHeight(1)
        div_l.setStyleSheet(f"background-color: {Styles.COLOR_BORDER}; margin: 2px 0;")
        l_layout.addWidget(div_l)

        # Subtitle
        lbl_leak_sub = QLabel("DROPPED BY PIECE")
        lbl_leak_sub.setStyleSheet(f"""
            color: {Styles.COLOR_TEXT_MUTED};
            font-size: 10px;
            font-weight: 700;
            letter-spacing: 0.4px;
            border: none;
            background: transparent;
        """)
        l_layout.addWidget(lbl_leak_sub)

        # 5 piece rows sorted descending by hung count
        sorted_leaks = sorted(
            self.PIECE_CONFIG.keys(),
            key=lambda p: by_piece.get(p, 0),
            reverse=True,
        )
        piece_list_l = QVBoxLayout()
        piece_list_l.setSpacing(5)

        for p_key in sorted_leaks:
            icon_name, p_name = self.PIECE_CONFIG[p_key]
            h_cnt = by_piece.get(p_key, 0)
            h_share = (h_cnt / total_hung * 100) if total_hung > 0 else 0.0

            p_row = QHBoxLayout()
            p_row.setSpacing(6)

            try:
                import qtawesome as qta

                p_ic = QLabel()
                p_ic.setPixmap(
                    qta.icon(icon_name, color=Styles.COLOR_TEXT_SECONDARY).pixmap(12, 12)
                )
                p_ic.setStyleSheet("border: none; background: transparent;")
                p_row.addWidget(p_ic)
            except Exception:
                pass

            p_lbl = QLabel(p_name)
            p_lbl.setStyleSheet(f"""
                color: {Styles.COLOR_TEXT_PRIMARY};
                font-size: 11px;
                font-weight: 600;
                border: none;
                background: transparent;
            """)
            p_lbl.setFixedWidth(60)
            p_row.addWidget(p_lbl)

            # Mini bar
            pbar = QProgressBar()
            pbar.setRange(0, 100)
            pbar.setValue(int(h_share))
            pbar.setTextVisible(False)
            pbar.setFixedHeight(4)
            pbar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            pbar.setStyleSheet(f"""
                QProgressBar {{
                    background-color: {Styles.COLOR_SURFACE};
                    border: none;
                    border-radius: 2px;
                }}
                QProgressBar::chunk {{
                    background-color: {Styles.COLOR_BLUNDER if h_cnt > 0 else "transparent"};
                    border-radius: 2px;
                }}
            """)
            p_row.addWidget(pbar)

            cnt_lbl = QLabel(f"{h_cnt}")
            cnt_lbl.setFixedWidth(24)
            cnt_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
            cnt_lbl.setStyleSheet(f"""
                color: {Styles.COLOR_TEXT_PRIMARY if h_cnt > 0 else Styles.COLOR_TEXT_MUTED};
                font-size: 11px;
                font-weight: 700;
                border: none;
                background: transparent;
            """)
            p_row.addWidget(cnt_lbl)

            piece_list_l.addLayout(p_row)

        l_layout.addLayout(piece_list_l)
        pillars_row.addWidget(leak_pillar)

        # -------------------------------------------------------------
        # Right Pillar: Tactical Vigilance
        # -------------------------------------------------------------
        vig_pillar = QFrame()
        vig_pillar.setObjectName("vigilance_pillar")
        vig_pillar.setStyleSheet(f"""
            QFrame#vigilance_pillar {{
                background-color: {Styles.COLOR_SURFACE_LIGHT};
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 8px;
            }}
        """)
        v_layout = QVBoxLayout(vig_pillar)
        v_layout.setContentsMargins(14, 12, 14, 12)
        v_layout.setSpacing(8)

        # Header with Crosshairs Icon
        v_top = QHBoxLayout()
        v_top.setSpacing(8)
        try:
            import qtawesome as qta

            ic_v = QLabel()
            ic_v.setPixmap(qta.icon("fa5s.crosshairs", color=Styles.COLOR_BEST).pixmap(14, 14))
            ic_v.setStyleSheet("border: none; background: transparent;")
            v_top.addWidget(ic_v)
        except Exception:
            pass

        lbl_vig_title = QLabel("TACTICAL VIGILANCE")
        lbl_vig_title.setStyleSheet(f"""
            color: {Styles.COLOR_TEXT_SECONDARY};
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 0.5px;
            border: none;
            background: transparent;
        """)
        v_top.addWidget(lbl_vig_title)
        v_top.addStretch()
        v_layout.addLayout(v_top)

        # Hero Stat: Capitalization Rate
        total_opp_hanging = opp_captured + opp_missed
        cap_rate = (opp_captured / total_opp_hanging * 100) if total_opp_hanging > 0 else 0.0
        bar_pct_color = (
            Styles.COLOR_BEST
            if cap_rate >= 70
            else (Styles.COLOR_GOOD if cap_rate >= 50 else Styles.COLOR_INACCURACY)
        )

        lbl_vig_val = QLabel(f"{cap_rate:.0f}% Capitalized" if total_opp_hanging > 0 else "N/A")
        lbl_vig_val.setStyleSheet(f"""
            color: {bar_pct_color if total_opp_hanging > 0 else Styles.COLOR_TEXT_PRIMARY};
            font-size: 22px;
            font-weight: 800;
            border: none;
            background: transparent;
        """)
        v_layout.addWidget(lbl_vig_val)

        vig_sub = (
            f"{opp_captured} of {total_opp_hanging} seized • {opp_missed} missed"
            if total_opp_hanging > 0
            else "No opponent hanging pieces recorded"
        )
        lbl_vig_sub = QLabel(vig_sub)
        lbl_vig_sub.setStyleSheet(f"""
            color: {Styles.COLOR_TEXT_SECONDARY};
            font-size: 11px;
            border: none;
            background: transparent;
        """)
        v_layout.addWidget(lbl_vig_sub)

        # Integrated Vigilance Progress Bar
        vig_pbar = QProgressBar()
        vig_pbar.setRange(0, 100)
        vig_pbar.setValue(int(cap_rate))
        vig_pbar.setTextVisible(False)
        vig_pbar.setFixedHeight(5)
        vig_pbar.setStyleSheet(f"""
            QProgressBar {{
                background-color: {Styles.COLOR_SURFACE};
                border: none;
                border-radius: 2px;
            }}
            QProgressBar::chunk {{
                background-color: {bar_pct_color if total_opp_hanging > 0 else "transparent"};
                border-radius: 2px;
            }}
        """)
        v_layout.addWidget(vig_pbar)

        # Divider
        div_v = QFrame()
        div_v.setFixedHeight(1)
        div_v.setStyleSheet(f"background-color: {Styles.COLOR_BORDER}; margin: 2px 0;")
        v_layout.addWidget(div_v)

        # Subtitle
        lbl_cap_sub = QLabel("FREE PIECES PUNISHED")
        lbl_cap_sub.setStyleSheet(f"""
            color: {Styles.COLOR_TEXT_MUTED};
            font-size: 10px;
            font-weight: 700;
            letter-spacing: 0.4px;
            border: none;
            background: transparent;
        """)
        v_layout.addWidget(lbl_cap_sub)

        # 5 piece rows sorted descending by captured count
        sorted_caps = sorted(
            self.PIECE_CONFIG.keys(),
            key=lambda p: captured_by_piece.get(p, 0),
            reverse=True,
        )
        piece_list_v = QVBoxLayout()
        piece_list_v.setSpacing(5)

        for p_key in sorted_caps:
            icon_name, p_name = self.PIECE_CONFIG[p_key]
            c_cnt = captured_by_piece.get(p_key, 0)
            c_share = (c_cnt / opp_captured * 100) if opp_captured > 0 else 0.0

            p_row = QHBoxLayout()
            p_row.setSpacing(6)

            try:
                import qtawesome as qta

                p_ic = QLabel()
                p_ic.setPixmap(
                    qta.icon(icon_name, color=Styles.COLOR_TEXT_SECONDARY).pixmap(12, 12)
                )
                p_ic.setStyleSheet("border: none; background: transparent;")
                p_row.addWidget(p_ic)
            except Exception:
                pass

            p_lbl = QLabel(p_name)
            p_lbl.setStyleSheet(f"""
                color: {Styles.COLOR_TEXT_PRIMARY};
                font-size: 11px;
                font-weight: 600;
                border: none;
                background: transparent;
            """)
            p_lbl.setFixedWidth(60)
            p_row.addWidget(p_lbl)

            # Mini bar
            pbar = QProgressBar()
            pbar.setRange(0, 100)
            pbar.setValue(int(c_share))
            pbar.setTextVisible(False)
            pbar.setFixedHeight(4)
            pbar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            pbar.setStyleSheet(f"""
                QProgressBar {{
                    background-color: {Styles.COLOR_SURFACE};
                    border: none;
                    border-radius: 2px;
                }}
                QProgressBar::chunk {{
                    background-color: {Styles.COLOR_BEST if c_cnt > 0 else "transparent"};
                    border-radius: 2px;
                }}
            """)
            p_row.addWidget(pbar)

            cnt_lbl = QLabel(f"{c_cnt}")
            cnt_lbl.setFixedWidth(24)
            cnt_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
            cnt_lbl.setStyleSheet(f"""
                color: {Styles.COLOR_TEXT_PRIMARY if c_cnt > 0 else Styles.COLOR_TEXT_MUTED};
                font-size: 11px;
                font-weight: 700;
                border: none;
                background: transparent;
            """)
            p_row.addWidget(cnt_lbl)

            piece_list_v.addLayout(p_row)

        v_layout.addLayout(piece_list_v)
        pillars_row.addWidget(vig_pillar)

        main_vbox.addLayout(pillars_row)
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
