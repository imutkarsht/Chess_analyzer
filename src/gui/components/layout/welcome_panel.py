"""
Empty-state Welcome & Project Hub panel for Chess Analyzer Pro.
Displayed on the right half of the main window when no game is loaded.
"""
import os

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices, QPixmap
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.constants import ABOUT_URL, APP_VERSION, GITHUB_REPO_URL, WEBSITE_URL
from src.gui.components.controls.button import Button, ButtonSize, ButtonVariant
from src.gui.styles import Styles
from src.gui.theme import ThemeManager
from src.utils.path_utils import get_resource_path


class WelcomePanel(QFrame):
    """
    Centered empty-state panel shown on the right half of the split UI when no
    chess game is loaded. Introduces the app, shows the version, appeals for
    open-source support, and links to community pages and feedback dialogs.

    Visual hierarchy:
      1. App identity  — logo + title + neutral badges
      2. Description   — short, readable paragraph
      3. One outlined CTA — Star on GitHub
      4. One hollow CTA — Rate & Review
      5. Four text links — quiet utility actions in a single row
    No element uses a solid accent fill, so the panel never competes with the
    board's Load Game button for attention.
    """

    CARD_WIDTH = 420
    CTA_HEIGHT = 42       # Apple minimum touch target
    TONAL_HEIGHT = 38
    UTIL_HEIGHT = 28

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("WelcomePanel")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._all_buttons: list[Button] = []
        self._setup_ui()

        ThemeManager.instance().theme_changed.connect(lambda _: self.refresh_styles())
        ThemeManager.instance().accent_changed.connect(lambda _: self.refresh_styles())
        self.refresh_styles()

    def _setup_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(24, 24, 24, 24)
        root_layout.setSpacing(0)

        self.card = QWidget()
        self.card.setObjectName("WelcomeCard")
        self.card.setFixedWidth(self.CARD_WIDTH)
        self.card.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)

        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)

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
        card_layout.addSpacing(12)

        # ── Title ─────────────────────────────────────────────────────────
        self.title_label = QLabel("Chess Analyzer Pro")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(self.title_label)
        card_layout.addSpacing(6)

        # ── Badges (both neutral — no accent on badges) ────────────────────
        badges_layout = QHBoxLayout()
        badges_layout.setSpacing(6)
        badges_layout.addStretch(1)

        self.version_badge = QLabel(f"v{APP_VERSION}")
        self.version_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badges_layout.addWidget(self.version_badge)

        self.oss_badge = QLabel("Open Source")
        self.oss_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badges_layout.addWidget(self.oss_badge)

        badges_layout.addStretch(1)
        card_layout.addLayout(badges_layout)
        card_layout.addSpacing(16)

        # ── Description ───────────────────────────────────────────────────
        self.desc_label = QLabel(
            "Free, local-first chess analysis. Unlimited reviews at any depth, "
            "fully offline and private."
        )
        self.desc_label.setWordWrap(True)
        self.desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(self.desc_label)
        card_layout.addSpacing(24)

        # ── Divider ───────────────────────────────────────────────────────
        self.divider = QFrame()
        self.divider.setFrameShape(QFrame.Shape.HLine)
        self.divider.setFrameShadow(QFrame.Shadow.Plain)
        self.divider.setFixedHeight(1)
        card_layout.addWidget(self.divider)
        card_layout.addSpacing(20)

        # ── Outlined CTA: Star on GitHub ───────────────────────────────────
        self.btn_github = Button(
            "Star on GitHub",
            ButtonVariant.OUTLINED,
            icon="fa5b.github",
            full_width=True,
            on_click=self._open_github,
        )
        self.btn_github.setFixedHeight(self.CTA_HEIGHT)
        self._all_buttons.append(self.btn_github)
        card_layout.addWidget(self.btn_github)
        card_layout.addSpacing(8)

        # ── Hollow CTA: Rate & Review (neutral, readable) ─────────────────
        self.btn_review = Button(
            "Rate && Review",
            ButtonVariant.HOLLOW,
            icon="fa5s.star",
            full_width=True,
            on_click=self._open_review,
        )
        self.btn_review.setFixedHeight(self.TONAL_HEIGHT)
        self._all_buttons.append(self.btn_review)
        card_layout.addWidget(self.btn_review)
        card_layout.addSpacing(20)

        # ── Utility links (text-only, one row) ─────────────────────────────
        links = QHBoxLayout()
        links.setSpacing(4)
        links.addStretch(1)

        util_specs = [
            ("Report Issue", "fa5s.bug", self._open_report_issue),
            ("Suggest Feature", "fa5s.lightbulb", self._open_suggest_feature),
            ("About", "fa5s.info-circle", self._open_about),
            ("Website", "fa5s.globe", self._open_website),
        ]
        util_buttons = []
        for label, icon, cb in util_specs:
            btn = Button(
                label,
                ButtonVariant.LINK,
                icon=icon,
                size=ButtonSize.SM,
                on_click=cb,
            )
            btn.setFixedHeight(self.UTIL_HEIGHT)
            self._all_buttons.append(btn)
            util_buttons.append(btn)
            links.addWidget(btn)

        links.addStretch(1)
        card_layout.addLayout(links)

        self.btn_issue, self.btn_feature, self.btn_about, self.btn_website = util_buttons

        # Center the card using stretches — preserves correct word-wrap heights.
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.addStretch(1)
        row.addWidget(self.card)
        row.addStretch(1)

        root_layout.addStretch(1)
        root_layout.addLayout(row)
        root_layout.addStretch(1)

    def refresh_styles(self) -> None:
        """Re-apply theme tokens when the active theme or accent changes."""
        bg = Styles.COLOR_BACKGROUND
        self.setStyleSheet(f"QFrame#WelcomePanel {{ background-color: {bg}; border: none; }}")
        self.card.setStyleSheet(f"QWidget#WelcomeCard {{ background-color: {bg}; }}")

        self.title_label.setStyleSheet(
            f"font-size: 24px; font-weight: 700; "
            f"color: {Styles.COLOR_TEXT_PRIMARY}; background: transparent;"
        )

        # Both badges use the same neutral surface — no accent tinting.
        badge_style = (
            f"background-color: {Styles.COLOR_SURFACE_LIGHT}; "
            f"color: {Styles.COLOR_TEXT_MUTED}; "
            f"border: 1px solid {Styles.COLOR_BORDER}; "
            "border-radius: 10px; padding: 2px 10px; font-size: 11px; font-weight: 500;"
        )
        self.version_badge.setStyleSheet(badge_style)
        self.oss_badge.setStyleSheet(badge_style)

        self.desc_label.setStyleSheet(
            f"font-size: 14px; color: {Styles.COLOR_TEXT_PRIMARY}; background: transparent;"
        )

        self.divider.setStyleSheet(f"background-color: {Styles.COLOR_BORDER}; border: none;")

        for btn in self._all_buttons:
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
