import sys
import os
import logging
from PyQt6.QtWidgets import QApplication, QMessageBox
from src.gui.main_window import MainWindow
from src.utils.logger import logger
from src.utils.path_utils import get_resource_path

def main():
    logger.info("Application starting...")
    try:
        app = QApplication(sys.argv)
        
        # Set App Icon
        resource_path = get_resource_path("assets")
        logo_path = os.path.join(resource_path, "images", "logo.png")
        if os.path.exists(logo_path):
            from PyQt6.QtGui import QIcon
            app.setWindowIcon(QIcon(logo_path))
        
        window = MainWindow()
        window.show()
        logger.info("MainWindow shown.")
        sys.exit(app.exec())
    except Exception as e:
        logger.critical(f"Unhandled exception: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
