"""
Game navigation controls widget.
"""
from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QToolButton, QWidget

from src.gui.styles import Styles

try:
    import qtawesome as qta

    HAS_QTAWESOME = True
except ImportError:  # pragma: no cover - exercised only on broken installs
    qta = None
    HAS_QTAWESOME = False


class GameControlsWidget(QWidget):
    """Compact, centred navigation toolbar for stepping through a game."""

    first_clicked = pyqtSignal()
    prev_clicked = pyqtSignal()
    next_clicked = pyqtSignal()
    last_clicked = pyqtSignal()
    flip_clicked = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setObjectName("BoardControls")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(2, 7, 2, 3)
        outer.setSpacing(0)

        self.nav_toolbar = QWidget()
        toolbar_layout = QHBoxLayout(self.nav_toolbar)
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        toolbar_layout.setSpacing(2)

        self.btn_first = self._make_button(
            "fa5s.angle-double-left", "⏮", "First move (Home)", self.first_clicked
        )
        self.btn_prev = self._make_button(
            "fa5s.angle-left", "◀", "Previous move (←)", self.prev_clicked
        )
        self.btn_next = self._make_button(
            "fa5s.angle-right", "▶", "Next move (→)", self.next_clicked
        )
        self.btn_last = self._make_button(
            "fa5s.angle-double-right", "⏭", "Last move (End)", self.last_clicked
        )
        self.btn_flip = self._make_button(
            "fa5s.exchange-alt", "⇄", "Flip board (F)", self.flip_clicked
        )

        toolbar_layout.addWidget(self.btn_first)
        toolbar_layout.addWidget(self.btn_prev)
        toolbar_layout.addWidget(self.btn_next)
        toolbar_layout.addWidget(self.btn_last)

        outer.addWidget(self.nav_toolbar)
        outer.addStretch()
        outer.addWidget(self.btn_flip)

        self.refresh_styles()

    def _make_button(self, icon_name, fallback, tooltip, signal):
        btn = QToolButton()
        btn.setAutoRaise(True)
        btn.setFixedSize(32, 30)
        btn.setIconSize(QSize(15, 15))
        btn.setToolTip(tooltip)
        btn.setAccessibleName(tooltip)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        # NoFocus prevents the buttons from stealing keyboard focus when clicked.
        btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        if HAS_QTAWESOME:
            icon = qta.icon(icon_name, color=Styles.COLOR_TEXT_PRIMARY)
            if icon.isNull():
                btn.setText(fallback)
            else:
                btn.setIcon(icon)
        else:
            btn.setText(fallback)
        btn.clicked.connect(lambda _checked=False: signal.emit())
        return btn

    def refresh_styles(self):
        self.setStyleSheet(Styles.get_board_controls_style())
        button_style = Styles.get_nav_icon_button_style()
        for btn in (self.btn_first, self.btn_prev, self.btn_next, self.btn_last, self.btn_flip):
            btn.setStyleSheet(button_style)
