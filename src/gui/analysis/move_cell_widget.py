"""
Custom widget representing a compact move cell that packs the classification icon, SAN, and think-time.
"""
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QIcon
from ..styles import Styles

class MoveCellWidget(QWidget):
    """
    Compact move cell that packs the classification icon, SAN, and optional think-time.
    """

    clicked = pyqtSignal(int)  # carries the move index

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(6, 3, 6, 3)
        outer.setSpacing(1)

        # Top row: icon + SAN + time label
        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(6)

        self._icon_label = QLabel(self)
        self._icon_label.setFixedSize(18, 18)
        self._icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._icon_label.setStyleSheet(Styles.get_transparent_label_style())
        top_row.addWidget(self._icon_label, 0, Qt.AlignmentFlag.AlignVCenter)

        self._san_label = QLabel(self)
        self._san_label.setAlignment(
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
        )
        self._san_label.setStyleSheet(Styles.get_transparent_label_style())
        top_row.addWidget(self._san_label, 1, Qt.AlignmentFlag.AlignVCenter)

        self._time_label = QLabel(self)
        self._time_label.setAlignment(
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight
        )
        self._time_label.setStyleSheet(
            Styles.get_label_style(size=10, color=Styles.COLOR_TEXT_MUTED) + " " + Styles.get_transparent_label_style()
        )
        top_row.addWidget(self._time_label, 0, Qt.AlignmentFlag.AlignVCenter)

        outer.addLayout(top_row)

        # Bottom row: a 2-pixel-tall coloured think-time bar (shown only if time_spent is present)
        self._bar = QLabel(self)
        self._bar.setFixedHeight(2)
        self._bar.setStyleSheet(Styles.get_transparent_label_style())
        self._bar.hide()
        outer.addWidget(self._bar)

        self._move_index: int = -1
        self._san_text: str = ""
        self._classification_color: str = ""
        self._classification_name: str = ""
        self._last_time_spent: float | None = None
        self._last_max_seconds: float = 30.0

        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    # ----- public API -------------------------------------------------
    def set_move(self, move, move_index: int, icon: QIcon = None,
                 san_color: str = "", max_seconds: float = 30.0) -> None:
        self._move_index = move_index
        self._san_text = move.san
        self._san_label.setText(move.san)
        self._classification_name = move.classification or ""

        # Determine color dynamically based on classification
        if self._classification_name:
            color = Styles.get_class_color(self._classification_name) or Styles.COLOR_TEXT_PRIMARY
        else:
            color = Styles.COLOR_TEXT_PRIMARY

        font_weight = "bold" if move.classification in ("Brilliant", "Blunder", "Mistake", "Miss", "Great") else "500"
        self._san_label.setStyleSheet(
            Styles.get_label_style(size=13, color=color, weight=font_weight) + " " + Styles.get_transparent_label_style()
        )

        if icon is not None and not icon.isNull():
            self._icon_label.setPixmap(icon.pixmap(18, 18))
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
            if time_spent_val >= 3600:
                time_str = f"{time_spent_val / 3600:.1f}h"
            elif time_spent_val >= 60:
                time_str = f"{time_spent_val / 60:.1f}m"
            else:
                time_str = f"{time_spent_val:.1f}s"
                
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
                f"{move.classification + ': ' if move.classification else ''}"
                f"{move.san}"
            )

    def refresh_styles(self):
        if self._classification_name:
            color = Styles.get_class_color(self._classification_name) or Styles.COLOR_TEXT_PRIMARY
        else:
            color = Styles.COLOR_TEXT_PRIMARY

        font_weight = "bold" if self._classification_name in ("Brilliant", "Blunder", "Mistake", "Miss", "Great") else "500"
        self._san_label.setStyleSheet(
            Styles.get_label_style(size=13, color=color, weight=font_weight) + " " + Styles.get_transparent_label_style()
        )
        
        self._time_label.setStyleSheet(
            Styles.get_label_style(size=10, color=Styles.COLOR_TEXT_MUTED) + " " + Styles.get_transparent_label_style()
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

    def _bar_colour(self, ratio: float) -> str:
        ratio = max(0.0, min(1.0, ratio))
        if ratio < 0.5:
            t = ratio / 0.5
            r = int(76 + (255 - 76) * t)
            g = int(175 + (193 - 175) * t)
            b = int(80 + 7 * t)
        else:
            t = (ratio - 0.5) / 0.5
            r = int(255 + (231 - 255) * t)
            g = int(193 + (76 - 193) * t)
            b = int(7 + (60 - 7) * t)
        return f"rgb({r},{g},{b})"

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._move_index)
            event.accept()
            return
        super().mousePressEvent(event)
