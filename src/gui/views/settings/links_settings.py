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
    ABOUT_URL,
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


class LinksSettings(QGroupBox):
    """Project information, credits, links, and update actions."""

    def __init__(self, parent=None):
        super().__init__("About and Links", parent)
        self._link_icons: list[tuple[QWidget, str]] = []
        self.setStyleSheet(Styles.get_group_box_style())
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(18)

        layout.addWidget(self._build_brand_header())
        layout.addWidget(self._build_about_section())
        layout.addWidget(self._divider())
        layout.addWidget(self._build_creator_section())
        layout.addWidget(self._divider())
        layout.addWidget(self._build_links_section())
        layout.addWidget(self._divider())
        layout.addWidget(self._build_support_section())
        layout.addWidget(self._build_footer())
        layout.addStretch(1)
        self.refresh_styles()

    # ------------------------------------------------------------------
    # Layout sections
    # ------------------------------------------------------------------
    def _divider(self) -> QWidget:
        line = QWidget()
        line.setFixedHeight(1)
        self._dividers = getattr(self, "_dividers", [])
        self._dividers.append(line)
        return line

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
        self.logo_label.setFixedSize(80, 80)
        self.logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_path = get_resource_path(os.path.join("assets", "images", "logo.png"))
        if os.path.exists(logo_path):
            self.logo_label.setPixmap(
                QPixmap(logo_path).scaled(
                    80,
                    80,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        brand_layout.addWidget(self.logo_label, 0, Qt.AlignmentFlag.AlignTop)

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(5)

        title_row = QHBoxLayout()
        title_row.setSpacing(8)
        self.title_label = QLabel("Chess Analyzer Pro")
        title_row.addWidget(self.title_label)

        self.version_badge = QLabel(f"v{APP_VERSION}")
        title_row.addWidget(self.version_badge)

        self.license_badge = QLabel("MIT License")
        title_row.addWidget(self.license_badge)
        title_row.addStretch(1)
        text_col.addLayout(title_row)

        self.tagline_label = QLabel(
            "Free, open-source offline Stockfish desktop analyzer for deep, private game review."
        )
        self.tagline_label.setWordWrap(True)
        text_col.addWidget(self.tagline_label)

        self.meta_label = QLabel(
            "Local SQLite history  ·  Opening explorer  ·  Move classifications  ·  "
            "AI Coach  ·  No accounts or telemetry"
        )
        self.meta_label.setWordWrap(True)
        text_col.addWidget(self.meta_label)

        brand_layout.addLayout(text_col, 1)
        return brand

    def _build_about_section(self) -> QWidget:
        section = QWidget()
        section.setStyleSheet(Styles.get_transparent_label_style())
        layout = QVBoxLayout(section)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(self._section_title("About the project"))

        self.about_label = QLabel(
            "Chess Analyzer Pro brings professional-grade analysis to your desktop "
            "without subscriptions or cloud dependencies. Import games from Chess.com, "
            "Lichess, or local PGN files, then review move classifications, accuracy, "
            "opening ideas, tactics, and time management. Stockfish runs locally with "
            "configurable depth and hardware limits, while your history, cached analysis, "
            "and AI Coach explanations stay on your machine."
        )
        self.about_label.setWordWrap(True)
        layout.addWidget(self.about_label)

        self.tech_label = QLabel(
            "Built with Python  ·  PyQt6  ·  Stockfish  ·  SQLite  ·  "
            "OpenAI-compatible AI Coach"
        )
        self.tech_label.setWordWrap(True)
        layout.addWidget(self.tech_label)
        return section

    def _build_creator_section(self) -> QWidget:
        section = QWidget()
        section.setStyleSheet(Styles.get_transparent_label_style())
        layout = QVBoxLayout(section)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        layout.addWidget(self._section_title(f"Created by {AUTHOR_NAME}"))
        self.author_hint = QLabel(
            "Supported by the open-source community. Feedback, bug reports, "
            "and feature ideas are always welcome."
        )
        self.author_hint.setWordWrap(True)
        layout.addWidget(self.author_hint)

        links = QHBoxLayout()
        links.setContentsMargins(0, 2, 0, 0)
        links.setSpacing(18)
        self.author_linkedin_btn = self._make_link(
            "LinkedIn", "fa5b.linkedin", self.open_author_linkedin
        )
        self.author_email_btn = self._make_link(
            "Contact", "fa5s.envelope", self.open_author_email
        )
        links.addWidget(self.author_linkedin_btn)
        links.addWidget(self.author_email_btn)
        links.addStretch(1)
        layout.addLayout(links)
        return section

    def _build_links_section(self) -> QWidget:
        section = QWidget()
        section.setStyleSheet(Styles.get_transparent_label_style())
        layout = QVBoxLayout(section)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(self._section_title("Project links"))

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(28)
        grid.setVerticalSpacing(2)

        self.website_btn = self._make_link(
            "Official Website", "fa5s.globe", self.open_website
        )
        self.docs_btn = self._make_link("Documentation", "fa5s.book", self.open_docs)
        self.github_btn = self._make_link(
            "GitHub Repository", "fa5b.github", self.open_github
        )
        self.releases_btn = self._make_link(
            "Download Releases", "fa5s.download", self.open_releases
        )
        self.about_btn = self._make_link(
            "About Project", "fa5s.info-circle", self.open_about
        )
        self.rate_btn = self._make_link("Rate App", "fa5s.star", self.open_review)

        links = (
            self.website_btn,
            self.docs_btn,
            self.github_btn,
            self.releases_btn,
            self.about_btn,
            self.rate_btn,
        )
        for index, button in enumerate(links):
            button.setMaximumWidth(220)
            grid.addWidget(button, index // 2, index % 2)
        grid.setColumnStretch(2, 1)
        layout.addLayout(grid)
        return section

    def _build_support_section(self) -> QWidget:
        section = QWidget()
        section.setStyleSheet(Styles.get_transparent_label_style())
        layout = QVBoxLayout(section)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(self._section_title("Support and feedback"))

        self.support_label = QLabel(
            "Found a bug, have an idea, or want to help the project? "
            "Use the links below to reach the maintainer and the community."
        )
        self.support_label.setWordWrap(True)
        layout.addWidget(self.support_label)

        links = QHBoxLayout()
        links.setContentsMargins(0, 2, 0, 0)
        links.setSpacing(18)
        self.feedback_btn = self._make_link(
            "Report Issue", "fa5s.bug", self.open_feedback
        )
        self.suggest_btn = self._make_link(
            "Suggest Feature", "fa5s.lightbulb", self.open_suggest_feature
        )
        self.update_btn = self._make_link(
            "Check for Updates", "fa5s.sync-alt", self.check_for_updates
        )
        links.addWidget(self.feedback_btn)
        links.addWidget(self.suggest_btn)
        links.addWidget(self.update_btn)
        links.addStretch(1)
        layout.addLayout(links)
        return section

    def _build_footer(self) -> QWidget:
        footer = QWidget()
        footer.setStyleSheet(Styles.get_transparent_label_style())
        layout = QVBoxLayout(footer)
        layout.setContentsMargins(0, 2, 0, 0)
        layout.setSpacing(2)

        self.license_note = QLabel(
            "Chess Analyzer Pro is released under the MIT License. "
            "Stockfish is licensed under GPLv3."
        )
        self.license_note.setWordWrap(True)
        layout.addWidget(self.license_note)

        self.version_note = QLabel(f"Version {APP_VERSION}  ·  Source available on GitHub")
        self.version_note.setWordWrap(True)
        layout.addWidget(self.version_note)
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
            f"font-size: 22px; font-weight: 700; color: {Styles.COLOR_TEXT_PRIMARY}; "
            + Styles.get_transparent_label_style()
        )
        badge_style = (
            f"background-color: {Styles.COLOR_SURFACE_LIGHT}; "
            f"color: {Styles.COLOR_TEXT_SECONDARY}; "
            f"border: 1px solid {Styles.COLOR_BORDER}; "
            "border-radius: 9px; padding: 2px 8px; font-size: 11px; font-weight: 600;"
        )
        self.version_badge.setStyleSheet(badge_style)
        self.license_badge.setStyleSheet(badge_style)
        self.tagline_label.setStyleSheet(
            f"font-size: 13px; color: {Styles.COLOR_TEXT_SECONDARY}; "
            + Styles.get_transparent_label_style()
        )
        self.meta_label.setStyleSheet(
            f"font-size: 11px; color: {Styles.COLOR_TEXT_MUTED}; "
            + Styles.get_transparent_label_style()
        )
        self.about_label.setStyleSheet(
            f"font-size: 12px; color: {Styles.COLOR_TEXT_SECONDARY}; "
            + Styles.get_transparent_label_style()
        )
        self.tech_label.setStyleSheet(
            f"font-size: 11px; color: {Styles.COLOR_TEXT_MUTED}; "
            + Styles.get_transparent_label_style()
        )
        self.author_hint.setStyleSheet(
            f"font-size: 12px; color: {Styles.COLOR_TEXT_SECONDARY}; "
            + Styles.get_transparent_label_style()
        )
        self.support_label.setStyleSheet(
            f"font-size: 12px; color: {Styles.COLOR_TEXT_SECONDARY}; "
            + Styles.get_transparent_label_style()
        )
        self.license_note.setStyleSheet(
            f"font-size: 11px; color: {Styles.COLOR_TEXT_MUTED}; "
            + Styles.get_transparent_label_style()
        )
        self.version_note.setStyleSheet(
            f"font-size: 11px; color: {Styles.COLOR_TEXT_MUTED}; "
            + Styles.get_transparent_label_style()
        )
        for line in getattr(self, "_dividers", []):
            line.setStyleSheet(f"background-color: {Styles.COLOR_BORDER};")
        for button, icon_name in self._link_icons:
            button.setStyleSheet(Styles.get_settings_link_button_style())
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

    def open_about(self):
        self._open(ABOUT_URL)

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
