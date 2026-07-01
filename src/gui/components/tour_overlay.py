from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QGraphicsDropShadowEffect,
)
from PyQt6.QtCore import Qt, QRect, QPoint, QTimer
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush

from src.gui.styles import Styles
from src.gui.components.tour_manager import TourManager


class TourOverlay(QWidget):
    """
    Non-dimming tour overlay.

    - The overlay itself is fully transparent to mouse/keyboard events.
    - It only draws an animated accent glow-border around the target widget.
    - The floating bubble (QFrame sibling) provides the tooltip card.
    """

    def __init__(self, parent: QWidget, tour_manager: TourManager, on_finished=None):
        super().__init__(parent)
        self.tour = tour_manager
        self._on_finished = on_finished  # callable() invoked when tour ends/closes
        self._highlight_rect: QRect = QRect()
        self._glow_phase: int = 0  # 0-100 for pulse animation

        # Overlay is transparent — it only paints the highlight border.
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setGeometry(parent.rect())

        # Pulse timer for the glow border animation
        self._pulse_timer = QTimer(self)
        self._pulse_timer.setInterval(30)
        self._pulse_timer.timeout.connect(self._tick_pulse)

        # ── Bubble ────────────────────────────────────────────────────────
        # Bubble is a direct child of the main window (sibling of overlay)
        # so it sits above the overlay and receives mouse events normally.
        self.bubble = QFrame(parent)
        self.bubble.setObjectName("TourBubble")
        self.bubble.setStyleSheet(f"""
            QFrame#TourBubble {{
                background-color: {Styles.COLOR_SURFACE};
                border: 2px solid {Styles.COLOR_ACCENT};
                border-radius: 14px;
            }}
            QFrame#TourBubble QLabel {{
                background: transparent;
            }}
        """)
        self.bubble.setFixedWidth(360)

        # Drop-shadow so the bubble visually "floats" without needing a dim
        shadow = QGraphicsDropShadowEffect(self.bubble)
        shadow.setBlurRadius(32)
        shadow.setOffset(0, 6)
        shadow.setColor(QColor(0, 0, 0, 180))
        self.bubble.setGraphicsEffect(shadow)

        layout = QVBoxLayout(self.bubble)
        layout.setContentsMargins(20, 18, 20, 16)
        layout.setSpacing(10)

        self.text_label = QLabel()
        self.text_label.setWordWrap(True)
        self.text_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.text_label.setStyleSheet(
            "font-size: 14px; color: #FFFFFF;"
        )
        layout.addWidget(self.text_label)

        self.step_label = QLabel()
        self.step_label.setStyleSheet(
            "font-size: 11px; color: #9CA3AF;"
        )
        layout.addWidget(self.step_label)

        nav = QHBoxLayout()
        nav.setContentsMargins(0, 4, 0, 0)
        nav.setSpacing(8)

        self.prev_btn = QPushButton("← Back")
        self.prev_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.prev_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Styles.COLOR_SURFACE_LIGHT};
                color: #FFFFFF;
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 6px;
                padding: 7px 16px;
                font-size: 13px;
            }}
            QPushButton:hover {{ border-color: {Styles.COLOR_ACCENT}; }}
            QPushButton:disabled {{ color: #6B7280; border-color: {Styles.COLOR_BORDER}; }}
        """)
        self.prev_btn.clicked.connect(self._on_prev)
        nav.addWidget(self.prev_btn)

        nav.addStretch()

        self.next_btn = QPushButton("Next →")
        self.next_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.next_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Styles.COLOR_ACCENT};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 7px 22px;
                font-size: 13px;
                font-weight: bold;
            }}
            QPushButton:hover {{ background-color: {Styles.COLOR_ACCENT_HOVER}; }}
        """)
        self.next_btn.clicked.connect(self._on_next)
        nav.addWidget(self.next_btn)

        close_btn = QPushButton("✕")
        close_btn.setToolTip("Close tour  (Esc)")
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: #9CA3AF;
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 6px;
                padding: 7px 11px;
                font-size: 13px;
            }}
            QPushButton:hover {{ color: #FFFFFF; border-color: {Styles.COLOR_ACCENT}; }}
        """)
        close_btn.clicked.connect(self._on_close)
        nav.addWidget(close_btn)

        layout.addLayout(nav)
        self.bubble.hide()

    # ── Public API ────────────────────────────────────────────────────────

    def show_tour(self):
        self.setGeometry(self.parent().rect())
        self.show()
        self.raise_()
        self.bubble.raise_()
        self._pulse_timer.start()
        self._show_step()

    # ── Internal ─────────────────────────────────────────────────────────

    def _show_step(self):
        step = self.tour.current
        if step is None:
            self._close_all()
            return

        # ── Text & nav state ──────────────────────────────────────────────
        self.text_label.setText(step.text or "")
        total = self.tour.total_steps
        idx = self.tour.current_step
        self.step_label.setText(f"Step {idx + 1} of {total}")
        self.prev_btn.setEnabled(idx > 0)
        self.next_btn.setText("Finish" if idx == total - 1 else "Next →")

        # ── Target highlight rect ─────────────────────────────────────────
        self._highlight_rect = self._widget_rect_in_parent(step.target)

        # ── Size the bubble so word-wrap text is never clipped ────────────
        # We must set an explicit height on the QLabel because QLabel with
        # word-wrap does not know its height until it knows its width.
        # heightForWidth() gives the exact pixel height needed.
        self.bubble.show()
        lm = self.bubble.layout().contentsMargins()
        content_w = self.bubble.width() - lm.left() - lm.right()
        needed_h = self.text_label.heightForWidth(content_w)
        if needed_h > 0:
            self.text_label.setFixedHeight(needed_h)
        self.bubble.adjustSize()

        # ── Position bubble near the target ───────────────────────────────
        self._position_bubble(step.position)

        self.raise_()
        self.bubble.raise_()
        self.update()

    def _widget_rect_in_parent(self, widget: QWidget) -> QRect:
        parent = self.parent()
        try:
            tl = widget.mapToGlobal(QPoint(0, 0))
            return QRect(parent.mapFromGlobal(tl), widget.size())
        except Exception:
            return QRect(0, 0, 100, 30)

    def _position_bubble(self, position: str):
        target = self._highlight_rect
        pr = self.parent().rect()
        bw = self.bubble.width()
        bh = self.bubble.height()
        gap = 18

        if position == "above":
            x = target.center().x() - bw // 2
            y = target.top() - bh - gap
        elif position == "below":
            x = target.center().x() - bw // 2
            y = target.bottom() + gap
        elif position == "left":
            x = target.left() - bw - gap
            y = target.center().y() - bh // 2
        else:  # "right"
            x = target.right() + gap
            y = target.center().y() - bh // 2

        # Clamp inside the window
        x = max(8, min(x, pr.width() - bw - 8))
        y = max(8, min(y, pr.height() - bh - 8))
        self.bubble.move(x, y)

    # ── Pulse animation ───────────────────────────────────────────────────

    def _tick_pulse(self):
        self._glow_phase = (self._glow_phase + 4) % 100
        self.update()

    # ── Painting — only the accent glow border ────────────────────────────

    def paintEvent(self, event):
        if self._highlight_rect.isNull() or self._highlight_rect.isEmpty():
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        r = self._highlight_rect.adjusted(-6, -6, 6, 6)

        # Pulsing glow: alpha oscillates between 120 and 255
        import math
        t = (1 + math.sin(self._glow_phase / 100 * 2 * math.pi)) / 2
        glow_alpha = int(120 + 135 * t)

        accent = QColor(Styles.COLOR_ACCENT)
        accent.setAlpha(glow_alpha)

        # Outer glow (wide, semi-transparent)
        glow_pen = QPen(accent, 6)
        painter.setPen(glow_pen)
        painter.setBrush(Qt.GlobalColor.transparent)
        painter.drawRoundedRect(r.adjusted(-3, -3, 3, 3), 13, 13)

        # Inner sharp border
        accent.setAlpha(255)
        painter.setPen(QPen(accent, 2))
        painter.drawRoundedRect(r, 10, 10)

    # ── Resize tracking ───────────────────────────────────────────────────

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.tour.active and not self._highlight_rect.isNull():
            self._show_step()

    # ── Keyboard ─────────────────────────────────────────────────────────

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key.Key_Escape:
            self._on_close()
        elif key in (Qt.Key.Key_Right, Qt.Key.Key_Return, Qt.Key.Key_Space):
            self._on_next()
        elif key == Qt.Key.Key_Left:
            self._on_prev()
        else:
            super().keyPressEvent(event)

    # ── Slot handlers ─────────────────────────────────────────────────────

    def _on_next(self):
        if not self.tour.next():
            # Last step completed — mark as seen.
            self._close_all(notify_finished=True)
            return
        self._show_step()

    def _on_prev(self):
        self.tour.prev()
        self._show_step()

    def _on_close(self):
        """X button / Esc — dismissed, NOT completed. Do NOT mark seen."""
        self.tour.stop()
        self._close_all(notify_finished=False)

    def close_silently(self):
        """Called by the main window on page switch — hide without any callback."""
        self.tour.stop()
        self._close_all(notify_finished=False)

    def _close_all(self, notify_finished: bool = False):
        self._pulse_timer.stop()
        self.hide()
        self.bubble.hide()
        self._highlight_rect = QRect()
        if notify_finished and callable(self._on_finished):
            self._on_finished()
