from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QGraphicsOpacityEffect


class Toast(QWidget):
    DURATIONS = {
        "info": 3500,
        "success": 3000,
        "warning": 4500,
        "error": 6000,
    }

    COLORS = {
        "info": "#3498db",
        "success": "#27ae60",
        "warning": "#e67e22",
        "error": "#e74c3c",
    }

    def __init__(self, parent, message, kind="info", duration=None):
        super().__init__(parent)
        self._kind = kind
        self._duration = duration or self.DURATIONS.get(kind, 3500)
        self._is_dismissing = False

        kind_color = self.COLORS.get(kind, "#3498db")
        dark_bg = "#2C2C30"

        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            Toast {{
                background-color: {dark_bg};
                border: 1px solid {kind_color};
                border-radius: 12px;
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

        icon_map = {"info": "\u2139", "success": "\u2713", "warning": "\u26A0", "error": "\u2717"}
        icon = QLabel(icon_map.get(kind, "\u2139"))
        icon.setStyleSheet(f"color: {kind_color}; font-size: 16px; font-weight: 700; background: transparent;")
        icon.setFixedWidth(20)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon)

        self._msg = QLabel(message)
        self._msg.setStyleSheet("color: #F0F0F2; font-size: 14px; font-weight: 500; background: transparent;")
        self._msg.setWordWrap(True)
        layout.addWidget(self._msg)

        self.adjustSize()
        self.setMinimumWidth(280)
        self.setMaximumWidth(420)

        self._opacity_effect = QGraphicsOpacityEffect(self)
        self._opacity_effect.setOpacity(0.0)
        self.setGraphicsEffect(self._opacity_effect)

        self._fade_in = QPropertyAnimation(self._opacity_effect, b"opacity")
        self._fade_in.setDuration(200)
        self._fade_in.setStartValue(0.0)
        self._fade_in.setEndValue(1.0)
        self._fade_in.setEasingCurve(QEasingCurve.Type.OutCubic)

        parent.installEventFilter(self)

        QTimer.singleShot(self._duration, self._start_dismiss)

    def _start_dismiss(self):
        if self._is_dismissing:
            return
        self._is_dismissing = True
        self._fade_out = QPropertyAnimation(self._opacity_effect, b"opacity")
        self._fade_out.setDuration(250)
        self._fade_out.setStartValue(1.0)
        self._fade_out.setEndValue(0.0)
        self._fade_out.setEasingCurve(QEasingCurve.Type.OutQuad)
        self._fade_out.finished.connect(self.deleteLater)
        self._fade_out.start()

    def eventFilter(self, obj, event):
        if obj is self.parent() and event.type() == event.Type.Resize:
            self._reposition()
        return super().eventFilter(obj, event)

    def _reposition(self):
        parent = self.parent()
        if parent:
            x = parent.width() - self.width() - 24
            y = 20
            self.move(x, y)

    def showEvent(self, event):
        super().showEvent(event)
        self._reposition()
        self._fade_in.start()

    @classmethod
    def show_message(cls, parent, message, kind="info", duration=None):
        toast = cls(parent, message, kind, duration)
        toast.show()
        return toast
