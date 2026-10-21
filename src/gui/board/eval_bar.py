from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QPainter
from PyQt6.QtWidgets import QWidget


class EvalBarWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedWidth(24)
        self.cp = 0.0
        self.target_cp = 0.0
        self.mate = None  # None, positive int (White mate), negative int (Black mate)

        # Animation
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.animate)
        # Timer started on demand in set_eval()

    def set_eval(self, cp=None, mate=None):
        try:
            self.target_cp = cp if cp is not None else 0.0
            self.mate = mate
            # If mate, snap immediately
            if mate is not None:
                self.cp = self.target_cp
            elif (
                abs(self.target_cp - self.cp) > 1
                and hasattr(self, "timer")
                and self.timer
                and not self.timer.isActive()
            ):
                self.timer.start(16)

            self.update()
        except (RuntimeError, AttributeError):
            pass

    def animate(self):
        try:
            if self.mate is not None:
                if hasattr(self, "timer") and self.timer:
                    self.timer.stop()
                return

            diff = self.target_cp - self.cp
            if abs(diff) < 1:
                self.cp = self.target_cp
                if hasattr(self, "timer") and self.timer:
                    self.timer.stop()
            else:
                # Simple lerp
                self.cp += diff * 0.1
                self.update()
        except (RuntimeError, AttributeError):
            pass

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        width = self.width()
        height = self.height()

        # Background (Black/Dark Grey)
        painter.fillRect(0, 0, width, height, QColor("#404040"))

        # Calculate White's height percentage
        white_pct = 0.5

        if self.mate is not None:
            if self.mate > 0:
                white_pct = 1.0  # White wins
            else:
                white_pct = 0.0  # Black wins
        else:
            # Sigmoid-like scaling for CP
            # Using a simple clamp for now: +/- 400 (4 pawns) = 100% advantage visually?
            clamped_cp = max(-1000, min(1000, self.cp))
            # Map -1000..1000 to 0..1
            white_pct = (clamped_cp + 1000) / 2000

        # Draw White bar
        white_height = height * white_pct
        white_top = height - white_height

        # Draw Black part (top)
        painter.fillRect(0, 0, width, int(white_top), QColor("#404040"))

        # Draw White part (bottom)
        painter.fillRect(0, int(white_top), width, int(white_height), QColor("#FFFFFF"))

        # Draw numeric label if space permits
        if height > 50:
            font = painter.font()
            # Use setPointSize to avoid "Point size <= 0" warnings on some systems
            font.setPointSize(8)
            font.setBold(True)
            painter.setFont(font)

            label_text = ""
            if self.mate is not None:
                label_text = f"M{abs(self.mate)}"
            else:
                label_text = f"{abs(self.cp) / 100:.1f}"

            # Keep the label on the winning side's fill: dark text on the
            # white (bottom) area, light text on the dark (top) area.
            if white_pct > 0.5:
                painter.setPen(QColor("#404040"))
            else:
                painter.setPen(QColor("#FFFFFF"))
            x, y, w, h = self._label_rect()
            painter.drawText(
                x,
                y,
                w,
                h,
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
                label_text,
            )

    def _label_rect(self) -> tuple[int, int, int, int]:
        """Geometry of the numeric label, fully inside the bar.

        The label used to be drawn from ``height - 5`` downwards, so when
        White was winning it fell outside the widget and was clipped away.
        """
        if self.mate is not None:
            white_wins = self.mate > 0
        else:
            white_wins = self.cp > 0
        if white_wins:
            return 0, max(0, self.height() - 22), self.width(), 20
        return 0, 2, self.width(), 20
