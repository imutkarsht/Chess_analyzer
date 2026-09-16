import pytest
from unittest.mock import patch, MagicMock
from src.backend.services.feedback_service import (
    FeedbackService,
    get_platform_name,
    get_formatted_version,
    get_recent_logs,
)
from src.constants import FEEDBACK_REVIEWS_URL, FEEDBACK_URL, APP_VERSION


@pytest.fixture(autouse=True)
def reset_cooldown():
    FeedbackService._last_submission_times.clear()
    yield
    FeedbackService._last_submission_times.clear()


def test_cooldown_rate_limiting():
    FeedbackService._record_submission("bug")
    success, msg, data = FeedbackService.submit_bug_report(
        title="Spam",
        message="Too fast",
    )
    assert success is False
    assert "Please wait" in msg


def test_get_platform_name():
    with patch("sys.platform", "darwin"):
        assert get_platform_name() == "macos"
    with patch("sys.platform", "win32"):
        assert get_platform_name() == "windows"
    with patch("sys.platform", "linux"):
        assert get_platform_name() == "linux"


def test_get_formatted_version():
    ver = get_formatted_version()
    assert ver.startswith("v")


def test_get_recent_logs_missing_file(tmp_path):
    with patch("src.backend.services.feedback_service.get_user_data_dir", return_value=str(tmp_path)):
        logs = get_recent_logs()
        assert logs == ""


def test_get_recent_logs_truncation(tmp_path):
    log_file = tmp_path / "chess_analyzer.log"
    log_file.write_text("A" * 2000, encoding="utf-8")

    with patch("src.backend.services.feedback_service.get_user_data_dir", return_value=str(tmp_path)):
        logs = get_recent_logs(max_chars=500)
        assert len(logs) <= 500
        assert logs.startswith("...")


@patch("requests.post")
def test_submit_review_success(mock_post):
    mock_resp = MagicMock()
    mock_resp.status_code = 201
    mock_resp.json.return_value = {
        "success": True,
        "message": "Review submitted successfully!",
        "review": {"id": "123", "rating": 5}
    }
    mock_post.return_value = mock_resp

    success, msg, data = FeedbackService.submit_review(
        rating=5,
        comment="Fast analysis!",
        username="Tester",
        platform="macos",
        app_version="v2.2.0"
    )

    assert success is True
    assert "successfully" in msg
    assert data["review"]["id"] == "123"

    mock_post.assert_called_once()
    called_url = mock_post.call_args[0][0]
    called_json = mock_post.call_args[1]["json"]
    assert called_url == FEEDBACK_REVIEWS_URL
    assert called_json["rating"] == 5
    assert called_json["userName"] == "Tester"
    assert called_json["comment"] == "Fast analysis!"
    assert called_json["platform"] == "macos"


@patch("requests.post")
def test_submit_review_failure(mock_post):
    mock_resp = MagicMock()
    mock_resp.status_code = 400
    mock_resp.json.return_value = {
        "success": False,
        "message": "Rating must be between 1 and 5"
    }
    mock_post.return_value = mock_resp

    success, msg, data = FeedbackService.submit_review(rating=0)
    assert success is False
    assert "Rating must be between 1 and 5" in msg


@patch("requests.post")
def test_submit_bug_report(mock_post):
    mock_resp = MagicMock()
    mock_resp.status_code = 201
    mock_resp.json.return_value = {
        "success": True,
        "type": "bug",
        "message": "Bug report logged successfully."
    }
    mock_post.return_value = mock_resp

    success, msg, data = FeedbackService.submit_bug_report(
        title="Crash on startup",
        message="Engine crashed",
        name="Alex",
        email="alex@test.com",
        logs="Traceback error line 10",
        platform="windows"
    )

    assert success is True
    assert data["type"] == "bug"

    called_url = mock_post.call_args[0][0]
    called_json = mock_post.call_args[1]["json"]
    assert called_url == FEEDBACK_URL
    assert called_json["type"] == "bug"
    assert called_json["title"] == "Crash on startup"
    assert called_json["email"] == "alex@test.com"
    assert called_json["logs"] == "Traceback error line 10"


@patch("requests.post")
def test_submit_feature_request(mock_post):
    mock_resp = MagicMock()
    mock_resp.status_code = 201
    mock_resp.json.return_value = {
        "success": True,
        "type": "feature",
        "message": "Feature request logged."
    }
    mock_post.return_value = mock_resp

    success, msg, data = FeedbackService.submit_feature_request(
        title="ECO codes",
        message="Add ECO codes support",
        email="player@test.com",
    )

    assert success is True
    called_json = mock_post.call_args[1]["json"]
    assert called_json["type"] == "feature"
    assert called_json["title"] == "ECO codes"

