"""
Openings Mastery Card.
Displays top openings with interactive frequency vs win rate sorting,
ECO badges, sub-variation lines, and proportional win/draw/loss stacked bars.
Automatically harmonizes with the global dashboard color filter.
"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.gui.styles import Styles
from src.gui.views.metrics.base_card import MetricCard


class OpeningsListCard(MetricCard):
    """
    Enhanced Openings Mastery Card.
    Features:
    - [Most Played | Win Rate] Sorting segmented control in card header.
    - Dynamically adapts to global toolbar color filter (All, White, or Black).
    - ECO badge and opening variation lines.
    - Proportional stacked Win/Draw/Loss distribution bars.
    - Average move accuracy per opening.
    """

    drill_down_requested = pyqtSignal(str, str)  # (category, subcategory)
    PAGE_SIZE = 4

    def __init__(self, parent=None):
        self.stats = {}
        self.current_sort = "played"  # 'played', 'winrate'
        self.current_page = 0
        self.content_widget = None

        # Header Action Widget: Sort Control [Most Played | Win Rate]
        self.sort_control = QFrame()
        self.sort_control.setObjectName("opening_sort_control")
        self.sort_control.setFixedHeight(24)
        self.sort_control.setStyleSheet(f"""
            QFrame#opening_sort_control {{
                background-color: {Styles.COLOR_SURFACE_LIGHT};
                border-radius: 4px;
                border: none;
            }}
        """)
        sort_layout = QHBoxLayout(self.sort_control)
        sort_layout.setContentsMargins(2, 2, 2, 2)
        sort_layout.setSpacing(2)

        self.btn_sort_played = QPushButton("Most Played")
        self.btn_sort_played.setFixedHeight(20)
        self.btn_sort_played.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_sort_played.clicked.connect(lambda: self.set_sort("played"))

        self.btn_sort_winrate = QPushButton("Win Rate")
        self.btn_sort_winrate.setFixedHeight(20)
        self.btn_sort_winrate.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_sort_winrate.clicked.connect(lambda: self.set_sort("winrate"))

        sort_layout.addWidget(self.btn_sort_played)
        sort_layout.addWidget(self.btn_sort_winrate)

        self._update_sort_styles()

        super().__init__(
            "Opening Repertoire",
            parent=parent,
            min_height=380,
            action_widget=self.sort_control,
        )

    def _update_sort_styles(self):
        active_sort_style = f"""
            QPushButton {{
                background-color: {Styles.COLOR_SURFACE_CARD};
                color: {Styles.COLOR_TEXT_PRIMARY};
                font-weight: 600;
                font-size: 10px;
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 3px;
                padding: 1px 7px;
            }}
        """
        inactive_sort_style = f"""
            QPushButton {{
                background-color: transparent;
                color: {Styles.COLOR_TEXT_SECONDARY};
                font-weight: 500;
                font-size: 10px;
                border: 1px solid transparent;
                border-radius: 3px;
                padding: 1px 7px;
            }}
            QPushButton:hover {{
                color: {Styles.COLOR_TEXT_PRIMARY};
            }}
        """
        self.btn_sort_played.setStyleSheet(
            active_sort_style if self.current_sort == "played" else inactive_sort_style
        )
        self.btn_sort_winrate.setStyleSheet(
            active_sort_style if self.current_sort == "winrate" else inactive_sort_style
        )

    def set_sort(self, sort_by: str):
        if self.current_sort == sort_by:
            return
        self.current_sort = sort_by
        self.current_page = 0
        self._update_sort_styles()
        self._render_view()

    def set_stats(self, stats: dict):
        self.stats = stats or {}
        self.current_page = 0

        # Update card title dynamically based on active color filter
        active_color = self.stats.get("filter_applied", {}).get("color", "All Colors")
        if hasattr(self, "lbl_title"):
            if active_color == "White":
                self.lbl_title.setText("White Repertoire")
            elif active_color == "Black":
                self.lbl_title.setText("Black Defenses")
            else:
                self.lbl_title.setText("Opening Repertoire")

        self._render_view()

    def _get_openings_list(self) -> list[dict]:
        detailed = self.stats.get("detailed_openings", {})
        if detailed:
            items = list(detailed.values())
        else:
            # Fallback to legacy openings dict
            legacy_openings = self.stats.get("openings", {})
            legacy_wins = self.stats.get("opening_wins", {})
            items = []
            for name, count in legacy_openings.items():
                w = legacy_wins.get(name, 0)
                wr = (w / count * 100) if count > 0 else 0.0
                items.append(
                    {
                        "name": name,
                        "eco": "",
                        "total": count,
                        "wins": w,
                        "draws": 0,
                        "losses": max(0, count - w),
                        "win_rate": wr,
                        "variations": [],
                        "avg_acc": 0.0,
                    }
                )

        # Sort items
        if self.current_sort == "winrate":
            items.sort(key=lambda x: (x.get("win_rate", 0.0), x.get("total", 0)), reverse=True)
        else:
            items.sort(key=lambda x: (x.get("total", 0), x.get("win_rate", 0.0)), reverse=True)

        return items

    def _render_view(self):
        if self.content_widget:
            self.card_layout.removeWidget(self.content_widget)
            self.content_widget.setParent(None)
            self.content_widget.deleteLater()
            self.content_widget = None

        self.content_widget = QWidget()
        self.content_widget.setStyleSheet("background: transparent;")
        main_vbox = QVBoxLayout(self.content_widget)
        main_vbox.setContentsMargins(0, 0, 0, 0)
        main_vbox.setSpacing(8)

        openings_list = self._get_openings_list()
        active_color = self.stats.get("filter_applied", {}).get("color", "All Colors")

        # 1. Sub-toolbar: Opening count summary
        sub_bar = QHBoxLayout()
        sub_bar.setContentsMargins(0, 0, 0, 2)

        total_openings = len(openings_list)
        total_games = sum(o.get("total", 0) for o in openings_list)

        if total_openings > 0:
            if active_color == "White":
                summary_text = f"{total_openings} White openings ({total_games} games)"
            elif active_color == "Black":
                summary_text = f"{total_openings} Black defenses ({total_games} games)"
            else:
                summary_text = f"{total_openings} openings ({total_games} games)"
        else:
            summary_text = f"No openings found for {active_color.lower()}"

        summary_lbl = QLabel(summary_text)
        summary_lbl.setStyleSheet(f"""
            color: {Styles.COLOR_TEXT_SECONDARY};
            font-size: 11px;
            font-weight: 500;
            border: none;
            background: transparent;
        """)
        sub_bar.addWidget(summary_lbl)
        sub_bar.addStretch()
        main_vbox.addLayout(sub_bar)

        if not openings_list:
            empty_lbl = QLabel("No openings data found for the selected filters.")
            empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_lbl.setStyleSheet(f"""
                color: {Styles.COLOR_TEXT_SECONDARY};
                font-size: 12px;
                padding: 40px 10px;
                background: transparent;
            """)
            main_vbox.addWidget(empty_lbl, stretch=1)
            self.set_content(self.content_widget)
            return

        # 2. Paginated List of Openings
        total_openings = len(openings_list)
        total_pages = max(1, (total_openings + self.PAGE_SIZE - 1) // self.PAGE_SIZE)
        self.current_page = max(0, min(self.current_page, total_pages - 1))

        start_idx = self.current_page * self.PAGE_SIZE
        end_idx = min(start_idx + self.PAGE_SIZE, total_openings)
        page_items = openings_list[start_idx:end_idx]

        items_container = QWidget()
        items_container.setStyleSheet("background: transparent;")
        items_vbox = QVBoxLayout(items_container)
        items_vbox.setContentsMargins(0, 0, 0, 0)
        items_vbox.setSpacing(8)

        show_color_tag = active_color not in ("White", "Black")

        for item in page_items:
            row_card = self._create_opening_row(item, show_color_tag=show_color_tag)
            items_vbox.addWidget(row_card)

        items_vbox.addStretch()
        main_vbox.addWidget(items_container, stretch=1)

        # 3. Pagination Bar
        if total_pages > 1:
            pagination_bar = QHBoxLayout()
            pagination_bar.setContentsMargins(4, 4, 4, 0)
            pagination_bar.setSpacing(10)

            self.btn_prev_page = QPushButton("◀ Prev")
            self.btn_prev_page.setFixedHeight(26)
            self.btn_prev_page.setCursor(Qt.CursorShape.PointingHandCursor)
            self.btn_prev_page.setEnabled(self.current_page > 0)
            self.btn_prev_page.clicked.connect(self._go_prev_page)

            self.lbl_page_info = QLabel(f"Page {self.current_page + 1} of {total_pages}")
            self.lbl_page_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.lbl_page_info.setStyleSheet(f"""
                color: {Styles.COLOR_TEXT_SECONDARY};
                font-size: 11px;
                font-weight: 500;
                background: transparent;
            """)

            self.btn_next_page = QPushButton("Next ▶")
            self.btn_next_page.setFixedHeight(26)
            self.btn_next_page.setCursor(Qt.CursorShape.PointingHandCursor)
            self.btn_next_page.setEnabled(self.current_page < total_pages - 1)
            self.btn_next_page.clicked.connect(self._go_next_page)

            btn_style = f"""
                QPushButton {{
                    background-color: {Styles.COLOR_SURFACE_LIGHT};
                    color: {Styles.COLOR_TEXT_PRIMARY};
                    border: 1px solid {Styles.COLOR_BORDER};
                    border-radius: 4px;
                    padding: 2px 10px;
                    font-size: 11px;
                    font-weight: 600;
                }}
                QPushButton:hover:enabled {{
                    background-color: {Styles.COLOR_SURFACE};
                    border-color: {Styles.COLOR_BORDER_LIGHT};
                }}
                QPushButton:disabled {{
                    color: {Styles.COLOR_TEXT_MUTED};
                    background-color: transparent;
                    border-color: transparent;
                }}
            """
            self.btn_prev_page.setStyleSheet(btn_style)
            self.btn_next_page.setStyleSheet(btn_style)

            pagination_bar.addWidget(self.btn_prev_page)
            pagination_bar.addStretch()
            pagination_bar.addWidget(self.lbl_page_info)
            pagination_bar.addStretch()
            pagination_bar.addWidget(self.btn_next_page)

            main_vbox.addLayout(pagination_bar)

        self.set_content(self.content_widget)

    def _go_prev_page(self):
        if self.current_page > 0:
            self.current_page -= 1
            self._render_view()

    def _go_next_page(self):
        openings_list = self._get_openings_list()
        total_pages = max(1, (len(openings_list) + self.PAGE_SIZE - 1) // self.PAGE_SIZE)
        if self.current_page < total_pages - 1:
            self.current_page += 1
            self._render_view()

    def _on_opening_clicked(self, event, opening_name: str) -> None:
        if event is None or event.button() == Qt.MouseButton.LeftButton:
            self.drill_down_requested.emit("openings", opening_name)

    def _create_opening_row(self, item: dict, show_color_tag: bool = False) -> QFrame:
        """Creates an individual opening card row with stacked W/D/L bar."""
        name = item.get("name", "Unknown Opening")
        eco = item.get("eco", "")
        total = item.get("total", 1)
        wins = item.get("wins", 0)
        draws = item.get("draws", 0)
        losses = item.get("losses", max(0, total - wins - draws))
        win_rate = item.get("win_rate", 0.0)
        avg_acc = item.get("avg_acc", 0.0)
        variations = item.get("variations", [])
        as_white = item.get("as_white", 0)
        as_black = item.get("as_black", 0)

        # Color rating for win rate
        if win_rate >= 60.0:
            wr_color = Styles.COLOR_BEST
        elif win_rate >= 45.0:
            wr_color = Styles.COLOR_TEXT_PRIMARY
        else:
            wr_color = Styles.COLOR_BLUNDER

        card = QFrame()
        card.setCursor(Qt.CursorShape.PointingHandCursor)
        card.setToolTip(f"Click to inspect games played in {name}")
        card.mousePressEvent = lambda e, op_name=name: self._on_opening_clicked(e, op_name)
        card.setStyleSheet(f"""
            QFrame#opening_item {{
                background-color: {Styles.COLOR_SURFACE_LIGHT};
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 8px;
            }}
            QFrame#opening_item:hover {{
                border: 1px solid {Styles.COLOR_ACCENT};
            }}
        """)
        card.setObjectName("opening_item")

        c_layout = QVBoxLayout(card)
        c_layout.setContentsMargins(12, 10, 12, 10)
        c_layout.setSpacing(6)

        # Line 1: [ECO] Opening Name [Side]  --  Win Rate % (Games)
        line1 = QHBoxLayout()
        line1.setContentsMargins(0, 0, 0, 0)
        line1.setSpacing(8)

        # ECO Badge
        if eco:
            eco_badge = QLabel(eco)
            eco_badge.setStyleSheet(f"""
                QLabel {{
                    background-color: {Styles.COLOR_SURFACE};
                    color: {Styles.COLOR_TEXT_PRIMARY};
                    font-size: 11px;
                    font-weight: 700;
                    border: 1px solid {Styles.COLOR_BORDER};
                    border-radius: 4px;
                    padding: 1px 5px;
                }}
            """)
            line1.addWidget(eco_badge)

        name_lbl = QLabel(name)
        name_lbl.setCursor(Qt.CursorShape.PointingHandCursor)
        name_lbl.setToolTip(f"Click to inspect games played in {name}")
        name_lbl.setStyleSheet(f"""
            color: {Styles.COLOR_TEXT_PRIMARY};
            font-size: 13px;
            font-weight: 700;
            border: none;
            background: transparent;
        """)
        line1.addWidget(name_lbl)

        # Subtle Side Badge (if in All view)
        if show_color_tag:
            side_text = (
                "White"
                if as_white > 0 and as_black == 0
                else ("Black" if as_black > 0 and as_white == 0 else "Both")
            )
            side_badge = QLabel(side_text)
            side_badge.setStyleSheet(f"""
                QLabel {{
                    color: {Styles.COLOR_TEXT_MUTED};
                    font-size: 10px;
                    font-weight: 600;
                    background-color: {Styles.COLOR_SURFACE};
                    border-radius: 3px;
                    padding: 0px 4px;
                }}
            """)
            line1.addWidget(side_badge)

        line1.addStretch()

        # Win Rate text
        wr_lbl = QLabel(f"{win_rate:.0f}% Win Rate")
        wr_lbl.setStyleSheet(f"""
            color: {wr_color};
            font-size: 12px;
            font-weight: 700;
            border: none;
            background: transparent;
        """)
        line1.addWidget(wr_lbl)

        games_lbl = QLabel(f"({total} {'game' if total == 1 else 'games'})")
        games_lbl.setStyleSheet(f"""
            color: {Styles.COLOR_TEXT_SECONDARY};
            font-size: 11px;
            font-weight: 500;
            border: none;
            background: transparent;
        """)
        line1.addWidget(games_lbl)

        c_layout.addLayout(line1)

        # Line 2: Sub-variations (if present)
        if variations:
            var_text = " • ".join(variations[:2])
            if len(variations) > 2:
                var_text += f" +{len(variations) - 2} more"
            var_lbl = QLabel(var_text)
            var_lbl.setToolTip(" • ".join(variations))
            var_lbl.setStyleSheet(f"""
                color: {Styles.COLOR_TEXT_MUTED};
                font-size: 11px;
                border: none;
                background: transparent;
            """)
            c_layout.addWidget(var_lbl)

        # Line 3: Proportional Stacked Bar [ Green Wins | Gray Draws | Red Losses ]
        bar_container = QFrame()
        bar_container.setFixedHeight(6)
        bar_container.setStyleSheet(f"""
            QFrame {{
                background-color: {Styles.COLOR_SURFACE};
                border-radius: 3px;
                border: none;
            }}
        """)
        bar_layout = QHBoxLayout(bar_container)
        bar_layout.setContentsMargins(0, 0, 0, 0)
        bar_layout.setSpacing(1)

        if total > 0:
            if wins > 0:
                w_seg = QFrame()
                w_seg.setStyleSheet(f"""
                    background-color: {Styles.COLOR_BEST};
                    border-radius: 2px;
                    border: none;
                """)
                w_seg.setToolTip(f"Wins: {wins} ({wins / total * 100:.0f}%)")
                bar_layout.addWidget(w_seg, stretch=max(1, int(wins * 100 / total)))

            if draws > 0:
                d_seg = QFrame()
                d_seg.setStyleSheet(f"""
                    background-color: {Styles.COLOR_BORDER};
                    border-radius: 2px;
                    border: none;
                """)
                d_seg.setToolTip(f"Draws: {draws} ({draws / total * 100:.0f}%)")
                bar_layout.addWidget(d_seg, stretch=max(1, int(draws * 100 / total)))

            if losses > 0:
                l_seg = QFrame()
                l_seg.setStyleSheet(f"""
                    background-color: {Styles.COLOR_BLUNDER};
                    border-radius: 2px;
                    border: none;
                """)
                l_seg.setToolTip(f"Losses: {losses} ({losses / total * 100:.0f}%)")
                bar_layout.addWidget(l_seg, stretch=max(1, int(losses * 100 / total)))
        else:
            empty_seg = QFrame()
            empty_seg.setStyleSheet("background: transparent; border: none;")
            bar_layout.addWidget(empty_seg)

        c_layout.addWidget(bar_container)

        # Line 4: Breakdown Strip: "XW • YD • ZL" and "Avg Acc: XX.X%"
        line4 = QHBoxLayout()
        line4.setContentsMargins(0, 0, 0, 0)

        record_parts = []
        if wins > 0:
            record_parts.append(f"{wins}W")
        if draws > 0:
            record_parts.append(f"{draws}D")
        if losses > 0:
            record_parts.append(f"{losses}L")
        record_str = " · ".join(record_parts) if record_parts else "0G"

        rec_lbl = QLabel(record_str)
        rec_lbl.setStyleSheet(f"""
            color: {Styles.COLOR_TEXT_SECONDARY};
            font-size: 11px;
            font-weight: 600;
            border: none;
            background: transparent;
        """)
        line4.addWidget(rec_lbl)

        if avg_acc > 0:
            dot_lbl = QLabel("•")
            dot_lbl.setStyleSheet(f"color: {Styles.COLOR_TEXT_MUTED}; font-size: 10px;")
            line4.addWidget(dot_lbl)

            acc_lbl = QLabel(f"{avg_acc:.1f}% avg accuracy")
            acc_lbl.setStyleSheet(f"""
                color: {Styles.COLOR_TEXT_SECONDARY};
                font-size: 11px;
                font-weight: 500;
                border: none;
                background: transparent;
            """)
            line4.addWidget(acc_lbl)

        line4.addStretch()
        c_layout.addLayout(line4)

        return card

    def refresh_styles(self):
        super().refresh_styles()
        if hasattr(self, "sort_control"):
            self.sort_control.setStyleSheet(f"""
                QFrame#opening_sort_control {{
                    background-color: {Styles.COLOR_SURFACE_LIGHT};
                    border-radius: 4px;
                    border: none;
                }}
            """)
            self._update_sort_styles()
        if self.stats:
            self._render_view()
