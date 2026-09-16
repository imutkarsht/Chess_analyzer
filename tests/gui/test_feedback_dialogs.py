import pytest
from unittest.mock import patch, MagicMock
from PyQt6.QtWidgets import QApplication

from src.gui.components.star_rating_widget import StarRatingWidget
from src.gui.dialogs.review_prompt_dialog import ReviewPromptDialog
from src.gui.dialogs.feedback_dialog import FeedbackDialog
from src.utils.config import ConfigManager


@pytest.fixture
def clean_config(tmp_path):
    ConfigManager._shared_config = None
    ConfigManager._shared_config_path = None
    with patch("src.utils.config.get_user_data_dir", return_value=str(tmp_path)):
        cfg = ConfigManager()
        yield cfg
    ConfigManager._shared_config = None
    ConfigManager._shared_config_path = None


def test_star_rating_widget(qtbot):
    widget = StarRatingWidget(initial_rating=0)
    qtbot.addWidget(widget)

    assert widget.get_rating() == 0

    # Simulate rating change signal
    with qtbot.waitSignal(widget.rating_changed) as blocker:
        widget._on_star_clicked(4)

    assert blocker.args == [4]
    assert widget.get_rating() == 4


def test_review_prompt_dialog_remind_later(qtbot, clean_config):
    clean_config.set("games_analyzed_count", 3)
    dialog = ReviewPromptDialog(games_count=3)
    qtbot.addWidget(dialog)

    dialog._on_remind_later()

    assert clean_config.get("review_next_prompt_count") == 8
    assert clean_config.get("review_submitted") is False


def test_review_prompt_dialog_no_thanks(qtbot, clean_config):
    dialog = ReviewPromptDialog(games_count=3)
    qtbot.addWidget(dialog)

    dialog._on_no_thanks()

    assert clean_config.get("review_prompt_dismissed") is True


@patch("src.backend.services.feedback_service.FeedbackService.submit_review")
def test_review_prompt_dialog_submit_success(mock_submit, qtbot, clean_config):
    mock_submit.return_value = (True, "Review submitted successfully!", {"id": "123"})

    dialog = ReviewPromptDialog(games_count=3)
    qtbot.addWidget(dialog)

    dialog.star_widget.set_rating(5)
    dialog.name_input.setText("Grandmaster99")
    dialog.comment_input.setPlainText("Super fast!")

    dialog._on_submit_review()
    qtbot.waitUntil(lambda: dialog.stacked_widget.currentIndex() == 1, timeout=2000)

    assert clean_config.get("review_submitted") is True
    assert dialog.stacked_widget.currentIndex() == 1


def test_feedback_dialog_tab_switching(qtbot, clean_config):
    dialog = FeedbackDialog(initial_tab="bug")
    qtbot.addWidget(dialog)

    assert dialog.stacked_widget.currentIndex() == 0

    dialog.btn_tab_feature.click()
    assert dialog.stacked_widget.currentIndex() == 1

    dialog.btn_tab_review.click()
    assert dialog.stacked_widget.currentIndex() == 2


@patch("src.backend.services.feedback_service.FeedbackService.submit_bug_report")
def test_feedback_dialog_submit_bug(mock_submit_bug, qtbot, clean_config):
    mock_submit_bug.return_value = (True, "Bug report submitted!", {})

    dialog = FeedbackDialog(initial_tab="bug")
    qtbot.addWidget(dialog)

    dialog.bug_title_input.setText("Test Title")
    dialog.bug_desc_input.setPlainText("Test Description")

    dialog._on_submit()
    qtbot.waitUntil(lambda: dialog.stacked_widget.currentIndex() == 3, timeout=2000)

    assert dialog.stacked_widget.currentIndex() == 3
    mock_submit_bug.assert_called_once()
