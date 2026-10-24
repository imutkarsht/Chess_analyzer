"""
Custom widget representing a compact move cell that packs the classification icon, SAN, and think-time.
"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QIcon
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QToolButton, QVBoxLayout, QWidget

from ..styles import Styles

# Every classified move keeps its badge. Only decisive/problem moves get colour
# and weight; routine classes (Book/Best/Excellent/Good) stay neutral so a page
# of solid moves does not turn into a wall of green.
EMPHASIS_CLASSES = frozenset({"Brilliant", "Great", "Inaccuracy", "Mistake", "Blunder", "Miss"})


class MoveCellWidget(QWidget):
    """
    Compact move cell that packs the classification icon, SAN, and optional think-time.
    """

    clicked = pyqtSignal(int)  # carries the move index
    variation_clicked = pyqtSignal(int)

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self.setObjectName("MoveCell")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 4, 6, 4)
        outer.setSpacing(3)

        # Top row: icon + SAN + time label, with the time kept adjacent to the
        # move text so it fits in a narrow pane instead of being pushed to the
        # far edge of a stretched column.
        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(4)

        self._icon_label = QLabel(self)
        self._icon_label.setFixedSize(16, 16)
        self._icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._icon_label.setStyleSheet(Styles.get_transparent_label_style())
        top_row.addWidget(self._icon_label, 0, Qt.AlignmentFlag.AlignVCenter)

        self._san_label = QLabel(self)
        self._san_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        self._san_label.setMinimumWidth(0)
        self._san_label.setStyleSheet(Styles.get_transparent_label_style())
        top_row.addWidget(self._san_label, 1, Qt.AlignmentFlag.AlignVCenter)

        self._variation_btn = QToolButton(self)
        self._variation_btn.setFixedSize(18, 18)
        self._variation_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._variation_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._variation_btn.hide()
        self._variation_btn.clicked.connect(
            lambda _checked=False: self.variation_clicked.emit(self._move_index)
        )
        top_row.addWidget(self._variation_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        self._time_label = QLabel(self)
        self._time_label.setFixedWidth(30)
        self._time_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight)
        self._time_label.setStyleSheet(
            Styles.get_label_style(size=11, color=Styles.COLOR_TEXT_SECONDARY)
            + " "
            + Styles.get_transparent_label_style()
        )
        top_row.addWidget(self._time_label, 0, Qt.AlignmentFlag.AlignVCenter)

        outer.addLayout(top_row, 1)

        # Bottom row: a 2-pixel-tall think-time bar (shown only if time_spent is present)
        self._bar = QLabel(self)
        self._bar.setFixedHeight(2)
        self._bar.setStyleSheet(Styles.get_transparent_label_style())
        self._bar.hide()
        outer.addWidget(self._bar)

        self._move_index: int = -1
        self._san_text: str = ""
        self._classification_name: str = ""
        self._last_time_spent: float | None = None
        self._last_max_seconds: float = 30.0
        self._variation_count: int = 0

        # Visual state (the embedded widget, not the QTableWidgetItem, paints the
        # row background so selection/hover stay visible above the cell widget).
        self._selected: bool = False
        self._row_active: bool = False
        self._hovered: bool = False
        self._compact: bool = False
        self._apply_background()

        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    # ----- public API -------------------------------------------------
    def set_move(
        self,
        move,
        move_index: int,
        icon: QIcon = None,
        max_seconds: float = 30.0,
        variation_count: int | None = None,
    ) -> None:
        self._move_index = move_index
        self._san_text = move.san
        self._san_label.setText(move.san)
        self._classification_name = move.classification or ""
        if variation_count is not None:
            self.set_variation_count(variation_count)

        # Badge stays for every classified move; only emphasis classes keep a colour.
        self._san_label.setStyleSheet(self._san_style())

        if icon is not None and not icon.isNull():
            self._icon_label.setPixmap(icon.pixmap(16, 16))
        else:
            self._icon_label.clear()

        # Think-time text + bar
        time_spent_val = None
        if move.time_spent is not None:
            try:
                time_spent_val = float(move.time_spent)
            except (TypeError, ValueError):
                time_spent_val = None

        self._last_time_spent = time_spent_val
        self._last_max_seconds = float(max_seconds) if max_seconds is not None else 30.0

        if time_spent_val is not None and time_spent_val > 0:
            time_str = self._format_time(time_spent_val)
            self._time_label.setText(time_str)

            safe_max = max(1.0, self._last_max_seconds)
            ratio = min(1.0, time_spent_val / safe_max)
            colour = self._bar_colour(ratio)
            track = Styles.COLOR_SURFACE_LIGHT
            self._bar.setStyleSheet(Styles.get_think_time_bar_style(colour, track, ratio))
            self._bar.show()
            self.setToolTip(
                f"{move.classification + ': ' if move.classification else ''}"
                f"{move.san}  —  Think time: {time_str}"
            )
        else:
            self._time_label.setText("")
            self._bar.hide()
            self.setToolTip(
                f"{move.classification + ': ' if move.classification else ''}{move.san}"
            )

    def set_state(self, selected: bool, row_active: bool) -> None:
        """Paint the active half-move and the faint tint of its partner."""
        if self._selected == selected and self._row_active == row_active:
            return
        self._selected = selected
        self._row_active = row_active
        self._apply_background()

    def set_compact(self, compact: bool) -> None:
        """Drop the numeric think time when the column is too narrow for SAN + time."""
        if self._compact == compact:
            return
        self._compact = compact
        self._time_label.setVisible(not compact)

    def set_variation_count(self, count: int) -> None:
        """Show a branch badge when this position owns saved variations."""
        self._variation_count = max(0, int(count))
        visible = self._variation_count > 0
        self._variation_btn.setVisible(visible)
        if not visible:
            return
        self._variation_btn.setText("" if self._variation_icon() else str(self._variation_count))
        self._variation_btn.setToolTip(
            f"Explore {self._variation_count} saved variation"
            f"{'s' if self._variation_count != 1 else ''} from this position"
        )
        self._variation_btn.setStyleSheet(Styles.get_variation_badge_style())

    def _san_style(self) -> str:
        if self._classification_name in EMPHASIS_CLASSES:
            color = Styles.get_class_color(self._classification_name) or Styles.COLOR_TEXT_PRIMARY
            weight = "600"
        else:
            color = Styles.COLOR_TEXT_PRIMARY
            weight = "500"
        return (
            Styles.get_label_style(size=13, color=color, weight=weight)
            + " "
            + Styles.get_transparent_label_style()
        )

    def _variation_icon(self) -> bool:
        try:
            import qtawesome as qta

            self._variation_btn.setIcon(qta.icon("fa5s.code-branch", color=Styles.COLOR_ACCENT))
            return True
        except ImportError:
            self._variation_btn.setIcon(QIcon())
            return False

    def refresh_styles(self):
        self._san_label.setStyleSheet(self._san_style())

        self._time_label.setStyleSheet(
            Styles.get_label_style(size=11, color=Styles.COLOR_TEXT_SECONDARY)
            + " "
            + Styles.get_transparent_label_style()
        )

        if self._last_time_spent is not None and self._last_time_spent > 0:
            safe_max = max(1.0, self._last_max_seconds)
            ratio = min(1.0, self._last_time_spent / safe_max)
            colour = self._bar_colour(ratio)
            track = Styles.COLOR_SURFACE_LIGHT
            self._bar.setStyleSheet(Styles.get_think_time_bar_style(colour, track, ratio))
            self._bar.show()
        else:
            self._bar.hide()

        if self._variation_count > 0:
            self.set_variation_count(self._variation_count)

        self._apply_background()

    def _apply_background(self) -> None:
        if self._selected:
            background = Styles.COLOR_ACCENT_SUBTLE
            left = Styles.COLOR_ACCENT
        elif self._hovered:
            background = Styles.COLOR_SURFACE_LIGHT
            left = "transparent"
        elif self._row_active:
            background = self._rgba(Styles.COLOR_SURFACE_LIGHT, 0.55)
            left = "transparent"
        else:
            background = "transparent"
            left = "transparent"

        self.setStyleSheet(f"""
            QWidget#MoveCell {{
                background-color: {background};
                border-left: 2px solid {left};
            }}
        """)

    def enterEvent(self, event):
        self._hovered = True
        self._apply_background()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self._apply_background()
        super().leaveEvent(event)

    @staticmethod
    def _rgba(hex_color: str, alpha: float) -> str:
        color = QColor(hex_color)
        return f"rgba({color.red()}, {color.green()}, {color.blue()}, {alpha:.2f})"

    @staticmethod
    def _format_time(seconds: float) -> str:
        if seconds >= 3600:
            return f"{seconds / 3600:.1f}h"
        if seconds >= 60:
            return f"{seconds / 60:.1f}m"
        if seconds >= 10:
            return f"{seconds:.0f}s"
        return f"{seconds:.1f}s"

    def _bar_colour(self, ratio: float) -> str:
        """Neutral ramp: length carries the time, colour stays out of the
        classification palette (green/yellow/orange already mean move quality)."""
        ratio = max(0.0, min(1.0, ratio))
        start = QColor(Styles.COLOR_TEXT_MUTED)
        end = QColor(Styles.COLOR_TEXT_PRIMARY)
        r = int(start.red() + (end.red() - start.red()) * ratio)
        g = int(start.green() + (end.green() - start.green()) * ratio)
        b = int(start.blue() + (end.blue() - start.blue()) * ratio)
        return f"rgb({r},{g},{b})"

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._move_index)
            event.accept()
            return
        super().mousePressEvent(event)
