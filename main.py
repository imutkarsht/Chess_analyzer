import sys
import os
import logging
from PyQt6.QtWidgets import QApplication, QMessageBox
from src.gui.main_window import MainWindow
from src.utils.logger import logger
from src.utils.path_utils import get_resource_path

from PyQt6.QtCore import qInstallMessageHandler, QtMsgType

def qt_message_handler(mode, context, message):
    # Suppress specific QFont warning
    if "QFont::setPointSize: Point size <= 0" in message:
        return
    
    # Default behavior for other messages
    if mode == QtMsgType.QtInfoMsg:
        mode_str = "Info"
    elif mode == QtMsgType.QtWarningMsg:
        mode_str = "Warning"
    elif mode == QtMsgType.QtCriticalMsg:
        mode_str = "Critical"
    elif mode == QtMsgType.QtFatalMsg:
        mode_str = "Fatal"
    else:
        mode_str = "Debug"
        
    # We can print to stderr or use our logger. 
    # Since we have a logger, let's try to use it or just print to keep it simple and avoid recursion if logger uses Qt
    print(f"Qt {mode_str}: {message}")

def main():
    qInstallMessageHandler(qt_message_handler)
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
