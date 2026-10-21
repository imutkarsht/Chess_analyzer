"""
Variation bar — the small toolbar shown above the board while exploring a line.
"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy

from src.gui.styles import Styles


class VariationBar(QFrame):
    """Compact banner: variation moves on the left, actions on the right."""

    play_best_requested = pyqtSignal()
    undo_requested = pyqtSignal()
    reset_requested = pyqtSignal()
    exit_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("VariationBar")
        self.setVisible(False)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(8)

        self.lbl_badge = QLabel("Variation")
        self.lbl_badge.setStyleSheet(
            Styles.get_label_style(size=11, weight=700, color=Styles.COLOR_ACCENT)
            + " "
            + Styles.get_transparent_label_style()
        )
        layout.addWidget(self.lbl_badge)

        self.lbl_moves = QLabel("")
        self.lbl_moves.setStyleSheet(
            Styles.get_label_style(size=12, color=Styles.COLOR_TEXT_SECONDARY)
            + " "
            + Styles.get_transparent_label_style()
        )
        self.lbl_moves.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.lbl_moves.setMinimumWidth(40)
        layout.addWidget(self.lbl_moves, 1)

        self.btn_best = self._make_button("Play best", self.play_best_requested)
        self.btn_undo = self._make_button("Undo", self.undo_requested)
        self.btn_reset = self._make_button("Reset", self.reset_requested)
        self.btn_exit = self._make_button("Exit", self.exit_requested)
        self.btn_exit.setToolTip("Leave the variation and return to the game (Esc)")
        for btn in (self.btn_best, self.btn_undo, self.btn_reset, self.btn_exit):
            layout.addWidget(btn)

        self.refresh_styles()

    def _make_button(self, text: str, signal) -> QPushButton:
        btn = QPushButton(text)
        btn.setFixedHeight(26)
        btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        # QPushButton.clicked always carries a bool; these signals take no args.
        btn.clicked.connect(lambda _checked=False, sig=signal: sig.emit())
        return btn

    def set_state(self, moves_text: str, can_undo: bool, can_play_best: bool) -> None:
        self.lbl_moves.setText(moves_text or "Play a move to start branching")
        self.lbl_moves.setToolTip(moves_text)
        self.btn_undo.setEnabled(can_undo)
        self.btn_reset.setEnabled(can_undo)
        self.btn_best.setEnabled(can_play_best)

    def refresh_styles(self) -> None:
        self.setStyleSheet(f"""
            QFrame#VariationBar {{
                background-color: {Styles.COLOR_SURFACE_LIGHT};
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 8px;
            }}
            QLabel {{ background: transparent; border: none; }}
        """)
        outline = Styles.get_outline_button_style()
        for btn in (self.btn_best, self.btn_undo, self.btn_reset, self.btn_exit):
            btn.setStyleSheet(outline)
