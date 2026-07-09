import sys
import os
import subprocess
import logging
from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox
from src.gui.main_window import MainWindow
from src.utils.logger import logger
from src.utils.path_utils import get_resource_path
from src.backend.analysis.engine import resolve_engine_path

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
    
    # Set Windows AppUserModelID to ensure taskbar icon displays correctly
    if sys.platform == 'win32':
        try:
            import ctypes
            myappid = 'com.imutkarsht.chessanalyzerpro.2.2.0'
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        except Exception as e:
            pass

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
        from src.gui.dialogs import SplashScreen
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
        
        # macOS Gatekeeper self-fix (only when bundled as .app)
        if getattr(sys, 'frozen', False) and sys.platform == "darwin":
            app_bundle = os.path.dirname(sys.executable)
            while not app_bundle.endswith(".app") and app_bundle != "/":
                app_bundle = os.path.dirname(app_bundle)
            if app_bundle.endswith(".app"):
                result = subprocess.run(
                    ["xattr", "-p", "com.apple.quarantine", app_bundle],
                    capture_output=True, text=True, timeout=5,
                )
                if result.returncode == 0 and result.stdout.strip():
                    subprocess.run(
                        ["xattr", "-dr", "com.apple.quarantine", app_bundle],
                        stderr=subprocess.DEVNULL, timeout=5,
                    )
                    logger.info("Gatekeeper: removed quarantine from .app bundle")
        
        # First-run setup wizard
        if not window.config_manager.get("setup_completed") or resolve_engine_path(window.config_manager) is None:
            from src.gui.dialogs.setup_wizard import SetupWizard
            wizard = SetupWizard(window.config_manager)
            if wizard.exec() == QDialog.DialogCode.Accepted:
                wizard.accepted_data()
                logger.info("Setup wizard completed successfully")
                
                # Reload config to make sure all config instances share the same state
                window.config_manager.reload_config()
                
                # Update MainWindow's engine path and re-initialize analyzer/engine
                new_path = resolve_engine_path(window.config_manager)
                if new_path:
                    window.engine_path = new_path
                    from src.backend.analysis.engine import EngineManager
                    from src.backend.analysis.analyzer import Analyzer
                    try:
                        window.analyzer = Analyzer(
                            EngineManager(window.engine_path, config_manager=window.config_manager)
                        )
                        if hasattr(window, 'move_list_panel'):
                            window.move_list_panel.update_engine_path(new_path)
                        logger.info("MainWindow: Engine and analyzer re-initialized successfully after setup wizard.")
                    except Exception as e:
                        logger.error(f"MainWindow: Failed to initialize engine after setup wizard: {e}")

                if hasattr(window, 'settings_view') and hasattr(window.settings_view, 'reload_from_config'):
                    window.settings_view.reload_from_config()
            else:
                logger.info("Setup wizard skipped")
            window._refresh_engine_status()
        
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
