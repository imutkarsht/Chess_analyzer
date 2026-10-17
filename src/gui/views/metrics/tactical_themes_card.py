"""
Tactical Themes and Motifs Card.
Displays breakdown of tactical patterns executed across games:
Forks, Pins, Skewers, Discovered Attacks, Sacrifices, and Back-Rank Infiltrations.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

from src.gui.styles import Styles
from src.gui.views.metrics.base_card import MetricCard


class TacticalThemesCard(MetricCard):
    """
    Card displaying player tactical motif execution:
    - Executive summary: Total tactics found & top tactical weapon.
    - 6-Motif breakdown grid with proportional occurrence bars:
      1. Forks (Double Attacks)
      2. Pins (Absolute pins against King)
      3. Skewers (Attack through valuable piece)
      4. Discovered Attacks (Unmasking hidden lines)
      5. Sacrifices (Material sacrifices for decisive advantage)
      6. Back-Rank Infiltrations (Exploiting trapped Kings)
    """

    MOTIF_CONFIG: dict[str, tuple[str, str, str]] = {
        "fork": ("Fork", "fa5s.code-branch", "Multi-target double attacks"),
        "pin": ("Pin", "fa5s.thumbtack", "Immobilizing pieces to King"),
        "skewer": ("Skewer", "fa5s.arrows-alt-v", "Attacking through high-value piece"),
        "discovered_attack": ("Discovered Attack", "fa5s.eye", "Unmasking hidden line of fire"),
        "sacrifice": ("Sacrifice", "fa5s.gem", "Sound material investment"),
        "back_rank": ("Back-Rank Threat", "fa5s.chess-rook", "Infiltrating trapped King"),
    }

    def __init__(self, parent=None):
        self.stats: dict = {}
        self.content_widget: QWidget | None = None

        self.action_badge = QLabel("Pattern Recognition")
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
            "Tactical Motifs & Patterns",
            parent=parent,
            min_height=340,
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

        themes = self.stats.get("tactical_themes", {})
        total_games = self.stats.get("total", 0)
        total_tactics = sum(themes.values())

        self.content_widget = QWidget()
        self.content_widget.setStyleSheet("background: transparent;")
        main_vbox = QVBoxLayout(self.content_widget)
        main_vbox.setContentsMargins(0, 0, 0, 0)
        main_vbox.setSpacing(12)

        if total_games == 0:
            empty_lbl = QLabel("No games available for tactical motif analysis.")
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

        # Identify top motif
        sorted_motifs = sorted(themes.items(), key=lambda x: x[1], reverse=True)
        top_motif_key, top_count = sorted_motifs[0] if sorted_motifs else ("fork", 0)
        top_name, top_icon, _ = self.MOTIF_CONFIG.get(top_motif_key, ("Tactics", "fa5s.bolt", ""))

        # ═══════════════════════════════════════════════════════════════
        #  1. TOP ROW: 2 HERO SUMMARY PILLARS
        # ═══════════════════════════════════════════════════════════════
        hero_row = QHBoxLayout()
        hero_row.setSpacing(12)

        # Pillar 1: Total Tactics Found
        tot_pillar = QFrame()
        tot_pillar.setObjectName("tot_pillar")
        tot_pillar.setStyleSheet(f"""
            QFrame#tot_pillar {{
                background-color: {Styles.COLOR_SURFACE_LIGHT};
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 10px;
            }}
        """)
        t_layout = QVBoxLayout(tot_pillar)
        t_layout.setContentsMargins(14, 12, 14, 12)
        t_layout.setSpacing(6)

        t_top = QHBoxLayout()
        t_tile = QFrame()
        t_tile.setFixedSize(28, 28)
        t_tile.setStyleSheet(f"""
            background-color: {Styles.COLOR_SURFACE};
            border-radius: 6px;
            border: 1px solid {Styles.COLOR_BORDER};
        """)
        tt_layout = QVBoxLayout(t_tile)
        tt_layout.setContentsMargins(0, 0, 0, 0)
        tt_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        try:
            import qtawesome as qta

            ic_t = QLabel()
            ic_t.setPixmap(qta.icon("fa5s.bolt", color=Styles.COLOR_BEST).pixmap(14, 14))
            ic_t.setStyleSheet("border: none; background: transparent;")
            tt_layout.addWidget(ic_t)
        except Exception:
            pass
        t_top.addWidget(t_tile)

        lbl_tot_title = QLabel("Tactics Executed")
        lbl_tot_title.setStyleSheet(f"""
            color: {Styles.COLOR_TEXT_PRIMARY};
            font-weight: 700;
            font-size: 13px;
            border: none;
            background: transparent;
        """)
        t_top.addWidget(lbl_tot_title)
        t_top.addStretch()
        t_layout.addLayout(t_top)

        lbl_tot_val = QLabel(str(total_tactics))
        lbl_tot_val.setStyleSheet(f"""
            color: {Styles.COLOR_TEXT_PRIMARY};
            font-size: 26px;
            font-weight: 800;
            border: none;
            background: transparent;
        """)
        t_layout.addWidget(lbl_tot_val)

        tpg = (total_tactics / total_games) if total_games > 0 else 0.0
        lbl_tot_sub = QLabel(f"{tpg:.1f} motifs per game • across sound moves")
        lbl_tot_sub.setStyleSheet(f"""
            color: {Styles.COLOR_TEXT_SECONDARY};
            font-size: 11px;
            font-weight: 500;
            border: none;
            background: transparent;
        """)
        t_layout.addWidget(lbl_tot_sub)
        hero_row.addWidget(tot_pillar)

        # Pillar 2: Sharpest Weapon
        top_pillar = QFrame()
        top_pillar.setObjectName("top_pillar")
        top_pillar.setStyleSheet(f"""
            QFrame#top_pillar {{
                background-color: {Styles.COLOR_SURFACE_LIGHT};
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 10px;
            }}
        """)
        tp_layout = QVBoxLayout(top_pillar)
        tp_layout.setContentsMargins(14, 12, 14, 12)
        tp_layout.setSpacing(6)

        tp_top = QHBoxLayout()
        tp_tile = QFrame()
        tp_tile.setFixedSize(28, 28)
        tp_tile.setStyleSheet(f"""
            background-color: {Styles.COLOR_SURFACE};
            border-radius: 6px;
            border: 1px solid {Styles.COLOR_BORDER};
        """)
        tpt_layout = QVBoxLayout(tp_tile)
        tpt_layout.setContentsMargins(0, 0, 0, 0)
        tpt_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        try:
            import qtawesome as qta

            ic_tp = QLabel()
            ic_tp.setPixmap(qta.icon(top_icon, color=Styles.COLOR_TEXT_SECONDARY).pixmap(14, 14))
            ic_tp.setStyleSheet("border: none; background: transparent;")
            tpt_layout.addWidget(ic_tp)
        except Exception:
            pass
        tp_top.addWidget(tp_tile)

        lbl_weapon_title = QLabel("Sharpest Weapon")
        lbl_weapon_title.setStyleSheet(f"""
            color: {Styles.COLOR_TEXT_PRIMARY};
            font-weight: 700;
            font-size: 13px;
            border: none;
            background: transparent;
        """)
        tp_top.addWidget(lbl_weapon_title)
        tp_top.addStretch()
        tp_layout.addLayout(tp_top)

        lbl_weapon_val = QLabel(top_name if total_tactics > 0 else "None")
        lbl_weapon_val.setStyleSheet(f"""
            color: {Styles.COLOR_TEXT_PRIMARY};
            font-size: 22px;
            font-weight: 800;
            border: none;
            background: transparent;
        """)
        tp_layout.addWidget(lbl_weapon_val)

        share_pct = (top_count / total_tactics * 100) if total_tactics > 0 else 0.0
        lbl_weapon_sub = QLabel(
            f"{top_count} strikes • {share_pct:.0f}% of all tactical blows"
            if total_tactics > 0
            else "No tactics executed yet"
        )
        lbl_weapon_sub.setStyleSheet(f"""
            color: {Styles.COLOR_TEXT_SECONDARY};
            font-size: 11px;
            font-weight: 500;
            border: none;
            background: transparent;
        """)
        tp_layout.addWidget(lbl_weapon_sub)
        hero_row.addWidget(top_pillar)

        main_vbox.addLayout(hero_row)

        # ═══════════════════════════════════════════════════════════════
        #  2. MIDDLE SECTION: 6-MOTIF GRID BREAKDOWN
        # ═══════════════════════════════════════════════════════════════
        grid_frame = QFrame()
        grid_frame.setObjectName("motifs_grid")
        grid_frame.setStyleSheet(f"""
            QFrame#motifs_grid {{
                background-color: {Styles.COLOR_SURFACE_LIGHT};
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 8px;
                padding: 10px 12px;
            }}
        """)
        g_layout = QVBoxLayout(grid_frame)
        g_layout.setContentsMargins(12, 10, 12, 10)
        g_layout.setSpacing(8)

        grid_title = QLabel("Tactical Patterns Breakdown")
        grid_title.setStyleSheet(f"""
            color: {Styles.COLOR_TEXT_PRIMARY};
            font-weight: 700;
            font-size: 12px;
            border: none;
            background: transparent;
        """)
        g_layout.addWidget(grid_title)

        grid = QGridLayout()
        grid.setSpacing(8)
        grid.setContentsMargins(0, 0, 0, 0)

        motif_order = [
            ("fork", 0, 0),
            ("pin", 0, 1),
            ("discovered_attack", 1, 0),
            ("skewer", 1, 1),
            ("sacrifice", 2, 0),
            ("back_rank", 2, 1),
        ]

        for key, row, col in motif_order:
            name, icon_name, desc = self.MOTIF_CONFIG[key]
            cnt = themes.get(key, 0)
            pct = (cnt / total_tactics * 100) if total_tactics > 0 else 0.0

            tile = QFrame()
            tile.setObjectName("motif_tile")
            tile.setStyleSheet(f"""
                QFrame#motif_tile {{
                    background-color: {Styles.COLOR_SURFACE};
                    border: 1px solid {Styles.COLOR_BORDER};
                    border-radius: 6px;
                    padding: 8px 10px;
                }}
            """)
            tl_layout = QVBoxLayout(tile)
            tl_layout.setContentsMargins(8, 6, 8, 6)
            tl_layout.setSpacing(4)

            # Top Row: Icon + Name on left, Count badge on right
            m_top = QHBoxLayout()
            m_top.setSpacing(6)

            try:
                import qtawesome as qta

                m_ic = QLabel()
                m_ic.setPixmap(qta.icon(icon_name, color=Styles.COLOR_TEXT_SECONDARY).pixmap(13, 13))
                m_ic.setStyleSheet("border: none; background: transparent;")
                m_top.addWidget(m_ic)
            except Exception:
                pass

            m_lbl = QLabel(name)
            m_lbl.setStyleSheet(f"""
                color: {Styles.COLOR_TEXT_PRIMARY};
                font-weight: 600;
                font-size: 11px;
                border: none;
                background: transparent;
            """)
            m_top.addWidget(m_lbl)
            m_top.addStretch()

            cnt_badge = QLabel(str(cnt))
            cnt_badge.setStyleSheet(f"""
                color: {Styles.COLOR_TEXT_PRIMARY};
                font-weight: 700;
                font-size: 12px;
                border: none;
                background: transparent;
            """)
            m_top.addWidget(cnt_badge)
            tl_layout.addLayout(m_top)

            # Mini Progress Bar
            pbar = QProgressBar()
            pbar.setRange(0, 100)
            pbar.setValue(int(pct))
            pbar.setTextVisible(False)
            pbar.setFixedHeight(4)
            pbar.setStyleSheet(f"""
                QProgressBar {{
                    background-color: {Styles.COLOR_SURFACE_LIGHT};
                    border: none;
                    border-radius: 2px;
                }}
                QProgressBar::chunk {{
                    background-color: {Styles.COLOR_BEST if cnt > 0 else "transparent"};
                    border-radius: 2px;
                }}
            """)
            tl_layout.addWidget(pbar)

            # Sub description
            desc_lbl = QLabel(desc)
            desc_lbl.setStyleSheet(f"""
                color: {Styles.COLOR_TEXT_MUTED};
                font-size: 9px;
                border: none;
                background: transparent;
            """)
            tl_layout.addWidget(desc_lbl)

            grid.addWidget(tile, row, col)

        g_layout.addLayout(grid)
        main_vbox.addWidget(grid_frame)

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

