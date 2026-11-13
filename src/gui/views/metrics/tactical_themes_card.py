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
    QVBoxLayout,
    QWidget,
)

from src.gui.components import (
    IconLabel,
    Label,
    MiniBar,
    SegmentedBar,
    StatusBadge,
    TextRole,
    TextTone,
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
        # Hanging pieces are tracked by the dedicated piece-safety card; they
        # are a material win, not a tactical pattern.
        "fork": (
            "Fork",
            "fa5s.code-branch",
            "Double attack against two enemy targets simultaneously",
            "COLOR_BEST",
        ),
        "pin": (
            "Pin",
            "fa5s.thumbtack",
            "Immobilizing an enemy piece against their King or high-value piece",
            "COLOR_BOOK",
        ),
        "skewer": (
            "Skewer",
            "fa5s.arrows-alt-v",
            "Attack through a higher-value piece to win material behind it",
            "COLOR_GREAT",
        ),
        "discovered_attack": (
            "Discovered Attack",
            "fa5s.eye",
            "Moving one piece to unmask a deadly line of attack from another",
            "COLOR_GOOD",
        ),
        "discovered_check": (
            "Discovered Check",
            "fa5s.bullseye",
            "Moving a piece to reveal a check from a hidden attacker",
            "COLOR_BEST",
        ),
        "double_check": (
            "Double Check",
            "fa5s.crosshairs",
            "Two pieces give check at once, forcing the king to move",
            "COLOR_BEST",
        ),
        "removal_of_defender": (
            "Removal of Defender",
            "fa5s.user-slash",
            "Capturing a defender so the piece it guarded becomes loose",
            "COLOR_GREAT",
        ),
        "trapped_piece": (
            "Trapped Piece",
            "fa5s.lock",
            "A piece with no safe escape that is about to be captured",
            "COLOR_ACCENT",
        ),
        "sacrifice": (
            "Sacrifice",
            "fa5s.gem",
            "Deliberate material investment for decisive tactical or positional gain",
            "COLOR_ACCENT",
        ),
        "promotion": (
            "Promotion",
            "fa5s.arrow-up",
            "Promoting a pawn to a queen or another piece",
            "COLOR_GOOD",
        ),
        "back_rank_mate": (
            "Back-Rank Mate",
            "fa5s.chess-rook",
            "Mating the trapped enemy King along their baseline",
            "COLOR_TEXT_SECONDARY",
        ),
        "smothered_mate": (
            "Smothered Mate",
            "fa5s.chess-knight",
            "A knight mates a King surrounded by its own pieces",
            "COLOR_BOOK",
        ),
        "morphy_mate": (
            "Morphy's Mate",
            "fa5s.chess-bishop",
            "A bishop mates while a rook confines the King",
            "COLOR_TEXT_SECONDARY",
        ),
        "opera_mate": (
            "Opera Mate",
            "fa5s.chess-rook",
            "A rook mates while a bishop defends it",
            "COLOR_TEXT_SECONDARY",
        ),
        "boden_mate": (
            "Boden's Mate",
            "fa5s.chess-bishop",
            "Two bishops mate on criss-crossing diagonals",
            "COLOR_TEXT_SECONDARY",
        ),
    }

    def __init__(self, parent=None):
        self.stats: dict = {}

        self.action_badge = StatusBadge("Pattern Execution", tone="neutral")

        super().__init__(
            "Tactical Motifs & Patterns",
            parent=parent,
            min_height=340,
            action_widget=self.action_badge,
        )

    def _render_view(self):
        # Only patterns with a tactical entry belong on this card. In
        # particular, hanging pieces are a material win handled by the
        # piece-safety card, not a tactical motif.
        themes = {
            key: count
            for key, count in (self.stats.get("tactical_themes") or {}).items()
            if key in self.MOTIF_CONFIG
        }
        total_games = self.stats.get("total", 0)
        total_tactics = sum(themes.values())

        if total_games == 0 or total_tactics == 0:
            self.show_empty(
                "No tactical motifs recorded yet.\n"
                "Analyze your games to reveal tactical patterns!"
                if total_games > 0
                else "No games available for tactical motif analysis."
            )
            return

        main_vbox = self.new_content(spacing=14).layout()

        # Rank only motifs that actually occurred; zero-count rows add noise.
        sorted_motifs = sorted(
            (key for key in self.MOTIF_CONFIG if themes.get(key, 0) > 0),
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

        lbl_tot_val = Label(
            str(total_tactics),
            role=TextRole.STAT,
            size=24,
            weight=800,
        )
        lbl_tot_val.setCursor(Qt.CursorShape.PointingHandCursor)
        lbl_tot_val.setToolTip("Click to inspect all executed tactics positions")
        lbl_tot_val.mousePressEvent = lambda e: self.drill_down_requested.emit(
            "tactical_themes", "all"
        )
        l_stat_row.addWidget(lbl_tot_val)

        lbl_tot_title = Label("Tactics Executed", role=TextRole.BODY, weight=600)
        l_stat_row.addWidget(lbl_tot_title)
        left_box.addLayout(l_stat_row)

        lbl_tot_sub = Label(
            f"{tpg:.1f} per game across {total_games} analyzed games",
            role=TextRole.MICRO,
            tone=TextTone.SECONDARY,
        )
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

        tp_layout.addWidget(IconLabel(top_icon, size=13, tone=TextTone.BEST))

        lbl_weapon = Label(
            f"Top Weapon: {top_name} ({top_share:.0f}%)",
            role=TextRole.CAPTION,
            weight=600,
        )
        tp_layout.addWidget(lbl_weapon)
        right_box.addWidget(top_pill, alignment=Qt.AlignmentFlag.AlignRight)

        lbl_weapon_sub = Label(
            f"{top_count} of {total_tactics} total tactical strikes",
            role=TextRole.MICRO,
            tone=TextTone.SECONDARY,
        )
        right_box.addWidget(lbl_weapon_sub, alignment=Qt.AlignmentFlag.AlignRight)

        h_layout.addLayout(right_box)
        main_vbox.addWidget(hero_strip)

        # ═══════════════════════════════════════════════════════════════
        #  2. PROPORTIONAL DISTRIBUTION RIBBON (Multi-Segmented Bar)
        # ═══════════════════════════════════════════════════════════════
        segments = []
        for key in sorted_motifs:
            cnt = themes.get(key, 0)
            pct = cnt / total_tactics * 100
            _, _, _, color_attr = self.MOTIF_CONFIG[key]
            seg_color = getattr(Styles, color_attr, Styles.COLOR_ACCENT)
            segments.append(
                (
                    max(1, int(pct * 10)),
                    seg_color,
                    f"{self.MOTIF_CONFIG[key][0]}: {cnt} strikes ({pct:.1f}%)",
                )
            )

        main_vbox.addWidget(
            SegmentedBar(
                segments,
                height=8,
                radius=4,
                segment_radius=2,
                spacing=1,
                track_color=Styles.COLOR_SURFACE_LIGHT,
            )
        )

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
            lbl_rank = Label(
                f"{rank_idx}.",
                role=TextRole.MICRO,
                weight=600,
                tone=TextTone.MUTED,
            )
            lbl_rank.setFixedWidth(16)
            row_l.addWidget(lbl_rank)

            # Icon
            row_l.addWidget(IconLabel(icon_name, size=16, color=theme_color))

            # Name
            lbl_name = Label(name, role=TextRole.CAPTION, weight=600)
            lbl_name.setFixedWidth(130)
            row_l.addWidget(lbl_name)

            # Proportional bar
            row_l.addWidget(
                MiniBar(
                    int(pct),
                    theme_color,
                    height=6,
                    radius=3,
                    track_color=Styles.COLOR_SURFACE_LIGHT,
                )
            )

            # Strikes count
            lbl_cnt = Label(
                f"{cnt} strikes" if cnt != 1 else "1 strike",
                role=TextRole.CAPTION,
                weight=700,
            )
            lbl_cnt.setFixedWidth(70)
            lbl_cnt.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            row_l.addWidget(lbl_cnt)

            # Percentage
            lbl_pct = Label(
                f"{pct:.1f}%",
                role=TextRole.MICRO,
                weight=500,
                tone=TextTone.SECONDARY,
            )
            lbl_pct.setFixedWidth(46)
            lbl_pct.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            row_l.addWidget(lbl_pct)

            list_layout.addWidget(row)

        main_vbox.addWidget(list_container)
        self.set_content(self.content_widget)
