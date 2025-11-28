import sys
from PyQt6.QtWidgets import QApplication
from src.gui.main_window import MainWindow
from src.utils.logger import logger

def main():
    logger.info("Application starting...")
    try:
        app = QApplication(sys.argv)
        window = MainWindow()
        window.show()
        logger.info("MainWindow shown.")
        sys.exit(app.exec())
    except Exception as e:
        logger.critical(f"Unhandled exception: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
