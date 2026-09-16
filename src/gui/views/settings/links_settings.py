"""
Links and Updates Settings group component.
"""
from PyQt6.QtWidgets import QGroupBox, QGridLayout, QApplication
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
        grid = QGridLayout(self)
        grid.setContentsMargins(20, 25, 20, 20)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(10)

        self.website_btn = create_icon_button("Visit Website", "fa5s.globe", self.open_website, self)
        self.update_btn = create_icon_button("Check for Updates", "fa5s.sync-alt", self.check_for_updates, self)
        self.feedback_btn = create_icon_button("Feedback & Bugs", "fa5s.comment-dots", self.open_feedback, self)
        self.rate_btn = create_icon_button("Rate App", "fa5s.star", self.open_review, self)

        grid.addWidget(self.website_btn, 0, 0)
        grid.addWidget(self.update_btn, 0, 1)
        grid.addWidget(self.feedback_btn, 1, 0)
        grid.addWidget(self.rate_btn, 1, 1)

    def open_website(self):
        QDesktopServices.openUrl(QUrl("https://chess-analyzer-ut.vercel.app/"))

    def open_feedback(self):
        from src.gui.dialogs.feedback_dialog import FeedbackDialog
        dialog = FeedbackDialog(self, initial_tab="bug")
        dialog.exec()

    def open_review(self):
        from src.gui.dialogs.review_prompt_dialog import ReviewPromptDialog
        dialog = ReviewPromptDialog(self, games_count=0)
        dialog.exec()

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
            from src.gui.main_window import MainWindow
            MainWindow.toast_from_widget(self, f"Failed to check for updates: {e}", "error")
        finally:
            self.update_btn.setEnabled(True)
            self.update_btn.setText("  Check for Updates")
            if HAS_QTAWESOME:
                self.update_btn.setIcon(qta.icon("fa5s.sync-alt", color=Styles.COLOR_TEXT_SECONDARY))

    def set_advanced_visible(self, visible):
        pass

    def refresh_styles(self, *args, **kwargs):
        self.setStyleSheet(Styles.get_group_box_style())
        if hasattr(self, 'website_btn'):
            self.website_btn.setStyleSheet(Styles.get_settings_default_button_style())
        if hasattr(self, 'feedback_btn'):
            self.feedback_btn.setStyleSheet(Styles.get_settings_default_button_style())
        if hasattr(self, 'rate_btn'):
            self.rate_btn.setStyleSheet(Styles.get_settings_default_button_style())
        if hasattr(self, 'update_btn'):
            self.update_btn.setStyleSheet(Styles.get_settings_default_button_style())
