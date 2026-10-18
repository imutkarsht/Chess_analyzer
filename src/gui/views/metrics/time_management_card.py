"""
Time Control and Clock Analytics Card.
Displays format performance breakdown (Bullet, Blitz, Rapid, Classical),
move pace and thinking time across game phases (Opening, Middlegame, Endgame),
decision quality pace (Best vs Blunders), and time trouble panic metrics.
"""

import math

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from src.gui.styles import Styles
from src.gui.views.metrics.base_card import MetricCard


class TimeManagementCard(MetricCard):
    """
    Card displaying time control and clock analytics.
    Features 3 executive views via a header segmented control and QStackedWidget:
    - [Formats]: Performance breakdown per speed category (Bullet, Blitz, Rapid, Classical)
    - [Move Pace]: Thinking time across game phases and decision quality (Best vs Blunders)
    - [Time Trouble]: Error rates under time pressure vs normal clock & panic index
    """

    FORMAT_META: dict[str, tuple[str, str]] = {
        "Bullet": ("fa5s.bolt", "Fast-paced scrambles (<3m)"),
        "Blitz": ("fa5s.stopwatch", "Standard fast play (3–5m)"),
        "Rapid": ("fa5s.hourglass-half", "Tactical calculation (10–30m)"),
        "Classical": ("fa5s.chess-rook", "Traditional classical (>30m)"),
        "Chess960": ("fa5s.random", "Fischer Random (Freestyle)"),
        "UltraBullet": ("fa5s.tachometer-alt", "Hyper-speed play (<30s)"),
    }

    def __init__(self, parent=None):
        self.stats: dict = {}
        self.current_mode = "formats"  # "formats", "pace", "trouble"

        # Action widget: segmented control
        self.segmented_control = self._build_segmented_control()

        super().__init__(
            "Time & Clock Analytics",
            parent=parent,
            min_height=320,
            action_widget=self.segmented_control,
        )

        # Central container using QStackedWidget for instant flicker-free switching
        self.stack = QStackedWidget()
        self.stack.setStyleSheet("background: transparent;")

        self.formats_page = QWidget()
        self.formats_page.setStyleSheet("background: transparent;")
        self.formats_layout = QVBoxLayout(self.formats_page)
        self.formats_layout.setContentsMargins(0, 0, 0, 0)
        self.formats_layout.setSpacing(10)
        self.stack.addWidget(self.formats_page)

        self.pace_page = QWidget()
        self.pace_page.setStyleSheet("background: transparent;")
        self.pace_layout = QVBoxLayout(self.pace_page)
        self.pace_layout.setContentsMargins(0, 0, 0, 0)
        self.pace_layout.setSpacing(12)
        self.stack.addWidget(self.pace_page)

        self.trouble_page = QWidget()
        self.trouble_page.setStyleSheet("background: transparent;")
        self.trouble_layout = QVBoxLayout(self.trouble_page)
        self.trouble_layout.setContentsMargins(0, 0, 0, 0)
        self.trouble_layout.setSpacing(12)
        self.stack.addWidget(self.trouble_page)

        self.set_content(self.stack)

    def _build_segmented_control(self) -> QFrame:
        container = QFrame()
        container.setObjectName("time_segmented")
        container.setStyleSheet(f"""
            QFrame#time_segmented {{
                background-color: {Styles.COLOR_SURFACE_LIGHT};
                border-radius: 6px;
                border: none;
            }}
        """)
        layout = QHBoxLayout(container)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)

        self.btn_formats = QPushButton("Formats")
        self.btn_pace = QPushButton("Move Pace")
        self.btn_trouble = QPushButton("Time Trouble")

        for btn, mode in [
            (self.btn_formats, "formats"),
            (self.btn_pace, "pace"),
            (self.btn_trouble, "trouble"),
        ]:
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedHeight(22)
            btn.clicked.connect(lambda checked=False, m=mode: self.set_mode(m))
            layout.addWidget(btn)

        self._update_segmented_styles()
        return container

    def _update_segmented_styles(self):
        active_style = f"""
            QPushButton {{
                background-color: {Styles.COLOR_ACCENT};
                color: #ffffff;
                font-size: 11px;
                font-weight: 600;
                border-radius: 4px;
                padding: 2px 8px;
                border: none;
            }}
        """
        inactive_style = f"""
            QPushButton {{
                background-color: transparent;
                color: {Styles.COLOR_TEXT_SECONDARY};
                font-size: 11px;
                font-weight: 500;
                border-radius: 4px;
                padding: 2px 8px;
                border: none;
            }}
            QPushButton:hover {{
                color: {Styles.COLOR_TEXT_PRIMARY};
                background-color: rgba(255, 255, 255, 0.05);
            }}
        """
        self.btn_formats.setStyleSheet(
            active_style if self.current_mode == "formats" else inactive_style
        )
        self.btn_pace.setStyleSheet(active_style if self.current_mode == "pace" else inactive_style)
        self.btn_trouble.setStyleSheet(
            active_style if self.current_mode == "trouble" else inactive_style
        )

    def set_mode(self, mode: str):
        self.current_mode = mode
        self._update_segmented_styles()
        if mode == "formats":
            self.stack.setCurrentWidget(self.formats_page)
        elif mode == "pace":
            self.stack.setCurrentWidget(self.pace_page)
        elif mode == "trouble":
            self.stack.setCurrentWidget(self.trouble_page)

    def set_stats(self, stats: dict):
        self.stats = stats or {}
        self._rebuild_all_views()

    def refresh_styles(self):
        super().refresh_styles()
        self._update_segmented_styles()
        self._rebuild_all_views()

    def _clear_layout(self, layout: QVBoxLayout):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
            sub_layout = item.layout()
            if sub_layout:
                self._clear_layout(sub_layout)

    def _rebuild_all_views(self):
        self._clear_layout(self.formats_layout)
        self._clear_layout(self.pace_layout)
        self._clear_layout(self.trouble_layout)

        time_data = self.stats.get("time_stats", {})
        has_clock = time_data.get("has_clock_data", False)
        formats = time_data.get("formats", {})

        # 1. Rebuild Formats Page
        if not formats and not has_clock:
            empty_lbl = QLabel("No time control or clock data available for selected games.")
            empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_lbl.setStyleSheet(f"""
                color: {Styles.COLOR_TEXT_SECONDARY};
                font-size: 12px;
                padding: 40px 10px;
                background: transparent;
            """)
            self.formats_layout.addWidget(empty_lbl)
        else:
            self._build_formats_view(self.formats_layout, formats)

        # 2. Rebuild Move Pace Page
        if not has_clock:
            self._build_no_clock_banner(
                self.pace_layout, "Move pace analysis requires per-move [%clk] tags."
            )
        else:
            self._build_pace_view(self.pace_layout, time_data)

        # 3. Rebuild Time Trouble Page
        if not has_clock:
            self._build_no_clock_banner(
                self.trouble_layout, "Time trouble analytics require per-move [%clk] tags."
            )
        else:
            self._build_trouble_view(self.trouble_layout, time_data)

        # Ensure correct active page is visible
        self.set_mode(self.current_mode)

    def _build_no_clock_banner(self, layout: QVBoxLayout, note: str):
        banner = QFrame()
        banner.setStyleSheet(f"""
            background-color: {Styles.COLOR_SURFACE_LIGHT};
            border: 1px dashed {Styles.COLOR_BORDER};
            border-radius: 8px;
            padding: 24px;
        """)
        b_layout = QVBoxLayout(banner)
        b_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        b_layout.setSpacing(8)

        lbl_title = QLabel("No Clock Timestamps Recorded")
        lbl_title.setStyleSheet(f"""
            color: {Styles.COLOR_TEXT_PRIMARY};
            font-size: 14px;
            font-weight: 700;
        """)
        lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        b_layout.addWidget(lbl_title)

        lbl_desc = QLabel(
            f"{note}\nGames imported from Chess.com or Lichess automatically include clock comments.\n"
            "View the 'Formats' tab for win rates and accuracy by time control."
        )
        lbl_desc.setStyleSheet(f"""
            color: {Styles.COLOR_TEXT_SECONDARY};
            font-size: 12px;
            line-height: 1.4;
        """)
        lbl_desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        b_layout.addWidget(lbl_desc)

        layout.addWidget(banner)

    # ═══════════════════════════════════════════════════════════════
    #  PAGE 1: FORMATS BREAKDOWN
    # ═══════════════════════════════════════════════════════════════
    def _build_formats_view(self, layout: QVBoxLayout, formats: dict[str, dict]):
        preferred_order = ["Bullet", "Blitz", "Rapid", "Classical", "Chess960"]
        sorted_keys = sorted(
            formats.keys(),
            key=lambda k: (
                preferred_order.index(k) if k in preferred_order else 99,
                -formats[k]["games"],
            ),
        )

        for sp in sorted_keys:
            f_data = formats[sp]
            tot = f_data["games"]
            if tot == 0:
                continue

            w = f_data["wins"]
            d = f_data["draws"]
            losses = f_data["losses"]
            wr = f_data["win_rate"]
            acc = f_data["avg_accuracy"]
            avg_t = f_data.get("avg_move_time", 0.0)
            tl = f_data.get("time_losses", 0)

            icon_name, _ = self.FORMAT_META.get(sp, ("fa5s.chess-clock", f"{tot} analyzed games"))

            row = QFrame()
            row.setObjectName("format_row")
            row.setStyleSheet(f"""
                QFrame#format_row {{
                    background-color: {Styles.COLOR_SURFACE_LIGHT};
                    border: 1px solid {Styles.COLOR_BORDER};
                    border-radius: 8px;
                    padding: 8px 12px;
                }}
                QFrame#format_row:hover {{
                    border: 1px solid {Styles.COLOR_ACCENT};
                }}
            """)
            r_layout = QVBoxLayout(row)
            r_layout.setContentsMargins(4, 4, 4, 4)
            r_layout.setSpacing(6)

            # Top Line: Icon + Format Info on Left, Metric Badges on Right
            top_line = QHBoxLayout()
            top_line.setSpacing(10)

            # Icon Tile
            tile = QFrame()
            tile.setFixedSize(32, 32)
            tile.setStyleSheet(f"""
                background-color: {Styles.COLOR_SURFACE};
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 6px;
            """)
            t_layout = QVBoxLayout(tile)
            t_layout.setContentsMargins(0, 0, 0, 0)
            t_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

            try:
                import qtawesome as qta

                ic_lbl = QLabel()
                ic_lbl.setPixmap(
                    qta.icon(icon_name, color=Styles.COLOR_TEXT_SECONDARY).pixmap(16, 16)
                )
                ic_lbl.setStyleSheet("border: none; background: transparent;")
                t_layout.addWidget(ic_lbl)
            except Exception:
                pass
            top_line.addWidget(tile)

            # Format name & record
            info_box = QVBoxLayout()
            info_box.setSpacing(1)
            name_lbl = QLabel(sp)
            name_lbl.setStyleSheet(f"""
                color: {Styles.COLOR_TEXT_PRIMARY};
                font-weight: 700;
                font-size: 13px;
                border: none;
            """)
            info_box.addWidget(name_lbl)

            record_lbl = QLabel(f"{tot} Games • {w}W {d}D {losses}L")
            record_lbl.setStyleSheet(f"""
                color: {Styles.COLOR_TEXT_SECONDARY};
                font-size: 11px;
                border: none;
            """)
            info_box.addWidget(record_lbl)
            top_line.addLayout(info_box)

            top_line.addStretch()

            # Right Badges Strip
            badges_strip = QHBoxLayout()
            badges_strip.setSpacing(6)

            # Win rate badge
            wr_color = Styles.COLOR_RESULT_WIN if wr >= 50.0 else Styles.COLOR_TEXT_PRIMARY
            wr_badge = QLabel(f"{wr:.1f}% Win")
            wr_badge.setStyleSheet(f"""
                background-color: {Styles.COLOR_SURFACE};
                color: {wr_color};
                font-weight: 700;
                font-size: 11px;
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 4px;
                padding: 3px 6px;
            """)
            badges_strip.addWidget(wr_badge)

            # Accuracy badge
            if acc > 0:
                acc_badge = QLabel(f"{acc:.1f}% Acc")
                acc_badge.setStyleSheet(f"""
                    background-color: {Styles.COLOR_SURFACE};
                    color: {Styles.COLOR_TEXT_PRIMARY};
                    font-weight: 600;
                    font-size: 11px;
                    border: 1px solid {Styles.COLOR_BORDER};
                    border-radius: 4px;
                    padding: 3px 6px;
                """)
                badges_strip.addWidget(acc_badge)

            # Move pace badge
            if avg_t > 0:
                pace_badge = QLabel(f"{avg_t:.1f}s / mv")
                pace_badge.setStyleSheet(f"""
                    background-color: {Styles.COLOR_SURFACE};
                    color: {Styles.COLOR_TEXT_PRIMARY};
                    font-weight: 600;
                    font-size: 11px;
                    border: 1px solid {Styles.COLOR_BORDER};
                    border-radius: 4px;
                    padding: 3px 6px;
                """)
                badges_strip.addWidget(pace_badge)

            # Timeouts indicator
            if tl > 0:
                tl_badge = QLabel(f"{tl} Timeouts")
                tl_badge.setStyleSheet(f"""
                    background-color: {Styles.COLOR_SURFACE};
                    color: {Styles.COLOR_BLUNDER};
                    font-weight: 700;
                    font-size: 11px;
                    border: 1px solid {Styles.COLOR_BLUNDER};
                    border-radius: 4px;
                    padding: 3px 6px;
                """)
                badges_strip.addWidget(tl_badge)

            top_line.addLayout(badges_strip)
            r_layout.addLayout(top_line)

            # Bottom Line: Full-width stacked W/D/L bar
            bar_container = QFrame()
            bar_container.setFixedHeight(6)
            bar_container.setStyleSheet(f"""
                background-color: {Styles.COLOR_SURFACE};
                border-radius: 3px;
                border: none;
            """)
            b_layout = QHBoxLayout(bar_container)
            b_layout.setContentsMargins(0, 0, 0, 0)
            b_layout.setSpacing(1)

            w_pct = (w / tot) if tot else 0.0
            d_pct = (d / tot) if tot else 0.0
            l_pct = (losses / tot) if tot else 0.0

            if w > 0:
                w_seg = QFrame()
                w_seg.setStyleSheet(
                    f"background-color: {Styles.COLOR_RESULT_WIN}; border-radius: 3px;"
                )
                b_layout.addWidget(w_seg, stretch=max(1, int(w_pct * 100)))
            if d > 0:
                d_seg = QFrame()
                d_seg.setStyleSheet(
                    f"background-color: {Styles.COLOR_RESULT_DRAW}; border-radius: 3px;"
                )
                b_layout.addWidget(d_seg, stretch=max(1, int(d_pct * 100)))
            if losses > 0:
                l_seg = QFrame()
                l_seg.setStyleSheet(
                    f"background-color: {Styles.COLOR_RESULT_LOSS}; border-radius: 3px;"
                )
                b_layout.addWidget(l_seg, stretch=max(1, int(l_pct * 100)))

            r_layout.addWidget(bar_container)
            layout.addWidget(row)

    # ═══════════════════════════════════════════════════════════════
    #  PAGE 2: MOVE PACE & THINKING TIME
    # ═══════════════════════════════════════════════════════════════
    def _build_pace_view(self, layout: QVBoxLayout, time_data: dict):
        phase_pace = time_data.get("phase_pace", {})
        quality_pace = time_data.get("quality_pace", {})

        # Top Section: 3 Phase Pillars
        pillars_row = QHBoxLayout()
        pillars_row.setSpacing(10)

        phases = [
            ("Opening", "opening", "fa5s.chess-pawn", "Moves 1–15"),
            ("Middlegame", "middlegame", "fa5s.chess-knight", "Moves 16–35"),
            ("Endgame", "endgame", "fa5s.chess-king", "Moves 36+"),
        ]

        for title, key, icon_name, move_range in phases:
            p_info = phase_pace.get(key, {})
            avg_t = p_info.get("avg_time", 0.0)
            m_cnt = p_info.get("moves_count", 0)

            pillar = QFrame()
            pillar.setObjectName("pace_pillar")
            pillar.setStyleSheet(f"""
                QFrame#pace_pillar {{
                    background-color: {Styles.COLOR_SURFACE_LIGHT};
                    border: 1px solid {Styles.COLOR_BORDER};
                    border-radius: 8px;
                    padding: 8px 10px;
                }}
            """)
            p_layout = QVBoxLayout(pillar)
            p_layout.setContentsMargins(6, 4, 6, 4)
            p_layout.setSpacing(3)

            # Header row with icon + title
            h_row = QHBoxLayout()
            h_row.setSpacing(6)
            try:
                import qtawesome as qta

                ic_lbl = QLabel()
                ic_lbl.setPixmap(
                    qta.icon(icon_name, color=Styles.COLOR_TEXT_SECONDARY).pixmap(14, 14)
                )
                ic_lbl.setStyleSheet("border: none; background: transparent;")
                h_row.addWidget(ic_lbl)
            except Exception:
                pass

            title_lbl = QLabel(title)
            title_lbl.setStyleSheet(f"""
                color: {Styles.COLOR_TEXT_PRIMARY};
                font-weight: 700;
                font-size: 13px;
                border: none;
            """)
            h_row.addWidget(title_lbl)
            h_row.addStretch()
            p_layout.addLayout(h_row)

            # Big Pace Stat
            stat_lbl = QLabel(f"{avg_t:.1f}s")
            stat_lbl.setStyleSheet(f"""
                color: {Styles.COLOR_TEXT_PRIMARY};
                font-size: 24px;
                font-weight: 800;
                border: none;
            """)
            p_layout.addWidget(stat_lbl)

            # Footer: move range + move count
            desc_lbl = QLabel(f"{m_cnt} moves • {move_range}")
            desc_lbl.setStyleSheet(f"""
                color: {Styles.COLOR_TEXT_SECONDARY};
                font-size: 10px;
                border: none;
            """)
            p_layout.addWidget(desc_lbl)

            pillars_row.addWidget(pillar)

        layout.addLayout(pillars_row)

        # Bottom Section: Decision Quality Thinking Time
        best_info = quality_pace.get("best", {})
        blunder_info = quality_pace.get("blunder", {})

        best_t = best_info.get("avg_time", 0.0)
        best_m = best_info.get("moves_count", 0)
        blund_t = blunder_info.get("avg_time", 0.0)
        blund_m = blunder_info.get("moves_count", 0)

        dq_card = QFrame()
        dq_card.setObjectName("dq_card")
        dq_card.setStyleSheet(f"""
            QFrame#dq_card {{
                background-color: {Styles.COLOR_SURFACE_LIGHT};
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 8px;
                padding: 10px 12px;
            }}
        """)
        dq_layout = QVBoxLayout(dq_card)
        dq_layout.setContentsMargins(10, 8, 10, 8)
        dq_layout.setSpacing(8)

        dq_title = QLabel("Decision Quality vs Thinking Time")
        dq_title.setStyleSheet(f"""
            color: {Styles.COLOR_TEXT_PRIMARY};
            font-weight: 700;
            font-size: 12px;
            border: none;
        """)
        dq_layout.addWidget(dq_title)

        dq_row = QHBoxLayout()
        dq_row.setSpacing(12)

        # Best Moves Box
        best_box = QFrame()
        best_box.setObjectName("best_box")
        best_box.setStyleSheet(f"""
            QFrame#best_box {{
                background-color: {Styles.COLOR_SURFACE};
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 6px;
            }}
        """)
        b_box_layout = QVBoxLayout(best_box)
        b_box_layout.setContentsMargins(12, 8, 12, 8)
        b_box_layout.setSpacing(3)

        best_header = QLabel("Best & Brilliant Moves")
        best_header.setStyleSheet(f"""
            color: {Styles.COLOR_BEST};
            font-weight: 600;
            font-size: 11px;
            border: none;
            background: transparent;
            padding: 0;
        """)
        b_box_layout.addWidget(best_header)

        best_stat = QLabel(f"{best_t:.1f}s")
        best_stat.setStyleSheet(f"""
            color: {Styles.COLOR_TEXT_PRIMARY};
            font-size: 20px;
            font-weight: 800;
            border: none;
            background: transparent;
            padding: 0;
        """)
        b_box_layout.addWidget(best_stat)

        best_sub = QLabel(f"{best_m} precision moves • avg/move")
        best_sub.setStyleSheet(f"""
            color: {Styles.COLOR_TEXT_MUTED};
            font-size: 10px;
            border: none;
            background: transparent;
            padding: 0;
        """)
        b_box_layout.addWidget(best_sub)
        dq_row.addWidget(best_box)

        # Blunders Box
        blund_box = QFrame()
        blund_box.setObjectName("blund_box")
        blund_box.setStyleSheet(f"""
            QFrame#blund_box {{
                background-color: {Styles.COLOR_SURFACE};
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 6px;
            }}
        """)
        bl_box_layout = QVBoxLayout(blund_box)
        bl_box_layout.setContentsMargins(12, 8, 12, 8)
        bl_box_layout.setSpacing(3)

        blund_header = QLabel("Blunders & Mistakes")
        blund_header.setStyleSheet(f"""
            color: {Styles.COLOR_BLUNDER};
            font-weight: 600;
            font-size: 11px;
            border: none;
            background: transparent;
            padding: 0;
        """)
        bl_box_layout.addWidget(blund_header)

        blund_stat = QLabel(f"{blund_t:.1f}s")
        blund_stat.setStyleSheet(f"""
            color: {Styles.COLOR_TEXT_PRIMARY};
            font-size: 20px;
            font-weight: 800;
            border: none;
            background: transparent;
            padding: 0;
        """)
        bl_box_layout.addWidget(blund_stat)

        blund_sub = QLabel(f"{blund_m} tactical errors • avg/move")
        blund_sub.setStyleSheet(f"""
            color: {Styles.COLOR_TEXT_MUTED};
            font-size: 10px;
            border: none;
            background: transparent;
            padding: 0;
        """)
        bl_box_layout.addWidget(blund_sub)
        dq_row.addWidget(blund_box)

        dq_layout.addLayout(dq_row)

        # Insight Line
        if best_t > 0 and blund_t > 0:
            ratio = blund_t / best_t
            if ratio > 1.2:
                insight_text = f"You spend {ratio:.1f}x longer calculating on blunder positions, indicating calculation traps in tricky positions."
            elif ratio < 0.8:
                inv_ratio = 1.0 / ratio
                insight_text = f"You play blunders {inv_ratio:.1f}x faster than your best moves, suggesting premature decisions or impulsive play."
            else:
                insight_text = (
                    "Your thinking time is evenly distributed between best moves and errors."
                )

            insight_lbl = QLabel(insight_text)
            insight_lbl.setStyleSheet(f"""
                color: {Styles.COLOR_TEXT_SECONDARY};
                font-size: 11px;
                border-top: 1px solid {Styles.COLOR_BORDER};
                padding-top: 6px;
            """)
            insight_lbl.setWordWrap(True)
            dq_layout.addWidget(insight_lbl)

        layout.addWidget(dq_card)

    # ═══════════════════════════════════════════════════════════════
    #  PAGE 3: TIME TROUBLE & PANIC INDEX
    # ═══════════════════════════════════════════════════════════════
    def _build_trouble_view(self, layout: QVBoxLayout, time_data: dict):
        trouble = time_data.get("time_trouble", {})
        n_moves = trouble.get("normal_moves", 0)
        n_blund = trouble.get("normal_blunders", 0)
        n_pct = trouble.get("normal_blunder_pct", 0.0)

        t_moves = trouble.get("trouble_moves", 0)
        t_blund = trouble.get("trouble_blunders", 0)
        t_pct = trouble.get("trouble_blunder_pct", 0.0)

        panic_mult = trouble.get("panic_multiplier", 1.0)
        timeouts = trouble.get("total_time_losses", 0)

        # 1. Comparative Cards (Normal Clock vs Time Trouble)
        comp_row = QHBoxLayout()
        comp_row.setSpacing(10)

        # Normal Clock Card
        nc_card = QFrame()
        nc_card.setObjectName("nc_card")
        nc_card.setStyleSheet(f"""
            QFrame#nc_card {{
                background-color: {Styles.COLOR_SURFACE_LIGHT};
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 8px;
                padding: 10px;
            }}
        """)
        nc_layout = QVBoxLayout(nc_card)
        nc_layout.setContentsMargins(6, 4, 6, 4)
        nc_layout.setSpacing(4)

        nc_top = QHBoxLayout()
        try:
            import qtawesome as qta

            ic_nc = QLabel()
            ic_nc.setPixmap(
                qta.icon("fa5s.shield-alt", color=Styles.COLOR_RESULT_WIN).pixmap(14, 14)
            )
            ic_nc.setStyleSheet("border: none; background: transparent;")
            nc_top.addWidget(ic_nc)
        except Exception:
            pass
        nc_title = QLabel("Normal Clock")
        nc_title.setStyleSheet(f"""
            color: {Styles.COLOR_TEXT_PRIMARY};
            font-weight: 700;
            font-size: 12px;
            border: none;
        """)
        nc_top.addWidget(nc_title)
        nc_top.addStretch()

        nc_thresh = QLabel(">15s Bullet, >30s Blitz")
        nc_thresh.setStyleSheet(f"""
            color: {Styles.COLOR_TEXT_MUTED};
            font-size: 9px;
            border: none;
        """)
        nc_top.addWidget(nc_thresh)
        nc_layout.addLayout(nc_top)

        nc_stat = QLabel(f"{n_pct:.1f}%")
        nc_stat.setStyleSheet(f"""
            color: {Styles.COLOR_TEXT_PRIMARY};
            font-size: 24px;
            font-weight: 800;
            border: none;
        """)
        nc_layout.addWidget(nc_stat)

        nc_desc = QLabel(f"{n_blund} errors across {n_moves} moves")
        nc_desc.setStyleSheet(f"""
            color: {Styles.COLOR_TEXT_SECONDARY};
            font-size: 10px;
            border: none;
        """)
        nc_layout.addWidget(nc_desc)
        comp_row.addWidget(nc_card)

        # Time Trouble Card
        tt_card = QFrame()
        tt_card.setObjectName("tt_card")
        tt_border = Styles.COLOR_BLUNDER if panic_mult > 1.2 else Styles.COLOR_BORDER
        tt_card.setStyleSheet(f"""
            QFrame#tt_card {{
                background-color: {Styles.COLOR_SURFACE_LIGHT};
                border: 1px solid {tt_border};
                border-radius: 8px;
                padding: 10px;
            }}
        """)
        tt_layout = QVBoxLayout(tt_card)
        tt_layout.setContentsMargins(6, 4, 6, 4)
        tt_layout.setSpacing(4)

        tt_top = QHBoxLayout()
        try:
            import qtawesome as qta

            ic_tt = QLabel()
            ic_tt.setPixmap(
                qta.icon("fa5s.tachometer-alt", color=Styles.COLOR_BLUNDER).pixmap(14, 14)
            )
            ic_tt.setStyleSheet("border: none; background: transparent;")
            tt_top.addWidget(ic_tt)
        except Exception:
            pass
        tt_title = QLabel("Time Trouble")
        tt_title.setStyleSheet(f"""
            color: {Styles.COLOR_TEXT_PRIMARY};
            font-weight: 700;
            font-size: 12px;
            border: none;
        """)
        tt_top.addWidget(tt_title)
        tt_top.addStretch()

        tt_thresh = QLabel("≤15s Bullet, ≤30s Blitz")
        tt_thresh.setStyleSheet(f"""
            color: {Styles.COLOR_TEXT_MUTED};
            font-size: 9px;
            border: none;
        """)
        tt_top.addWidget(tt_thresh)
        tt_layout.addLayout(tt_top)

        tt_color = Styles.COLOR_BLUNDER if panic_mult > 1.2 else Styles.COLOR_BEST
        tt_stat = QLabel(f"{t_pct:.1f}%")
        tt_stat.setStyleSheet(f"""
            color: {tt_color};
            font-size: 24px;
            font-weight: 800;
            border: none;
        """)
        tt_layout.addWidget(tt_stat)

        tt_desc = QLabel(f"{t_blund} errors across {t_moves} scramble moves")
        tt_desc.setStyleSheet(f"""
            color: {Styles.COLOR_TEXT_SECONDARY};
            font-size: 10px;
            border: none;
        """)
        tt_layout.addWidget(tt_desc)
        comp_row.addWidget(tt_card)

        layout.addLayout(comp_row)

        # 2. Panic Index & Timeouts Banner
        banner = QFrame()
        banner.setStyleSheet(f"""
            background-color: {Styles.COLOR_SURFACE_LIGHT};
            border: 1px solid {Styles.COLOR_BORDER};
            border-radius: 8px;
            padding: 10px 12px;
        """)
        b_layout = QHBoxLayout(banner)
        b_layout.setContentsMargins(10, 8, 10, 8)
        b_layout.setSpacing(12)

        # Left Info
        b_info = QVBoxLayout()
        b_info.setSpacing(2)

        if math.isinf(panic_mult):
            banner_title = "High Blunder Rate Under Time Pressure"
            banner_desc = (
                f"Your tactical errors increase under low clock ({t_pct:.1f}% vs {n_pct:.1f}%).\n"
                "Focus on pace in the opening and middlegame to preserve time reserves."
            )
            title_color = Styles.COLOR_BLUNDER
        elif panic_mult > 1.2:
            banner_title = f"{panic_mult:.1f}x Blunder Rate Under Time Pressure"
            banner_desc = (
                f"Your tactical errors increase under low clock ({t_pct:.1f}% vs {n_pct:.1f}%).\n"
                "Focus on pace in the opening and middlegame to preserve time reserves."
            )
            title_color = Styles.COLOR_BLUNDER
        elif panic_mult <= 0.8 and t_moves > 0:
            banner_title = "Disciplined in Time Scrambles"
            banner_desc = (
                f"Your error rate remains lower in time trouble ({t_pct:.1f}%) than in regular play ({n_pct:.1f}%).\n"
                "You rely successfully on fast tactical intuition when pressed for time."
            )
            title_color = Styles.COLOR_RESULT_WIN
        else:
            banner_title = "Stable Under Clock Pressure"
            banner_desc = "Your error rate remains consistent regardless of clock situation. You maintain good stability."
            title_color = Styles.COLOR_TEXT_PRIMARY

        lbl_btitle = QLabel(banner_title)
        lbl_btitle.setStyleSheet(f"""
            color: {title_color};
            font-weight: 700;
            font-size: 12px;
            border: none;
        """)
        b_info.addWidget(lbl_btitle)

        lbl_bdesc = QLabel(banner_desc)
        lbl_bdesc.setStyleSheet(f"""
            color: {Styles.COLOR_TEXT_SECONDARY};
            font-size: 11px;
            border: none;
        """)
        lbl_bdesc.setWordWrap(True)
        b_info.addWidget(lbl_bdesc)
        b_layout.addLayout(b_info, stretch=1)

        # Right Pill: Timeouts
        to_pill = QFrame()
        to_pill.setObjectName("to_pill")
        to_pill.setStyleSheet(f"""
            QFrame#to_pill {{
                background-color: {Styles.COLOR_SURFACE};
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 6px;
            }}
        """)
        to_layout = QVBoxLayout(to_pill)
        to_layout.setContentsMargins(12, 6, 12, 6)
        to_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        to_num = QLabel(str(timeouts))
        to_color = Styles.COLOR_BLUNDER if timeouts > 0 else Styles.COLOR_TEXT_PRIMARY
        to_num.setStyleSheet(f"""
            color: {to_color};
            font-size: 16px;
            font-weight: 800;
            border: none;
        """)
        to_num.setAlignment(Qt.AlignmentFlag.AlignCenter)
        to_layout.addWidget(to_num)

        to_lbl = QLabel("Timeouts")
        to_lbl.setStyleSheet(f"""
            color: {Styles.COLOR_TEXT_MUTED};
            font-size: 9px;
            font-weight: 600;
            border: none;
        """)
        to_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        to_layout.addWidget(to_lbl)

        b_layout.addWidget(to_pill)
        layout.addWidget(banner)
