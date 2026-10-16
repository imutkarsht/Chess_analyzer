import os

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.gui.metrics.charts import create_donut_figure, fig_to_canvas
from src.gui.styles import Styles
from src.gui.utils.gui_utils import resolve_asset
from src.gui.views.metrics.base_card import MetricCard


class EndingDistributionCard(MetricCard):
    def __init__(self, parent=None):
        self.current_mode = "all"  # "all", "won", "lost", "drawn"
        self.stats = {}
        self.content_widget = None

        self.segmented_control = self._build_segmented_control()
        super().__init__(
            "Ending Distribution",
            parent=parent,
            max_height=310,
            action_widget=self.segmented_control,
        )

    def _build_segmented_control(self) -> QFrame:
        container = QFrame()
        container.setObjectName("ending_segmented")
        container.setStyleSheet(f"""
            QFrame#ending_segmented {{
                background-color: {Styles.COLOR_SURFACE_LIGHT};
                border-radius: 6px;
                border: none;
            }}
        """)
        layout = QHBoxLayout(container)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)

        self.btn_all = QPushButton("All")
        self.btn_won = QPushButton("Won")
        self.btn_lost = QPushButton("Lost")
        self.btn_drawn = QPushButton("Drawn")

        for btn, mode in [
            (self.btn_all, "all"),
            (self.btn_won, "won"),
            (self.btn_lost, "lost"),
            (self.btn_drawn, "drawn"),
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
            }}
        """
        self.btn_all.setStyleSheet(active_style if self.current_mode == "all" else inactive_style)
        self.btn_won.setStyleSheet(active_style if self.current_mode == "won" else inactive_style)
        self.btn_lost.setStyleSheet(active_style if self.current_mode == "lost" else inactive_style)
        self.btn_drawn.setStyleSheet(
            active_style if self.current_mode == "drawn" else inactive_style
        )

    def set_mode(self, mode: str):
        if self.current_mode == mode:
            return
        self.current_mode = mode
        self._update_segmented_styles()
        self._render_view()

    def set_stats(self, stats: dict):
        self.stats = stats or {}
        self._render_view()

    def _render_view(self):
        if self.content_widget:
            self.card_layout.removeWidget(self.content_widget)
            self.content_widget.deleteLater()
            self.content_widget = None

        if self.current_mode == "won":
            counts = self.stats.get("win_term_counts", {})
            keys = ["Checkmate", "Resignation", "Time", "Abandon"]
            center_suffix = "Won"
        elif self.current_mode == "lost":
            counts = self.stats.get("loss_term_counts", {})
            keys = ["Checkmate", "Resignation", "Time", "Abandon"]
            center_suffix = "Lost"
        elif self.current_mode == "drawn":
            counts = self.stats.get("draw_term_counts", {})
            keys = [
                "3-Fold Repetition",
                "Agreement",
                "Stalemate",
                "Insufficient vs Timeout",
                "Insufficient Material",
                "50-Move Rule",
            ]
            center_suffix = "Drawn"
        else:
            counts = self.stats.get("term_counts", {})
            keys = ["Checkmate", "Resignation", "Time", "Draw", "Abandon"]
            center_suffix = ""

        type_colors = {
            "Checkmate": Styles.COLOR_BEST,
            "Resignation": Styles.COLOR_ACCENT,
            "Time": "#e67e22",
            "Abandon": Styles.COLOR_BLUNDER,
            "Draw": "#888888",
            "3-Fold Repetition": "#3498db",
            "Agreement": "#1abc9c",
            "Stalemate": "#9b59b6",
            "Insufficient vs Timeout": "#e67e22",
            "Insufficient Material": "#f1c40f",
            "50-Move Rule": "#95a5a6",
        }

        icon_map = {
            "Checkmate": "checkmate.svg",
            "Resignation": "resign.svg",
            "Time": "timeout.svg",
            "Abandon": "resign.svg",
            "Draw": "draw_black.svg",
            "Insufficient vs Timeout": "timeout.svg",
        }

        qta_icon_map = {
            "3-Fold Repetition": "fa6s.repeat",
            "Agreement": "fa6s.handshake",
            "Stalemate": "fa6s.chess-king",
            "Insufficient Material": "fa6s.scale-balanced",
            "50-Move Rule": "fa6s.flag",
        }

        labels, sizes, colors = [], [], []
        for k in keys:
            v = counts.get(k, 0)
            if v > 0:
                labels.append(k)
                sizes.append(v)
                colors.append(type_colors.get(k, "#888888"))

        total_endings = sum(sizes)
        center_text = f"{total_endings}\n{center_suffix}".strip() if total_endings > 0 else ""

        fig = create_donut_figure(
            sizes,
            colors,
            center_text,
            figsize=(3.5, 3.0),
            text_color=Styles.COLOR_TEXT_PRIMARY,
        )
        canvas = fig_to_canvas(fig)

        self.content_widget = QWidget()
        self.content_widget.setStyleSheet("background: transparent;")
        main_vbox = QVBoxLayout(self.content_widget)
        main_vbox.setContentsMargins(0, 0, 0, 0)
        main_vbox.setSpacing(6)

        chart_row = QHBoxLayout()
        chart_row.setContentsMargins(0, 0, 0, 0)
        chart_row.addWidget(canvas, stretch=3)

        # Legend Sidebar
        legend_widget = QWidget()
        legend_widget.setStyleSheet("background: transparent;")
        legend_layout = QVBoxLayout(legend_widget)
        legend_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        legend_layout.setSpacing(6)

        if total_endings == 0:
            mode_label = (
                f"No {self.current_mode} games recorded"
                if self.current_mode != "all"
                else "No games recorded"
            )
            empty_lbl = QLabel(mode_label)
            empty_lbl.setStyleSheet(
                f"color: {Styles.COLOR_TEXT_SECONDARY}; font-size: 12px; font-style: italic; border: none; background: transparent;"
            )
            empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            legend_layout.addWidget(empty_lbl)
        else:
            for k in keys:
                v = counts.get(k, 0)
                if v == 0:
                    continue

                row = QHBoxLayout()
                row.setSpacing(8)

                icon_file = icon_map.get(k)
                icon_path = resolve_asset(icon_file) if icon_file else None
                pixmap = None

                if icon_path and os.path.exists(icon_path):
                    pm = QPixmap(icon_path)
                    if not pm.isNull():
                        pixmap = pm.scaled(
                            18,
                            18,
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation,
                        )
                elif k in qta_icon_map:
                    try:
                        import qtawesome as qta

                        pixmap = qta.icon(
                            qta_icon_map[k], color=type_colors.get(k, "#ffffff")
                        ).pixmap(16, 16)
                    except Exception:
                        pixmap = None

                if pixmap and not pixmap.isNull():
                    lbl_icon = QLabel()
                    lbl_icon.setPixmap(pixmap)
                    lbl_icon.setStyleSheet("border: none; background: transparent;")
                    row.addWidget(lbl_icon)
                else:
                    dot = QLabel("●")
                    dot.setStyleSheet(
                        f"color: {type_colors.get(k, '#888888')}; font-size: 14px; border: none; background: transparent;"
                    )
                    row.addWidget(dot)

                lbl_name = QLabel(k)
                lbl_name.setStyleSheet(
                    f"color: {Styles.COLOR_TEXT_SECONDARY}; font-size: 12px; font-weight: 500; border: none; background: transparent;"
                )
                row.addWidget(lbl_name)

                row.addStretch()

                pct = (v / total_endings * 100) if total_endings > 0 else 0
                lbl_val = QLabel(f"{v} ({pct:.0f}%)")
                lbl_val.setStyleSheet(
                    f"color: {type_colors.get(k, '#888888')}; font-size: 12px; font-weight: bold; border: none; background: transparent;"
                )
                row.addWidget(lbl_val)

                legend_layout.addLayout(row)

        chart_row.addWidget(legend_widget, stretch=3)
        main_vbox.addLayout(chart_row)

        # Clock Alert if losses on time >= 25% and at least 3 losses (relevant for All and Lost views)
        if self.current_mode in ("all", "lost"):
            time_loss_pct = self.stats.get("time_loss_pct", 0.0)
            losses = self.stats.get("losses", 0)
            if time_loss_pct >= 25.0 and losses >= 3:
                alert_lbl = QLabel(f"Clock Alert: {time_loss_pct:.0f}% of losses on time")
                alert_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                alert_lbl.setStyleSheet("""
                    background-color: rgba(230, 126, 34, 0.15);
                    color: #e67e22;
                    border-radius: 4px;
                    padding: 3px 8px;
                    font-size: 11px;
                    font-weight: 600;
                    border: none;
                """)
                main_vbox.addWidget(alert_lbl)

        self.set_content(self.content_widget)

    def refresh_styles(self):
        super().refresh_styles()
        if hasattr(self, "segmented_control"):
            self.segmented_control.setStyleSheet(f"""
                QFrame#ending_segmented {{
                    background-color: {Styles.COLOR_SURFACE_LIGHT};
                    border-radius: 6px;
                    border: none;
                }}
            """)
            self._update_segmented_styles()
        if self.stats:
            self._render_view()
