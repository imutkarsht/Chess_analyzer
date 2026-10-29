"""
Empty-state Welcome & Project Hub panel for Chess Analyzer Pro.
Displayed on the right half of the main window when no game is loaded.
"""
import os

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices, QPixmap
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.constants import ABOUT_URL, APP_VERSION, GITHUB_REPO_URL, WEBSITE_URL
from src.gui.components.controls.button import Button, ButtonVariant
from src.gui.styles import Styles
from src.gui.theme import ThemeManager
from src.utils.path_utils import get_resource_path


class WelcomePanel(QFrame):
    """
    Centered empty-state panel shown on the right half of the split UI when no
    chess game is loaded. Introduces the app, shows the version, appeals for
    open-source support, and links to community pages and feedback dialogs.
    """

    CARD_WIDTH = 440
    BUTTON_HEIGHT = 40
    GRID_H_GAP = 12
    GRID_V_GAP = 12

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("WelcomePanel")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._buttons: list[tuple[Button, str, bool]] = []
        self._setup_ui()

        ThemeManager.instance().theme_changed.connect(lambda mode: self.refresh_styles())
        ThemeManager.instance().accent_changed.connect(lambda acc: self.refresh_styles())
        self.refresh_styles()

    def _setup_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(24, 24, 24, 24)
        root_layout.setSpacing(0)

        # Card with a FIXED width. A stable width lets the word-wrapped labels
        # report a correct height, which prevents the button rows from being
        # squeezed together or clipped at the bottom.
        self.card = QWidget()
        self.card.setObjectName("WelcomeCard")
        self.card.setFixedWidth(self.CARD_WIDTH)
        self.card.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)

        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(10)

        # ── Logo ──────────────────────────────────────────────────────────
        self.logo_label = QLabel()
        self.logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.logo_label.setStyleSheet("background: transparent;")
        logo_path = get_resource_path(os.path.join("assets", "images", "logo.png"))
        if os.path.exists(logo_path):
            pixmap = QPixmap(logo_path).scaled(
                72,
                72,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.logo_label.setPixmap(pixmap)
        card_layout.addWidget(self.logo_label)

        # ── Title ─────────────────────────────────────────────────────────
        self.title_label = QLabel("Chess Analyzer Pro")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(self.title_label)

        # ── Badges ────────────────────────────────────────────────────────
        badges_layout = QHBoxLayout()
        badges_layout.setSpacing(8)
        badges_layout.addStretch(1)

        self.version_badge = QLabel(f"v{APP_VERSION}")
        self.version_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badges_layout.addWidget(self.version_badge)

        self.oss_badge = QLabel("Open Source")
        self.oss_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badges_layout.addWidget(self.oss_badge)

        badges_layout.addStretch(1)
        card_layout.addLayout(badges_layout)
        card_layout.addSpacing(6)

        # ── Description ───────────────────────────────────────────────────
        self.desc_label = QLabel(
            "A free, local-first chess analysis app. Get unlimited game reviews at any "
            "engine depth, import games from multiple sources, explore your game history, "
            "and track detailed statistics, all analyzed privately on your own machine "
            "and fully offline."
        )
        self.desc_label.setWordWrap(True)
        self.desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(self.desc_label)
        card_layout.addSpacing(8)

        # ── Divider ───────────────────────────────────────────────────────
        self.divider = QFrame()
        self.divider.setFrameShape(QFrame.Shape.HLine)
        self.divider.setFrameShadow(QFrame.Shadow.Plain)
        self.divider.setFixedHeight(1)
        card_layout.addWidget(self.divider)
        card_layout.addSpacing(8)

        # ── Support appeal ────────────────────────────────────────────────
        self.appeal_title = QLabel("Support the Project")
        self.appeal_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(self.appeal_title)

        self.appeal_text = QLabel(
            "Chess Analyzer Pro is open-source and maintained with passion. "
            "If you find it helpful, supporting the project takes just a few seconds!"
        )
        self.appeal_text.setWordWrap(True)
        self.appeal_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(self.appeal_text)
        card_layout.addSpacing(10)

        # ── Action buttons (2 equal columns, clear gaps) ──────────────────
        grid = QGridLayout()
        grid.setHorizontalSpacing(self.GRID_H_GAP)
        grid.setVerticalSpacing(self.GRID_V_GAP)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)

        self.btn_github = self._create_action_button(
            "Star on GitHub", "fa5b.github", self._open_github, highlight=True
        )
        self.btn_review = self._create_action_button(
            "Rate && Review", "fa5s.star", self._open_review, highlight=True
        )
        self.btn_issue = self._create_action_button(
            "Report Issue", "fa5s.bug", self._open_report_issue
        )
        self.btn_feature = self._create_action_button(
            "Suggest Feature", "fa5s.lightbulb", self._open_suggest_feature
        )
        self.btn_about = self._create_action_button(
            "About Project", "fa5s.info-circle", self._open_about
        )
        self.btn_website = self._create_action_button(
            "Visit Website", "fa5s.globe", self._open_website
        )

        grid.addWidget(self.btn_github, 0, 0)
        grid.addWidget(self.btn_review, 0, 1)
        grid.addWidget(self.btn_issue, 1, 0)
        grid.addWidget(self.btn_feature, 1, 1)
        grid.addWidget(self.btn_about, 2, 0)
        grid.addWidget(self.btn_website, 2, 1)
        card_layout.addLayout(grid)

        # Center the card horizontally AND vertically. No alignment flags are
        # used on the card itself; stretches do the centering so the layout can
        # still compute the correct height for wrapped text.
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.addStretch(1)
        row.addWidget(self.card)
        row.addStretch(1)

        root_layout.addStretch(1)
        root_layout.addLayout(row)
        root_layout.addStretch(1)

    def _create_action_button(
        self,
        text: str,
        icon_name: str,
        callback,
        highlight: bool = False,
    ) -> Button:
        """Create a quick-action button with centered icon and text."""
        variant = ButtonVariant.TONAL if highlight else ButtonVariant.FILLED
        btn = Button(text, variant, icon=icon_name, full_width=True, on_click=callback)
        btn.setFixedHeight(self.BUTTON_HEIGHT)
        self._buttons.append((btn, icon_name, highlight))
        return btn

    def refresh_styles(self) -> None:
        """Re-apply theme tokens when the active theme or accent changes."""
        bg = Styles.COLOR_BACKGROUND
        self.setStyleSheet(f"QFrame#WelcomePanel {{ background-color: {bg}; border: none; }}")
        self.card.setStyleSheet(f"QWidget#WelcomeCard {{ background-color: {bg}; }}")

        self.title_label.setStyleSheet(
            f"font-size: 24px; font-weight: 700; color: {Styles.COLOR_TEXT_PRIMARY}; "
            "background: transparent;"
        )

        badge_style = (
            f"background-color: {Styles.COLOR_SURFACE_LIGHT}; "
            f"color: {Styles.COLOR_TEXT_SECONDARY}; "
            f"border: 1px solid {Styles.COLOR_BORDER}; "
            "border-radius: 10px; padding: 2px 10px; font-size: 11px; font-weight: 600;"
        )
        self.version_badge.setStyleSheet(badge_style)
        self.oss_badge.setStyleSheet(badge_style)

        self.desc_label.setStyleSheet(
            f"font-size: 13px; color: {Styles.COLOR_TEXT_SECONDARY}; background: transparent;"
        )

        self.divider.setStyleSheet(f"background-color: {Styles.COLOR_BORDER}; border: none;")

        self.appeal_title.setStyleSheet(
            f"font-size: 15px; font-weight: 600; color: {Styles.COLOR_TEXT_PRIMARY}; "
            "background: transparent;"
        )
        self.appeal_text.setStyleSheet(
            f"font-size: 12px; color: {Styles.COLOR_TEXT_MUTED}; background: transparent;"
        )

        for btn, _icon_name, _is_highlight in self._buttons:
            btn.refresh_styles()

    # ── Action callbacks ──────────────────────────────────────────────────
    def _open_github(self) -> None:
        QDesktopServices.openUrl(QUrl(GITHUB_REPO_URL))

    def _open_review(self) -> None:
        from src.gui.dialogs.review_prompt_dialog import ReviewPromptDialog

        dialog = ReviewPromptDialog(self, games_count=0)
        dialog.exec()

    def _open_report_issue(self) -> None:
        from src.gui.dialogs.feedback_dialog import FeedbackDialog

        dialog = FeedbackDialog(self, initial_tab="bug")
        dialog.exec()

    def _open_suggest_feature(self) -> None:
        from src.gui.dialogs.feedback_dialog import FeedbackDialog

        dialog = FeedbackDialog(self, initial_tab="feature")
        dialog.exec()

    def _open_about(self) -> None:
        QDesktopServices.openUrl(QUrl(ABOUT_URL))

    def _open_website(self) -> None:
        QDesktopServices.openUrl(QUrl(WEBSITE_URL))
