"""
Advantage Capitalization and Comeback Card.
Visualizes how effectively a player converts decisive leads (+3.0 pawns)
versus squandering them, and their fighting spirit / comeback rate when trailing (-3.0 pawns).
Clean, open design with zero cluttered box-in-a-box frames.
"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
)

from src.gui.components import Label, SegmentedBar, StatusBadge, TextRole, TextTone
from src.gui.styles import Styles
from src.gui.views.metrics.base_card import MetricCard


class AdvantageConversionCard(MetricCard):
    """
    Card visualizing game conversion and resilience:
    1. Advantage Capitalization: Win conversion from winning positions (>= +3.0 pawns).
    2. Choke / Throw Tracking: Distinguishing between drawn leads and thrown losses.
    3. Comeback / Resilience: Frequency of rescuing wins or draws from losing positions (<= -3.0 pawns).
    """

    drill_down_requested = pyqtSignal(str, str)  # (category, subcategory)

    def __init__(self, parent=None):
        self.stats: dict = {}

        self.action_badge = StatusBadge("Conversion Analytics", tone="neutral")

        super().__init__(
            "Advantage Capitalization & Comeback",
            parent=parent,
            min_height=280,
            action_widget=self.action_badge,
        )

    def _render_view(self):
        adv = self.stats.get("advantage_stats", {})
        total_games = self.stats.get("total", 0)

        hwa = adv.get("had_winning_advantage", 0)
        converted = adv.get("converted_advantage", 0)
        thrown = adv.get("thrown_losses", 0)
        squandered = adv.get("squandered_draws", 0)
        conv_rate = adv.get("conversion_rate", 0.0)

        hlp = adv.get("had_losing_position", 0)
        comeback_total = adv.get("comeback_drawn_or_won", 0)
        comeback_wins = adv.get("comeback_wins", 0)
        comeback_draws = adv.get("comeback_draws", 0)
        lost_deficit = max(0, hlp - comeback_total)
        comeback_rate = adv.get("comeback_rate", 0.0)

        # Update action badge
        if hwa > 0:
            throw_text = f" • {thrown} Thrown" if thrown > 0 else ""
            self.action_badge.set_text(f"{conv_rate:.0f}% Conversion{throw_text}")
        else:
            self.action_badge.set_text("Conversion Analytics")

        if total_games == 0:
            self.show_empty("No games available for advantage conversion analysis.")
            return

        main_vbox = self.new_content(spacing=14).layout()
        main_vbox.setContentsMargins(4, 4, 4, 4)

        # ═══════════════════════════════════════════════════════════════
        #  1. TOP ROW: 2 CLEAN OPEN PANELS
        # ═══════════════════════════════════════════════════════════════
        hero_row = QHBoxLayout()
        hero_row.setSpacing(16)

        # Panel 1: Decisive Advantage
        adv_pillar = QFrame()
        adv_pillar.setObjectName("adv_pillar")
        adv_pillar.setStyleSheet(f"""
            QFrame#adv_pillar {{
                background-color: {Styles.COLOR_SURFACE_LIGHT};
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 8px;
            }}
        """)
        adv_vbox = QVBoxLayout(adv_pillar)
        adv_vbox.setContentsMargins(14, 12, 14, 12)
        adv_vbox.setSpacing(8)

        adv_title = Label(
            "DECISIVE ADVANTAGE (>= +3.0 PAWNS)",
            role=TextRole.CARD_TITLE,
            size=10,
            weight=700,
            tone=TextTone.SECONDARY,
        )
        adv_vbox.addWidget(adv_title)

        num_sub_layout = QHBoxLayout()
        num_sub_layout.setSpacing(10)
        num_sub_layout.setAlignment(Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignLeft)

        adv_num = Label(
            f"{conv_rate:.1f}%" if hwa > 0 else "N/A",
            role=TextRole.STAT,
            tone=TextTone.RESULT_WIN,
        )
        num_sub_layout.addWidget(adv_num)

        adv_sub = Label(
            f"{converted} of {hwa} won" if hwa > 0 else "No leads >= +3.0",
            role=TextRole.CAPTION,
            tone=TextTone.SECONDARY,
        )
        num_sub_layout.addWidget(adv_sub)
        num_sub_layout.addStretch()
        adv_vbox.addLayout(num_sub_layout)

        # Segmented conversion bar (clean 6px bar)
        if hwa > 0:
            win_w = max(1, int(converted / hwa * 100))
            draw_w = max(1, int(squandered / hwa * 100)) if squandered > 0 else 0
            loss_w = max(1, int(thrown / hwa * 100)) if thrown > 0 else 0

            segments = [(win_w, Styles.COLOR_RESULT_WIN, None)]
            if draw_w > 0:
                segments.append((draw_w, Styles.COLOR_RESULT_DRAW, None))
            if loss_w > 0:
                segments.append((loss_w, Styles.COLOR_BLUNDER, None))

            adv_vbox.addWidget(
                SegmentedBar(
                    segments,
                    height=6,
                    radius=3,
                    segment_radius=3,
                    spacing=2,
                    track_color=None,
                )
            )
        else:
            adv_vbox.addWidget(
                SegmentedBar(
                    height=6,
                    radius=3,
                    segment_radius=3,
                    spacing=2,
                    track_color=Styles.COLOR_BORDER,
                )
            )

        # Clean typography stats (NO nested box clutter)
        stats_line = QHBoxLayout()
        stats_line.setContentsMargins(0, 4, 0, 0)
        stats_line.setSpacing(8)

        def add_stat_col(
            layout: QHBoxLayout,
            value: int,
            label: str,
            tone: TextTone,
            subcategory: str | None = None,
        ):
            w = QWidget()
            w.setObjectName("AdvantageStat")
            w.setStyleSheet("""
                QWidget#AdvantageStat {
                    background: transparent;
                    border-radius: 4px;
                }
                QWidget#AdvantageStat QLabel {
                    background: transparent;
                    border: none;
                }
            """)
            if subcategory and value > 0:
                w.setCursor(Qt.CursorShape.PointingHandCursor)
                w.setToolTip(f"Click to inspect {value} {label.lower()} positions")
                w.setStyleSheet(f"""
                    QWidget#AdvantageStat {{
                        background: transparent;
                        border-radius: 4px;
                    }}
                    QWidget#AdvantageStat QLabel {{
                        background: transparent;
                        border: none;
                    }}
                    QWidget#AdvantageStat:hover {{
                        background-color: {Styles.COLOR_SURFACE};
                    }}
                """)
                w.mousePressEvent = lambda e, sc=subcategory: self.drill_down_requested.emit(
                    "advantage", sc
                )

            vl = QVBoxLayout(w)
            vl.setContentsMargins(4, 2, 4, 2)
            vl.setSpacing(1)
            vl.setAlignment(Qt.AlignmentFlag.AlignCenter)

            v_lbl = Label(
                str(value),
                role=TextRole.SUBHEADING,
                weight=700,
                tone=tone,
            )
            v_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            vl.addWidget(v_lbl)

            l_lbl = Label(
                label,
                role=TextRole.MICRO,
                size=10,
                weight=600,
                tone=TextTone.SECONDARY,
            )
            l_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            vl.addWidget(l_lbl)

            layout.addWidget(w)

        add_stat_col(stats_line, converted, "Wins", TextTone.RESULT_WIN)
        add_stat_col(
            stats_line,
            squandered,
            "Draws",
            TextTone.PRIMARY,
            subcategory="squandered_draws",
        )
        add_stat_col(
            stats_line,
            thrown,
            "Thrown",
            TextTone.BLUNDER if thrown > 0 else TextTone.SECONDARY,
            subcategory="thrown_losses",
        )
        adv_vbox.addLayout(stats_line)

        hero_row.addWidget(adv_pillar)

        # Panel 2: Decisive Deficit & Comeback
        comeback_pillar = QFrame()
        comeback_pillar.setObjectName("comeback_pillar")
        comeback_pillar.setStyleSheet(f"""
            QFrame#comeback_pillar {{
                background-color: {Styles.COLOR_SURFACE_LIGHT};
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 8px;
            }}
        """)
        cb_vbox = QVBoxLayout(comeback_pillar)
        cb_vbox.setContentsMargins(14, 12, 14, 12)
        cb_vbox.setSpacing(8)

        cb_title = Label(
            "DECISIVE DEFICIT (<= -3.0 PAWNS)",
            role=TextRole.CARD_TITLE,
            size=10,
            weight=700,
            tone=TextTone.SECONDARY,
        )
        cb_vbox.addWidget(cb_title)

        cb_num_sub = QHBoxLayout()
        cb_num_sub.setSpacing(10)
        cb_num_sub.setAlignment(Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignLeft)

        cb_num = Label(
            f"{comeback_rate:.1f}%" if hlp > 0 else "N/A",
            role=TextRole.STAT,
            tone=TextTone.ACCENT,
        )
        cb_num_sub.addWidget(cb_num)

        cb_sub = Label(
            f"{comeback_total} of {hlp} saved" if hlp > 0 else "No deficits <= -3.0",
            role=TextRole.CAPTION,
            tone=TextTone.SECONDARY,
        )
        cb_num_sub.addWidget(cb_sub)
        cb_num_sub.addStretch()
        cb_vbox.addLayout(cb_num_sub)

        # Segmented comeback bar
        if hlp > 0:
            res_w = max(1, int(comeback_total / hlp * 100)) if comeback_total > 0 else 0
            def_w = max(1, int(lost_deficit / hlp * 100)) if lost_deficit > 0 else 0

            segments = []
            if res_w > 0:
                segments.append((res_w, Styles.COLOR_ACCENT, None))
            if def_w > 0:
                segments.append((def_w, Styles.COLOR_BORDER, None))

            cb_vbox.addWidget(
                SegmentedBar(
                    segments,
                    height=6,
                    radius=3,
                    segment_radius=3,
                    spacing=2,
                    track_color=None,
                )
            )
        else:
            cb_vbox.addWidget(
                SegmentedBar(
                    height=6,
                    radius=3,
                    segment_radius=3,
                    spacing=2,
                    track_color=Styles.COLOR_BORDER,
                )
            )

        # Clean typography stats for Comeback
        cb_stats_line = QHBoxLayout()
        cb_stats_line.setContentsMargins(0, 4, 0, 0)
        cb_stats_line.setSpacing(8)

        add_stat_col(
            cb_stats_line,
            comeback_wins,
            "Miracle Wins",
            TextTone.ACCENT,
            subcategory="comeback_wins",
        )
        add_stat_col(
            cb_stats_line,
            comeback_draws,
            "Saved Draws",
            TextTone.PRIMARY,
            subcategory="comeback_draws",
        )
        add_stat_col(cb_stats_line, lost_deficit, "Defeats", TextTone.SECONDARY)
        cb_vbox.addLayout(cb_stats_line)

        hero_row.addWidget(comeback_pillar)
        main_vbox.addLayout(hero_row)

        # ═══════════════════════════════════════════════════════════════
        #  2. BOTTOM INSIGHT BANNER (Clean, non-boxy)
        # ═══════════════════════════════════════════════════════════════
        insight_frame = QFrame()
        insight_frame.setObjectName("conversion_insight_frame")
        insight_frame.setStyleSheet(f"""
            QFrame#conversion_insight_frame {{
                background-color: {Styles.COLOR_SURFACE_LIGHT};
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 6px;
                padding: 10px 14px;
            }}
        """)
        ins_layout = QHBoxLayout(insight_frame)
        ins_layout.setContentsMargins(10, 8, 10, 8)
        ins_layout.setSpacing(10)

        # Formulate insight
        if hwa == 0 and hlp == 0:
            verdict_text = "Balanced Match Dynamics: Neither player reached extreme evaluation leads (+3.0 / -3.0 pawns) in this filter range."
            indicator_tone = TextTone.SECONDARY
        elif thrown == 0 and hwa > 0:
            verdict_text = "Clinical Finisher: Flawless advantage security. 100% of winning leads were guided to victory or safe draws with 0 thrown games."
            indicator_tone = TextTone.RESULT_WIN
        elif thrown >= 2 or (hwa > 0 and (thrown / hwa) >= 0.20):
            verdict_text = f"High Volatility: {thrown} games were lost from winning positions (>= +3.0 pawns). Prioritize simplification and king safety when ahead."
            indicator_tone = TextTone.BLUNDER
        elif comeback_rate >= 25.0 and hlp >= 3:
            verdict_text = f"Tenacious Defender: Rescued {comeback_rate:.0f}% of lost games ({comeback_total} saves). Excellent resilience and resourcefulness under pressure."
            indicator_tone = TextTone.ACCENT
        else:
            verdict_text = f"Solid Conversion: {conv_rate:.0f}% conversion efficiency on winning advantages with reliable endgame technique."
            indicator_tone = TextTone.PRIMARY

        ins_lbl = Label(
            verdict_text,
            role=TextRole.MICRO,
            weight=500,
            tone=(
                TextTone.BLUNDER
                if indicator_tone is TextTone.BLUNDER
                else TextTone.SECONDARY
            ),
            wrap=True,
        )
        ins_layout.addWidget(ins_lbl, stretch=1)

        main_vbox.addWidget(insight_frame)
        self.set_content(self.content_widget)
