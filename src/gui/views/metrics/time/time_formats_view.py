"""Formats page for the Time & Clock Analytics card."""

from __future__ import annotations

from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from src.gui.components import EmptyState, SegmentedBar
from src.gui.styles import Styles
from src.gui.utils.gui_utils import clear_layout
from src.gui.views.metrics.time.panels import IconTile


class FormatsView(QWidget):
    """Performance breakdown per speed category."""

    FORMAT_META: dict[str, tuple[str, str]] = {
        "Bullet": ("fa5s.bolt", "Fast-paced scrambles (<3m)"),
        "Blitz": ("fa5s.stopwatch", "Standard fast play (3–5m)"),
        "Rapid": ("fa5s.hourglass-half", "Tactical calculation (10–30m)"),
        "Classical": ("fa5s.chess-rook", "Traditional classical (>30m)"),
        "Chess960": ("fa5s.random", "Fischer Random (Freestyle)"),
        "UltraBullet": ("fa5s.tachometer-alt", "Hyper-speed play (<30s)"),
    }

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(10)
        self._formats: dict[str, dict] = {}
        self._has_clock = False
        self._dirty = True

    def set_data(self, formats: dict[str, dict], has_clock: bool) -> None:
        self._formats = formats or {}
        self._has_clock = has_clock
        self._dirty = True

    def mark_dirty(self) -> None:
        self._dirty = True

    def ensure_rendered(self) -> None:
        if not self._dirty:
            return
        self._render()
        self._dirty = False

    def _render(self) -> None:
        clear_layout(self._layout)

        if not self._formats and not self._has_clock:
            self._layout.addWidget(
                EmptyState("No time control or clock data available for selected games.")
            )
            return

        preferred_order = ["Bullet", "Blitz", "Rapid", "Classical", "Chess960"]
        sorted_keys = sorted(
            self._formats.keys(),
            key=lambda key: (
                preferred_order.index(key) if key in preferred_order else 99,
                -self._formats[key]["games"],
            ),
        )
        for sp in sorted_keys:
            row = self._build_format_row(sp, self._formats[sp])
            if row is not None:
                self._layout.addWidget(row)

    def _build_format_row(self, sp: str, f_data: dict) -> QFrame | None:
        tot = f_data["games"]
        if tot == 0:
            return None

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
        row_layout = QVBoxLayout(row)
        row_layout.setContentsMargins(4, 4, 4, 4)
        row_layout.setSpacing(6)

        top_line = QHBoxLayout()
        top_line.setSpacing(10)
        top_line.addWidget(IconTile(icon_name))

        info_box = QVBoxLayout()
        info_box.setSpacing(1)
        name_lbl = QLabel(sp)
        name_lbl.setStyleSheet(
            f"color: {Styles.COLOR_TEXT_PRIMARY}; font-weight: 700; "
            "font-size: 13px; border: none;"
        )
        info_box.addWidget(name_lbl)

        record_lbl = QLabel(f"{tot} Games • {w}W {d}D {losses}L")
        record_lbl.setStyleSheet(
            f"color: {Styles.COLOR_TEXT_SECONDARY}; font-size: 11px; border: none;"
        )
        info_box.addWidget(record_lbl)
        top_line.addLayout(info_box)
        top_line.addStretch()

        badges = QHBoxLayout()
        badges.setSpacing(6)
        wr_color = Styles.COLOR_RESULT_WIN if wr >= 50.0 else Styles.COLOR_TEXT_PRIMARY
        badges.addWidget(self._badge(f"{wr:.1f}% Win", wr_color, weight=700))
        if acc > 0:
            badges.addWidget(self._badge(f"{acc:.1f}% Acc", Styles.COLOR_TEXT_PRIMARY))
        if avg_t > 0:
            badges.addWidget(self._badge(f"{avg_t:.1f}s / mv", Styles.COLOR_TEXT_PRIMARY))
        if tl > 0:
            badges.addWidget(
                self._badge(
                    f"{tl} Timeouts",
                    Styles.COLOR_BLUNDER,
                    weight=700,
                    border_color=Styles.COLOR_BLUNDER,
                )
            )
        top_line.addLayout(badges)
        row_layout.addLayout(top_line)

        segments = []
        if w > 0:
            segments.append(
                (max(1, int(w / tot * 100)), Styles.COLOR_RESULT_WIN, None)
            )
        if d > 0:
            segments.append(
                (max(1, int(d / tot * 100)), Styles.COLOR_RESULT_DRAW, None)
            )
        if losses > 0:
            segments.append(
                (max(1, int(losses / tot * 100)), Styles.COLOR_RESULT_LOSS, None)
            )
        row_layout.addWidget(
            SegmentedBar(
                segments,
                height=6,
                radius=3,
                segment_radius=3,
                spacing=1,
                track_color=Styles.COLOR_SURFACE,
            )
        )
        return row

    @staticmethod
    def _badge(
        text: str,
        color: str,
        *,
        weight: int = 600,
        border_color: str = Styles.COLOR_BORDER,
    ) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet(
            f"background-color: {Styles.COLOR_SURFACE}; color: {color}; "
            f"font-weight: {weight}; font-size: 11px; "
            f"border: 1px solid {border_color}; border-radius: 4px; padding: 3px 6px;"
        )
        return label
