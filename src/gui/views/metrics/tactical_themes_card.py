"""
Tactical Themes and Motifs Card.
Displays clean, executive breakdown of tactical patterns executed across games:
Forks, Pins, Skewers, Discovered Attacks, Sacrifices, and Back-Rank Infiltrations.
Zero nested box clutter, ranked distribution bars, and DRY telemetry.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
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


class TacticalThemesCard(MetricCard):
    """
    Card displaying player tactical motif execution:
    - Executive summary strip: Total tactics found, motifs per game, top tactical weapon.
    - Proportional tactical distribution ribbon.
    - Ranked arsenal breakdown list sorted by frequency (no nested box frames).
    """

    drill_down_requested = pyqtSignal(str, str)  # (category, subcategory)

    MOTIF_CONFIG: dict[str, tuple[str, str, str, str]] = {
        # key: (Display Name, Icon, Description/Tooltip, Color Property Name)
        "fork": (
            "Fork",
            "fa5s.code-branch",
            "Double attack against two enemy targets simultaneously",
            "COLOR_BEST",
        ),
        "skewer": (
            "Skewer",
            "fa5s.arrows-alt-v",
            "Attack through a higher-value piece to win material behind it",
            "COLOR_GREAT",
        ),
        "sacrifice": (
            "Sacrifice",
            "fa5s.gem",
            "Deliberate material investment for decisive tactical or positional gain",
            "COLOR_ACCENT",
        ),
        "pin": (
            "Pin",
            "fa5s.thumbtack",
            "Immobilizing an enemy piece against their King or high-value piece",
            "COLOR_BOOK",
        ),
        "discovered_attack": (
            "Discovered Attack",
            "fa5s.eye",
            "Moving one piece to unmask a deadly line of attack from another",
            "COLOR_GOOD",
        ),
        "back_rank": (
            "Back-Rank Threat",
            "fa5s.chess-rook",
            "Infiltrating the trapped enemy King along their baseline",
            "COLOR_TEXT_SECONDARY",
        ),
    }

    def __init__(self, parent=None):
        self.stats: dict = {}
        self.content_widget: QWidget | None = None

        self.action_badge = QLabel("Pattern Execution")
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
        main_vbox.setSpacing(14)

        if total_games == 0 or total_tactics == 0:
            empty_lbl = QLabel(
                "No tactical motifs recorded yet.\nAnalyze your games to reveal tactical patterns!"
                if total_games > 0
                else "No games available for tactical motif analysis."
            )
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

        # Sort motifs by strike count descending (frequency ranking)
        sorted_motifs = sorted(
            self.MOTIF_CONFIG.keys(),
            key=lambda k: themes.get(k, 0),
            reverse=True,
        )
        top_motif_key = sorted_motifs[0]
        top_count = themes.get(top_motif_key, 0)
        top_name, top_icon, _, _ = self.MOTIF_CONFIG[top_motif_key]
        top_share = (top_count / total_tactics * 100) if total_tactics > 0 else 0.0
        tpg = (total_tactics / total_games) if total_games > 0 else 0.0

        # ═══════════════════════════════════════════════════════════════
        #  1. HERO SUMMARY STRIP (Clean, Open, Unboxed)
        # ═══════════════════════════════════════════════════════════════
        hero_strip = QWidget()
        hero_strip.setStyleSheet("background: transparent;")
        h_layout = QHBoxLayout(hero_strip)
        h_layout.setContentsMargins(0, 2, 0, 2)
        h_layout.setSpacing(16)

        # Left: Total tactics count + per game pace
        left_box = QVBoxLayout()
        left_box.setSpacing(2)

        l_stat_row = QHBoxLayout()
        l_stat_row.setSpacing(6)
        l_stat_row.setAlignment(Qt.AlignmentFlag.AlignLeft)

        lbl_tot_val = QLabel(str(total_tactics))
        lbl_tot_val.setCursor(Qt.CursorShape.PointingHandCursor)
        lbl_tot_val.setToolTip("Click to inspect all executed tactics positions")
        lbl_tot_val.mousePressEvent = lambda e: self.drill_down_requested.emit(
            "tactical_themes", "all"
        )
        lbl_tot_val.setStyleSheet(f"""
            color: {Styles.COLOR_TEXT_PRIMARY};
            font-size: 24px;
            font-weight: 800;
            background: transparent;
        """)
        l_stat_row.addWidget(lbl_tot_val)

        lbl_tot_title = QLabel("Tactics Executed")
        lbl_tot_title.setStyleSheet(f"""
            color: {Styles.COLOR_TEXT_PRIMARY};
            font-size: 13px;
            font-weight: 600;
            background: transparent;
            padding-top: 4px;
        """)
        l_stat_row.addWidget(lbl_tot_title)
        left_box.addLayout(l_stat_row)

        lbl_tot_sub = QLabel(f"{tpg:.1f} per game across {total_games} analyzed games")
        lbl_tot_sub.setStyleSheet(f"""
            color: {Styles.COLOR_TEXT_SECONDARY};
            font-size: 11px;
            background: transparent;
        """)
        left_box.addWidget(lbl_tot_sub)
        h_layout.addLayout(left_box)

        h_layout.addStretch()

        # Right: Top Weapon Badge
        right_box = QVBoxLayout()
        right_box.setSpacing(2)
        right_box.setAlignment(Qt.AlignmentFlag.AlignRight)

        top_pill = QFrame()
        top_pill.setStyleSheet(f"""
            background-color: {Styles.COLOR_SURFACE_LIGHT};
            border: 1px solid {Styles.COLOR_BORDER};
            border-radius: 6px;
        """)
        tp_layout = QHBoxLayout(top_pill)
        tp_layout.setContentsMargins(8, 4, 8, 4)
        tp_layout.setSpacing(6)

        try:
            import qtawesome as qta

            ic = QLabel()
            ic.setPixmap(qta.icon(top_icon, color=Styles.COLOR_BEST).pixmap(13, 13))
            ic.setStyleSheet("border: none; background: transparent;")
            tp_layout.addWidget(ic)
        except Exception:
            pass

        lbl_weapon = QLabel(f"Top Weapon: {top_name} ({top_share:.0f}%)")
        lbl_weapon.setStyleSheet(f"""
            color: {Styles.COLOR_TEXT_PRIMARY};
            font-size: 12px;
            font-weight: 600;
            border: none;
            background: transparent;
        """)
        tp_layout.addWidget(lbl_weapon)
        right_box.addWidget(top_pill, alignment=Qt.AlignmentFlag.AlignRight)

        lbl_weapon_sub = QLabel(f"{top_count} of {total_tactics} total tactical strikes")
        lbl_weapon_sub.setStyleSheet(f"""
            color: {Styles.COLOR_TEXT_SECONDARY};
            font-size: 11px;
            background: transparent;
        """)
        right_box.addWidget(lbl_weapon_sub, alignment=Qt.AlignmentFlag.AlignRight)

        h_layout.addLayout(right_box)
        main_vbox.addWidget(hero_strip)

        # ═══════════════════════════════════════════════════════════════
        #  2. PROPORTIONAL DISTRIBUTION RIBBON (Multi-Segmented Bar)
        # ═══════════════════════════════════════════════════════════════
        ribbon_frame = QFrame()
        ribbon_frame.setFixedHeight(8)
        ribbon_frame.setStyleSheet(f"""
            background-color: {Styles.COLOR_SURFACE_LIGHT};
            border-radius: 4px;
        """)
        r_layout = QHBoxLayout(ribbon_frame)
        r_layout.setContentsMargins(0, 0, 0, 0)
        r_layout.setSpacing(1)

        for key in sorted_motifs:
            cnt = themes.get(key, 0)
            if cnt <= 0:
                continue
            pct = cnt / total_tactics * 100
            _, _, _, color_attr = self.MOTIF_CONFIG[key]
            seg_color = getattr(Styles, color_attr, Styles.COLOR_ACCENT)

            seg = QFrame()
            seg.setFixedHeight(8)
            seg.setStyleSheet(f"""
                background-color: {seg_color};
                border-radius: 2px;
            """)
            seg.setToolTip(f"{self.MOTIF_CONFIG[key][0]}: {cnt} strikes ({pct:.1f}%)")
            r_layout.addWidget(seg, max(1, int(pct * 10)))

        main_vbox.addWidget(ribbon_frame)

        # ═══════════════════════════════════════════════════════════════
        #  3. RANKED ARSENAL LIST (Clean, Open Rows with Proportional Bars)
        # ═══════════════════════════════════════════════════════════════
        list_container = QWidget()
        list_container.setObjectName("tactics_list_container")
        list_container.setStyleSheet("background: transparent;")
        list_layout = QVBoxLayout(list_container)
        list_layout.setContentsMargins(0, 4, 0, 0)
        list_layout.setSpacing(4)

        for rank_idx, key in enumerate(sorted_motifs, start=1):
            name, icon_name, desc, color_attr = self.MOTIF_CONFIG[key]
            cnt = themes.get(key, 0)
            pct = (cnt / total_tactics * 100) if total_tactics > 0 else 0.0
            theme_color = getattr(Styles, color_attr, Styles.COLOR_BEST)

            row = QWidget()
            row.setCursor(Qt.CursorShape.PointingHandCursor)
            row.mousePressEvent = lambda e, k=key: self.drill_down_requested.emit(
                "tactical_themes", k
            )
            row.setStyleSheet(f"""
                QWidget:hover {{
                    background-color: {Styles.COLOR_SURFACE_LIGHT};
                    border-radius: 6px;
                }}
            """)
            row.setToolTip(
                f"{name}: {desc}\nExecuted {cnt} times ({pct:.1f}% of arsenal)\nClick to view positions"
            )
            row_l = QHBoxLayout(row)
            row_l.setContentsMargins(6, 4, 8, 4)
            row_l.setSpacing(10)

            # Rank
            lbl_rank = QLabel(f"{rank_idx}.")
            lbl_rank.setFixedWidth(16)
            lbl_rank.setStyleSheet(f"""
                color: {Styles.COLOR_TEXT_MUTED};
                font-size: 11px;
                font-weight: 600;
                background: transparent;
            """)
            row_l.addWidget(lbl_rank)

            # Icon
            try:
                import qtawesome as qta

                m_ic = QLabel()
                m_ic.setPixmap(qta.icon(icon_name, color=theme_color).pixmap(14, 14))
                m_ic.setFixedSize(16, 16)
                m_ic.setStyleSheet("border: none; background: transparent;")
                row_l.addWidget(m_ic)
            except Exception:
                pass

            # Name
            lbl_name = QLabel(name)
            lbl_name.setFixedWidth(130)
            lbl_name.setStyleSheet(f"""
                color: {Styles.COLOR_TEXT_PRIMARY};
                font-size: 12px;
                font-weight: 600;
                background: transparent;
            """)
            row_l.addWidget(lbl_name)

            # Proportional bar
            pbar = QProgressBar()
            pbar.setRange(0, 100)
            pbar.setValue(int(pct))
            pbar.setTextVisible(False)
            pbar.setFixedHeight(6)
            pbar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            pbar.setStyleSheet(f"""
                QProgressBar {{
                    background-color: {Styles.COLOR_SURFACE_LIGHT};
                    border: none;
                    border-radius: 3px;
                }}
                QProgressBar::chunk {{
                    background-color: {theme_color if cnt > 0 else "transparent"};
                    border-radius: 3px;
                }}
            """)
            row_l.addWidget(pbar)

            # Strikes count
            lbl_cnt = QLabel(f"{cnt} strikes" if cnt != 1 else "1 strike")
            lbl_cnt.setFixedWidth(70)
            lbl_cnt.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            lbl_cnt.setStyleSheet(f"""
                color: {Styles.COLOR_TEXT_PRIMARY};
                font-size: 12px;
                font-weight: 700;
                background: transparent;
            """)
            row_l.addWidget(lbl_cnt)

            # Percentage
            lbl_pct = QLabel(f"{pct:.1f}%")
            lbl_pct.setFixedWidth(46)
            lbl_pct.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            lbl_pct.setStyleSheet(f"""
                color: {Styles.COLOR_TEXT_SECONDARY};
                font-size: 11px;
                font-weight: 500;
                background: transparent;
            """)
            row_l.addWidget(lbl_pct)

            list_layout.addWidget(row)

        main_vbox.addWidget(list_container)
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
