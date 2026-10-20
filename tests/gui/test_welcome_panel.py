from unittest.mock import patch

from PyQt6.QtGui import QDesktopServices

from src.constants import ABOUT_URL, APP_VERSION, GITHUB_REPO_URL, WEBSITE_URL
from src.gui.components.welcome_panel import WelcomePanel


def test_welcome_panel_initialization(qapp, qtbot):
    panel = WelcomePanel()
    qtbot.addWidget(panel)

    assert panel.title_label.text() == "Chess Analyzer Pro"
    assert f"v{APP_VERSION}" in panel.version_badge.text()
    assert panel.oss_badge.text() == "Open Source"
    assert "local-first" in panel.desc_label.text()
    assert "Support the Project" in panel.appeal_title.text()

    # Verify all 6 action buttons exist
    assert hasattr(panel, "btn_github")
    assert hasattr(panel, "btn_review")
    assert hasattr(panel, "btn_issue")
    assert hasattr(panel, "btn_feature")
    assert hasattr(panel, "btn_about")
    assert hasattr(panel, "btn_website")

    # Verify refresh_styles does not raise
    panel.refresh_styles()


def test_welcome_panel_links(qapp, qtbot, monkeypatch):
    panel = WelcomePanel()
    qtbot.addWidget(panel)

    opened_urls = []
    monkeypatch.setattr(QDesktopServices, "openUrl", lambda url: opened_urls.append(url.toString()))

    # Click GitHub
    panel.btn_github.click()
    assert GITHUB_REPO_URL in opened_urls

    # Click About
    panel.btn_about.click()
    assert ABOUT_URL in opened_urls

    # Click Website
    panel.btn_website.click()
    assert WEBSITE_URL in opened_urls


def test_welcome_panel_dialog_triggers(qapp, qtbot):
    panel = WelcomePanel()
    qtbot.addWidget(panel)

    with patch("src.gui.dialogs.review_prompt_dialog.ReviewPromptDialog.exec", return_value=0) as mock_review:
        panel.btn_review.click()
        assert mock_review.call_count == 1

    with patch("src.gui.dialogs.feedback_dialog.FeedbackDialog.exec", return_value=0) as mock_fb:
        panel.btn_issue.click()
        assert mock_fb.call_count == 1

    with patch("src.gui.dialogs.feedback_dialog.FeedbackDialog.exec", return_value=0) as mock_feat:
        panel.btn_feature.click()
        assert mock_feat.call_count == 1

