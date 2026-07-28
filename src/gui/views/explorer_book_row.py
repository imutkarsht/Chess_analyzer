from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt


class BookRowWidget(QWidget):
    def __init__(self, san, on_click=None, parent=None):
        super().__init__(parent)
        self.san = san
        self.on_click = on_click
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.on_click:
            self.on_click(self.san)
