"""
Game navigation controls widget.
"""
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QPushButton
from PyQt6.QtCore import pyqtSignal, Qt
from ..styles import Styles
from ..gui_utils import create_button


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
        
        layout.addWidget(self.btn_first)
        layout.addWidget(self.btn_prev)
        layout.addWidget(self.btn_next)
        layout.addWidget(self.btn_last)
        layout.addStretch()
        layout.addWidget(self.btn_flip)
