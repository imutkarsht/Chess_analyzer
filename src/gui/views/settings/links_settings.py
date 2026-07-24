"""
Links and Updates Settings group component.
"""
from PyQt6.QtWidgets import QGroupBox, QHBoxLayout, QApplication, QMessageBox
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtCore import QUrl
from ...styles import Styles
from .helpers import create_icon_button, HAS_QTAWESOME

if HAS_QTAWESOME:
    import qtawesome as qta

class LinksSettings(QGroupBox):
    def __init__(self, parent=None):
        super().__init__("Links", parent)
        self.setStyleSheet(Styles.get_group_box_style())
        
        self.setup_ui()

    def setup_ui(self):
        website_layout = QHBoxLayout(self)
        website_layout.setContentsMargins(20, 25, 20, 20)
        website_layout.setSpacing(12)

        self.website_btn = create_icon_button("Visit Website", "fa5s.globe", self.open_website, self)
        website_layout.addWidget(self.website_btn)

        self.feedback_btn = create_icon_button("Feedback", "fa5s.comment-dots", self.open_feedback, self)
        website_layout.addWidget(self.feedback_btn)
        
        self.update_btn = create_icon_button("Check for Updates", "fa5s.sync-alt", self.check_for_updates, self)
        website_layout.addWidget(self.update_btn)

    def open_website(self):
        QDesktopServices.openUrl(QUrl("https://chess-analyzer-ut.vercel.app/"))

    def open_feedback(self):
        QDesktopServices.openUrl(QUrl("https://chess-analyzer-ut.vercel.app/feedback"))

    def check_for_updates(self):
        """Manually check for updates."""
        from src.backend.updater.update_checker import UpdateChecker, APP_VERSION
        from ...dialogs import UpdateNotificationDialog
        
        # Show checking message
        self.update_btn.setEnabled(False)
        self.update_btn.setText("  Checking...")
        QApplication.processEvents()
        
        try:
            update_info = UpdateChecker.check_for_updates()
            
            if update_info.available:
                dialog = UpdateNotificationDialog(update_info, self)
                dialog.exec()
            else:
                from src.gui.main_window import MainWindow
                MainWindow.toast_from_widget(self, f"You're up to date (v{APP_VERSION}).", "success")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to check for updates: {e}")
        finally:
            self.update_btn.setEnabled(True)
            self.update_btn.setText("  Check for Updates")
            if HAS_QTAWESOME:
                self.update_btn.setIcon(qta.icon("fa5s.sync-alt", color=Styles.COLOR_TEXT_SECONDARY))

    def set_advanced_visible(self, visible):
        pass

    def refresh_styles(self, default_style):
        self.setStyleSheet(Styles.get_group_box_style())
        self.website_btn.setStyleSheet(default_style)
        self.feedback_btn.setStyleSheet(default_style)
        self.update_btn.setStyleSheet(default_style)
