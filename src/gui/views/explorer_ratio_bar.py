from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel
from PyQt6.QtCore import Qt

from src.gui.styles import Styles


class RatioBar(QWidget):
    def __init__(self, w_pct, d_pct, b_pct, parent=None):
        super().__init__(parent)
        self.setFixedSize(140, 16)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        only_w = (d_pct == 0 and b_pct == 0)
        only_b = (w_pct == 0 and d_pct == 0)

        if w_pct > 0:
            w_lbl = QLabel(f"{w_pct}%" if w_pct >= 12 else "")
            w_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            w_lbl.setStyleSheet(Styles.get_ratio_bar_segment_style(
                Styles.COLOR_RESULT_WIN,
                top_left=True, bottom_left=True,
                top_right=only_w, bottom_right=only_w
            ))
            layout.addWidget(w_lbl, stretch=w_pct)

        if d_pct > 0:
            d_lbl = QLabel(f"{d_pct}%" if d_pct >= 12 else "")
            d_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            d_lbl.setStyleSheet(Styles.get_ratio_bar_segment_style(
                Styles.COLOR_RESULT_DRAW,
                top_left=(w_pct == 0), bottom_left=(w_pct == 0),
                top_right=(b_pct == 0), bottom_right=(b_pct == 0)
            ))
            layout.addWidget(d_lbl, stretch=d_pct)

        if b_pct > 0:
            b_lbl = QLabel(f"{b_pct}%" if b_pct >= 12 else "")
            b_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            b_lbl.setStyleSheet(Styles.get_ratio_bar_segment_style(
                Styles.COLOR_RESULT_LOSS,
                top_right=True, bottom_right=True,
                top_left=only_b, bottom_left=only_b
            ))
            layout.addWidget(b_lbl, stretch=b_pct)

        self.setToolTip(f"White Wins: {w_pct}%  |  Draws: {d_pct}%  |  Black Wins: {b_pct}%")
