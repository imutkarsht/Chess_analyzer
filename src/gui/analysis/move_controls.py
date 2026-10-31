"""Shared move navigation controls for the Analysis and Explorer pages."""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QWidget

from src.gui.components import Button, ButtonSize, ButtonVariant
from src.gui.styles import Styles

try:
    import qtawesome as qta

    HAS_QTAWESOME = True
except ImportError:  # pragma: no cover - exercised only on broken installs
    qta = None
    HAS_QTAWESOME = False


class MoveControls(QWidget):
    """First/prev/next/last toolbar with an optional flip button."""

    first_clicked = pyqtSignal()
    prev_clicked = pyqtSignal()
    next_clicked = pyqtSignal()
    last_clicked = pyqtSignal()
    flip_clicked = pyqtSignal()

    def __init__(self, variant: str = "analysis", parent: QWidget | None = None):
        super().__init__(parent)
        if variant not in {"analysis", "explorer"}:
            raise ValueError(f"Unknown move-controls variant: {variant}")
        self.variant = variant

        self.btn_first: Button
        self.btn_prev: Button
        self.btn_next: Button
        self.btn_last: Button
        self.btn_flip: Button | None = None

        if variant == "analysis":
            self._build_analysis_controls()
        else:
            self._build_explorer_controls()

        self.refresh_styles()

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def _build_analysis_controls(self) -> None:
        self.setObjectName("BoardControls")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(2, 7, 2, 3)
        outer.setSpacing(0)

        self.nav_toolbar = QWidget()
        toolbar_layout = QHBoxLayout(self.nav_toolbar)
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        toolbar_layout.setSpacing(2)

        self.btn_first = self._make_analysis_button(
            "fa5s.angle-double-left", "⏮", "First move (Home)", self.first_clicked
        )
        self.btn_prev = self._make_analysis_button(
            "fa5s.angle-left", "◀", "Previous move (←)", self.prev_clicked
        )
        self.btn_next = self._make_analysis_button(
            "fa5s.angle-right", "▶", "Next move (→)", self.next_clicked
        )
        self.btn_last = self._make_analysis_button(
            "fa5s.angle-double-right", "⏭", "Last move (End)", self.last_clicked
        )
        self.btn_flip = self._make_analysis_button(
            "fa5s.exchange-alt", "⇄", "Flip board (F)", self.flip_clicked
        )

        for button in (self.btn_first, self.btn_prev, self.btn_next, self.btn_last):
            toolbar_layout.addWidget(button)
        outer.addWidget(self.nav_toolbar)
        outer.addStretch()
        outer.addWidget(self.btn_flip)

    def _build_explorer_controls(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(10)

        self.btn_first = self._make_explorer_button("⏮", self.first_clicked)
        self.btn_prev = self._make_explorer_button("◀", self.prev_clicked)
        self.btn_next = self._make_explorer_button("▶", self.next_clicked)
        self.btn_last = self._make_explorer_button("⏭", self.last_clicked)

        for button in (self.btn_first, self.btn_prev, self.btn_next, self.btn_last):
            layout.addWidget(button)

    def _make_analysis_button(self, icon_name, fallback, tooltip, signal):
        button = Button(
            icon=icon_name if HAS_QTAWESOME else None,
            icon_position="only" if HAS_QTAWESOME else "left",
            variant=ButtonVariant.GHOST,
            size=ButtonSize.SM,
            tooltip=tooltip,
            on_click=lambda: signal.emit(),
        )
        if not HAS_QTAWESOME:
            button.setText(fallback)
        button.setFixedSize(32, 30)
        button.setAccessibleName(tooltip)
        # NoFocus prevents the buttons from stealing keyboard focus when clicked.
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        return button

    def _make_explorer_button(self, text, signal):
        button = Button(
            text,
            ButtonVariant.FILLED,
            ButtonSize.LG,
            on_click=lambda: signal.emit(),
        )
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        return button

    # ------------------------------------------------------------------
    # State
    # ------------------------------------------------------------------

    def set_navigation_state(self, current_index: int, total: int) -> None:
        """Enable the buttons that can move from ``current_index``."""
        has_moves = total > 0
        self.btn_first.setEnabled(has_moves and current_index > -1)
        self.btn_prev.setEnabled(has_moves and current_index > -1)
        self.btn_next.setEnabled(has_moves and current_index < total - 1)
        self.btn_last.setEnabled(has_moves and current_index < total - 1)

    def refresh_styles(self) -> None:
        if self.variant == "analysis":
            self.setStyleSheet(Styles.get_board_controls_style())
        for button in (self.btn_first, self.btn_prev, self.btn_next, self.btn_last):
            button.refresh_styles()
        if self.btn_flip is not None:
            self.btn_flip.refresh_styles()
