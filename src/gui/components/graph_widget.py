from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QVBoxLayout, QWidget

from src.gui.styles import Styles


class GraphWidget(QWidget):
    move_clicked = pyqtSignal(int)

    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)

        self.figure = Figure(figsize=(5, 2.2), dpi=100)
        self.canvas = FigureCanvas(self.figure)
        self.layout.addWidget(self.canvas)
        self.ax = self.figure.add_subplot(111)

        self.setFixedHeight(int(self.figure.get_figheight() * self.figure.get_dpi()))

        # Connect canvas events once to avoid listener accumulation on repeated renders
        self.canvas.mpl_connect("motion_notify_event", self.on_hover)
        self.canvas.mpl_connect("button_press_event", self.on_click)

        self.clear()
