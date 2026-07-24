"""
Game navigation controls widget.
"""
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QPushButton
from PyQt6.QtCore import pyqtSignal, Qt
from src.gui.styles import Styles
from src.gui.utils.gui_utils import create_button


class GameControlsWidget(QWidget):
    """Widget with navigation controls for stepping through game moves."""
    
    first_clicked = pyqtSignal()
    prev_clicked = pyqtSignal()
    next_clicked = pyqtSignal()
    last_clicked = pyqtSignal()
    flip_clicked = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 10, 0, 10)
        layout.setSpacing(10)
        
        self.btn_first = create_button("<<", style="secondary", on_click=self.first_clicked.emit)
        self.btn_prev = create_button("<", style="secondary", on_click=self.prev_clicked.emit)
        self.btn_next = create_button(">", style="secondary", on_click=self.next_clicked.emit)
        self.btn_last = create_button(">>", style="secondary", on_click=self.last_clicked.emit)
        self.btn_flip = create_button("Flip", style="secondary", on_click=self.flip_clicked.emit)

        # NoFocus prevents the buttons from stealing keyboard focus when clicked.
        # Without this, clicking a button grabs focus away from the main window,
        # so the very next arrow-key press goes to the button rather than the
        # keyPressEvent handler — making navigation feel like it needs two clicks.
        for btn in (self.btn_first, self.btn_prev, self.btn_next,
                    self.btn_last, self.btn_flip):
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        
        layout.addWidget(self.btn_first)
        layout.addWidget(self.btn_prev)
        layout.addWidget(self.btn_next)
        layout.addWidget(self.btn_last)
        layout.addStretch()
        layout.addWidget(self.btn_flip)

    def refresh_styles(self):
        from src.gui.styles import Styles
        style = Styles.get_control_button_style()
        for btn in (self.btn_first, self.btn_prev, self.btn_next,
                    self.btn_last, self.btn_flip):
            btn.setStyleSheet(style)
