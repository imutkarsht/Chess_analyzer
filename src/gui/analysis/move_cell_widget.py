"""
Custom widget representing a compact move cell that packs the classification icon, SAN, and think-time.
"""
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QIcon
from ..styles import Styles

class MoveCellWidget(QWidget):
    """
    Compact move cell that packs the classification icon, the SAN, an
    optional think-time label, and a thin coloured think-time bar in a
    single column. This keeps the move list at 3 columns (#, White, Black)
    while still surfacing the clock information visually.

    The widget emits ``clicked`` when the user clicks anywhere in it, so
    a single ``setCellWidget`` replacement keeps the existing
    cellClicked-style handlers working.
    """

    clicked = pyqtSignal(int)  # carries the move index

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        # Main horizontal layout: [icon] [SAN + bar]  [think-time label]
        outer = QVBoxLayout(self)
        outer.setContentsMargins(4, 2, 4, 2)
        outer.setSpacing(0)

        # Top row: icon + SAN + time label
        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(4)

        self._icon_label = QLabel(self)
        self._icon_label.setFixedSize(20, 20)
        self._icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        top_row.addWidget(self._icon_label, 0, Qt.AlignmentFlag.AlignVCenter)

        self._san_label = QLabel(self)
        self._san_label.setAlignment(
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
        )
        font = self._san_label.font()
        font.setPointSize(13)
        self._san_label.setFont(font)
        top_row.addWidget(self._san_label, 1, Qt.AlignmentFlag.AlignVCenter)

        self._time_label = QLabel(self)
        self._time_label.setAlignment(
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight
        )
        self._time_label.setStyleSheet(
            "color: rgba(255,255,255,140); font-size: 10px;"
        )
        top_row.addWidget(self._time_label, 0, Qt.AlignmentFlag.AlignVCenter)

        outer.addLayout(top_row)

        # Bottom row: a 3-pixel-tall coloured think-time bar (full width).
        # We use a plain QLabel with a stylesheet background so we don't
        # need a second custom widget for such a simple thing.
        self._bar = QLabel(self)
        self._bar.setFixedHeight(3)
        self._bar.setStyleSheet("background: rgba(255,255,255,20); border: none;")
        outer.addWidget(self._bar)

        # Track the move index so clicks can re-emit it.
        self._move_index: int = -1
        self._san_text: str = ""
        self._classification_color: str = ""
        self._classification_name: str = ""

        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    # ----- public API -------------------------------------------------
    def set_move(self, move, move_index: int, icon: QIcon = None,
                 san_color: str = "", max_seconds: float = 30.0) -> None:
        self._move_index = move_index
        self._san_text = move.san
        self._san_label.setText(move.san)
        self._classification_name = move.classification or ""
        self._classification_color = san_color

        if san_color:
            self._san_label.setStyleSheet(
                f"color: {san_color}; font-size: 13px; background: transparent;"
            )
        else:
            self._san_label.setStyleSheet(
                "color: white; font-size: 13px; background: transparent;"
            )

        if move.classification in ("Brilliant", "Blunder", "Mistake", "Miss"):
            f = self._san_label.font()
            f.setBold(True)
            self._san_label.setFont(f)
        else:
            f = self._san_label.font()
            f.setBold(False)
            self._san_label.setFont(f)

        if icon is not None and not icon.isNull():
            self._icon_label.setPixmap(icon.pixmap(20, 20))
        else:
            self._icon_label.clear()

        # Think-time text + bar
        time_spent_val = None
        if move.time_spent is not None:
            try:
                time_spent_val = float(move.time_spent)
            except (TypeError, ValueError):
                time_spent_val = None

        if time_spent_val is not None:
            if time_spent_val >= 3600:
                time_str = f"{time_spent_val / 3600:.1f}h"
            elif time_spent_val >= 60:
                time_str = f"{time_spent_val / 60:.1f}m"
            else:
                time_str = f"{time_spent_val:.1f}s"
                
            self._time_label.setText(time_str)
            
            # Use dynamically passed max_seconds for color ratio
            safe_max = max(1.0, float(max_seconds) if max_seconds is not None else 30.0)
            ratio = min(1.0, time_spent_val / safe_max)
            colour = self._bar_colour(ratio)
            # Render as left-to-right fill: 100% of the cell width for the
            # coloured portion, plus a faded track for the remainder.
            self._bar.setStyleSheet(
                f"""
                QLabel {{
                    background: qlineargradient(
                        x1:0, y1:0, x2:1, y2:0,
                        stop:0 {colour},
                        stop:{ratio:.4f} {colour},
                        stop:{ratio:.4f} rgba(255,255,255,18),
                        stop:1 rgba(255,255,255,18)
                    );
                    border: none;
                }}
                """
            )
            self.setToolTip(
                f"{move.classification + ': ' if move.classification else ''}"
                f"{move.san}  —  Think time: {time_str}"
            )
        else:
            self._time_label.setText("")
            self._bar.setStyleSheet("background: rgba(255,255,255,12); border: none;")
            self.setToolTip(
                f"{move.classification + ': ' if move.classification else ''}"
                f"{move.san}"
            )

    # ----- helpers ----------------------------------------------------
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

    # ----- mouse handling so a click on the cell still selects the move
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._move_index)
            event.accept()
            return
        super().mousePressEvent(event)
