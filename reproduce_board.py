import sys
from PyQt6.QtWidgets import QApplication, QMainWindow
from src.gui.board_widget import BoardWidget

def run():
    app = QApplication(sys.argv)
    window = QMainWindow()
    window.resize(800, 800)
    widget = BoardWidget()
    window.setCentralWidget(widget)
    window.show()
    print("Window shown. Check if board is visible.")
    # app.exec() # We can't block, but this verifies instantiation.

if __name__ == "__main__":
    run()
