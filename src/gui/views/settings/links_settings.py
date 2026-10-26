"""About, links, and update actions."""

import os

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from src.constants import (
    APP_VERSION,
    AUTHOR_EMAIL,
    AUTHOR_LINKEDIN_URL,
    AUTHOR_NAME,
    GITHUB_REPO_URL,
    WEBSITE_URL,
)
from src.utils.path_utils import get_resource_path

from ...styles import Styles
from .helpers import HAS_QTAWESOME, create_icon_button

if HAS_QTAWESOME:
    import qtawesome as qta

LINK_COLUMNS = 4


class LinksSettings(QGroupBox):
    """Project information, links, and update actions."""

    def __init__(self, parent=None):
        super().__init__("About", parent)
        self._link_icons: list[tuple[QWidget, str]] = []
        self.setStyleSheet(Styles.get_group_box_style())
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(22)

        layout.addWidget(self._build_brand_header())
        layout.addWidget(self._build_links_section())
        layout.addWidget(self._build_footer())
        layout.addStretch(1)
        self.refresh_styles()

    # ------------------------------------------------------------------
    # Layout sections
    # ------------------------------------------------------------------
    def _section_title(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet(
            f"font-size: 14px; font-weight: 600; color: {Styles.COLOR_TEXT_PRIMARY}; "
            + Styles.get_transparent_label_style()
        )
        return label

    def _build_brand_header(self) -> QWidget:
        brand = QWidget()
        brand.setStyleSheet(Styles.get_transparent_label_style())
        brand_layout = QHBoxLayout(brand)
        brand_layout.setContentsMargins(0, 0, 0, 0)
        brand_layout.setSpacing(16)

        self.logo_label = QLabel()
        self.logo_label.setFixedSize(64, 64)
        self.logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_path = get_resource_path(os.path.join("assets", "images", "logo.png"))
        if os.path.exists(logo_path):
            self.logo_label.setPixmap(
                QPixmap(logo_path).scaled(
                    64,
                    64,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        brand_layout.addWidget(self.logo_label, 0, Qt.AlignmentFlag.AlignTop)

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(3)

        title_row = QHBoxLayout()
        title_row.setSpacing(8)
        self.title_label = QLabel("Chess Analyzer Pro")
        title_row.addWidget(self.title_label)

        self.version_badge = QLabel(f"v{APP_VERSION}")
        title_row.addWidget(self.version_badge)

        title_row.addStretch(1)
        text_col.addLayout(title_row)

        self.tagline_label = QLabel(
            "Offline Stockfish analysis with local history and an optional AI Coach."
        )
        self.tagline_label.setWordWrap(True)
        text_col.addWidget(self.tagline_label)

        brand_layout.addLayout(text_col, 1)
        return brand

    def _build_links_section(self) -> QWidget:
        section = QWidget()
        section.setStyleSheet(Styles.get_transparent_label_style())
        layout = QVBoxLayout(section)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(self._section_title("Links"))

        self.website_btn = self._make_link(
            "Website", "fa5s.globe", self.open_website
        )
        self.docs_btn = self._make_link("Documentation", "fa5s.book", self.open_docs)
        self.github_btn = self._make_link(
            "GitHub", "fa5b.github", self.open_github
        )
        self.releases_btn = self._make_link(
            "Releases", "fa5s.download", self.open_releases
        )
        self.feedback_btn = self._make_link(
            "Report Issue", "fa5s.bug", self.open_feedback
        )
        self.suggest_btn = self._make_link(
            "Suggest Feature", "fa5s.lightbulb", self.open_suggest_feature
        )
        self.update_btn = self._make_link(
            "Check for Updates", "fa5s.sync-alt", self.check_for_updates
        )
        self.rate_btn = self._make_link("Rate App", "fa5s.star", self.open_review)

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(20)
        grid.setVerticalSpacing(2)
        for index, button in enumerate(
            (
                self.website_btn,
                self.docs_btn,
                self.github_btn,
                self.releases_btn,
                self.feedback_btn,
                self.suggest_btn,
                self.update_btn,
                self.rate_btn,
            )
        ):
            grid.addWidget(button, index // LINK_COLUMNS, index % LINK_COLUMNS)
        grid.setColumnStretch(LINK_COLUMNS, 1)
        layout.addLayout(grid)
        return section

    def _build_footer(self) -> QWidget:
        footer = QWidget()
        footer.setStyleSheet(Styles.get_transparent_label_style())
        layout = QVBoxLayout(footer)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        creator_row = QHBoxLayout()
        creator_row.setContentsMargins(0, 0, 0, 0)
        creator_row.setSpacing(10)
        self.creator_label = QLabel(f"Created by {AUTHOR_NAME}")
        creator_row.addWidget(self.creator_label)
        self.author_linkedin_btn = self._make_link(
            "LinkedIn", "fa5b.linkedin", self.open_author_linkedin
        )
        self.author_email_btn = self._make_link(
            "Contact", "fa5s.envelope", self.open_author_email
        )
        creator_row.addWidget(self.author_linkedin_btn)
        creator_row.addWidget(self.author_email_btn)
        creator_row.addStretch(1)
        layout.addLayout(creator_row)

        self.license_note = QLabel(
            "MIT License  ·  Stockfish is licensed under GPLv3"
        )
        self.license_note.setWordWrap(True)
        layout.addWidget(self.license_note)
        return footer

    def _make_link(self, text: str, icon_name: str, callback) -> QWidget:
        button = create_icon_button(text, icon_name, callback, self)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._link_icons.append((button, icon_name))
        return button

    # ------------------------------------------------------------------
    # Styling
    # ------------------------------------------------------------------
    def refresh_styles(self, *args, **kwargs):
        self.setStyleSheet(Styles.get_group_box_style())
        self.title_label.setStyleSheet(
            f"font-size: 20px; font-weight: 700; color: {Styles.COLOR_TEXT_PRIMARY}; "
            + Styles.get_transparent_label_style()
        )
        badge_style = (
            f"background-color: {Styles.COLOR_SURFACE_LIGHT}; "
            f"color: {Styles.COLOR_TEXT_SECONDARY}; "
            f"border: 1px solid {Styles.COLOR_BORDER}; "
            "border-radius: 9px; padding: 2px 8px; font-size: 11px; font-weight: 600;"
        )
        self.version_badge.setStyleSheet(badge_style)
        self.tagline_label.setStyleSheet(
            f"font-size: 12px; color: {Styles.COLOR_TEXT_SECONDARY}; "
            + Styles.get_transparent_label_style()
        )
        self.creator_label.setStyleSheet(
            f"font-size: 12px; color: {Styles.COLOR_TEXT_SECONDARY}; "
            + Styles.get_transparent_label_style()
        )
        self.license_note.setStyleSheet(
            f"font-size: 11px; color: {Styles.COLOR_TEXT_MUTED}; "
            + Styles.get_transparent_label_style()
        )
        for button, icon_name in self._link_icons:
            button.refresh_styles()
            if HAS_QTAWESOME:
                qta_icon = qta.icon(icon_name, color=Styles.COLOR_TEXT_SECONDARY)
                button.setIcon(qta_icon)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def _open(self, url: str):
        QDesktopServices.openUrl(QUrl(url))

    def open_website(self):
        self._open(WEBSITE_URL)

    def open_docs(self):
        self._open(f"{WEBSITE_URL}/docs")

    def open_github(self):
        self._open(GITHUB_REPO_URL)

    def open_releases(self):
        self._open(f"{WEBSITE_URL}/releases")

    def open_author_linkedin(self):
        self._open(AUTHOR_LINKEDIN_URL)

    def open_author_email(self):
        self._open(f"mailto:{AUTHOR_EMAIL}")

    def open_feedback(self):
        from src.gui.dialogs.feedback_dialog import FeedbackDialog

        FeedbackDialog(self, initial_tab="bug").exec()

    def open_suggest_feature(self):
        from src.gui.dialogs.feedback_dialog import FeedbackDialog

        FeedbackDialog(self, initial_tab="feature").exec()

    def open_review(self):
        from src.gui.dialogs.review_prompt_dialog import ReviewPromptDialog

        ReviewPromptDialog(self, games_count=0).exec()

    def check_for_updates(self):
        """Manually check for updates."""
        from src.backend.updater.update_checker import APP_VERSION, UpdateChecker

        from ...dialogs import UpdateNotificationDialog

        self.update_btn.setEnabled(False)
        self.update_btn.setText("  Checking...")
        QApplication.processEvents()

        try:
            update_info = UpdateChecker.check_for_updates()

            if update_info.available:
                UpdateNotificationDialog(update_info, self).exec()
            else:
                from src.gui.main_window import MainWindow

                MainWindow.toast_from_widget(
                    self, f"You're up to date (v{APP_VERSION}).", "success"
                )
        except Exception as e:
            from src.gui.main_window import MainWindow

            MainWindow.toast_from_widget(
                self, f"Failed to check for updates: {e}", "error"
            )
        finally:
            self.update_btn.setEnabled(True)
            self.update_btn.setText("  Check for Updates")
            if HAS_QTAWESOME:
                self.update_btn.setIcon(
                    qta.icon("fa5s.sync-alt", color=Styles.COLOR_TEXT_SECONDARY)
                )

    def set_advanced_visible(self, visible):
        pass
