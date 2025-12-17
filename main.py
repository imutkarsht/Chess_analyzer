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
        
        # Resource paths
        resource_path = get_resource_path("assets")
        logo_path = os.path.join(resource_path, "images", "logo.png")
        
        # Set App Icon
        if os.path.exists(logo_path):
            from PyQt6.QtGui import QIcon
            app.setWindowIcon(QIcon(logo_path))
            logger.debug(f"App icon set from: {logo_path}")
        else:
            logger.warning(f"App icon not found at: {logo_path}")
            
        # --- Splash Screen Start ---
        from src.gui.splash_screen import SplashScreen
        from PyQt6.QtCore import QThread, QTimer
        import time

        splash = SplashScreen(logo_path)
        splash.show()
        
        # Process events to ensure splash is painted
        app.processEvents()
        
        
        splash.update_progress(10, "Loading configuration...")
        time.sleep(0.3) # Artificial delay for smoothness
        
        splash.update_progress(30, "Initializing core engine...")
        time.sleep(0.3)
        
        splash.update_progress(50, "Loading user interface...")
        
        # Heavy imports could effectively happen here or inside MainWindow
        from src.gui.main_window import MainWindow
        
        splash.update_progress(80, "Preparing dashboard...")
        
        window = MainWindow()
        
        splash.update_progress(95, "Starting up...")
        time.sleep(0.2)
        
        # Show Main Window
        window.show()
        
        splash.update_progress(100, "Done!")
        splash.finish(window)
        # --- Splash Screen End ---

        logger.info("MainWindow shown. Application ready.")
        exit_code = app.exec()
        logger.info(f"Application exiting with code: {exit_code}")
        sys.exit(exit_code)
    except Exception as e:
        logger.critical(f"Unhandled exception: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
