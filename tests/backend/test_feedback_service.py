from unittest.mock import MagicMock, patch

import pytest
import requests

from src.backend.services.feedback_service import (
    FeedbackService,
    FeedbackWorker,
    get_formatted_version,
    get_platform_name,
    get_recent_logs,
)
from src.constants import FEEDBACK_REVIEWS_URL, FEEDBACK_URL


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


@pytest.mark.parametrize(
    "submit",
    [
        lambda: FeedbackService.submit_review(5, comment="great"),
        lambda: FeedbackService.submit_bug_report("Crash", "Details"),
        lambda: FeedbackService.submit_feature_request("Idea", "Details"),
    ],
)
def test_submission_timeout_is_reported(mocker, submit):
    mocker.patch(
        "requests.post", side_effect=requests.exceptions.Timeout("timed out")
    )

    success, msg, data = submit()

    assert success is False
    assert "timed out" in msg.lower()
    assert data == {}


@pytest.mark.parametrize(
    "submit",
    [
        lambda: FeedbackService.submit_review(5),
        lambda: FeedbackService.submit_bug_report("Crash", "Details"),
        lambda: FeedbackService.submit_feature_request("Idea", "Details"),
    ],
)
def test_submission_network_error_is_reported(mocker, submit):
    mocker.patch(
        "requests.post",
        side_effect=requests.exceptions.ConnectionError("offline"),
    )

    success, msg, data = submit()

    assert success is False
    assert "Could not connect" in msg
    assert data == {}


@pytest.mark.parametrize(
    "submit",
    [
        lambda: FeedbackService.submit_review(5),
        lambda: FeedbackService.submit_bug_report("Crash", "Details"),
        lambda: FeedbackService.submit_feature_request("Idea", "Details"),
    ],
)
def test_submission_unexpected_error_is_reported(mocker, submit):
    mocker.patch("requests.post", side_effect=RuntimeError("boom"))

    success, msg, data = submit()

    assert success is False
    assert "unexpected error" in msg.lower()
    assert data == {}


def test_non_json_error_response_uses_status_code(mocker):
    response = mocker.Mock(status_code=500)
    response.json.side_effect = ValueError("html")
    response.text = "<html>server error</html>"
    mocker.patch("requests.post", return_value=response)

    success, msg, data = FeedbackService.submit_bug_report("Crash", "Details")

    assert success is False
    assert msg == "Server returned code 500"
    assert data == {"raw": "<html>server error</html>"}


def test_bug_payload_is_truncated_and_defaulted(mocker):
    response = mocker.Mock(status_code=201)
    response.json.return_value = {"message": "ok"}
    post = mocker.patch("requests.post", return_value=response)

    FeedbackService.submit_bug_report(
        title="T" * 200,
        message="M" * 4000,
        logs="L" * 2000,
    )

    payload = post.call_args.kwargs["json"]
    assert len(payload["title"]) == 150
    assert len(payload["message"]) == 3000
    assert len(payload["logs"]) == 1000
    assert payload["name"] == "Anonymous"
    assert payload["email"] == ""


def test_feature_title_defaults_when_blank(mocker):
    response = mocker.Mock(status_code=200)
    response.json.return_value = {}
    post = mocker.patch("requests.post", return_value=response)

    FeedbackService.submit_feature_request("", "Details")

    assert post.call_args.kwargs["json"]["title"] == "Feature Request"


def test_successful_submission_starts_cooldown(mocker):
    response = mocker.Mock(status_code=201)
    response.json.return_value = {}
    mocker.patch("requests.post", return_value=response)

    assert FeedbackService.submit_review(5)[0] is True
    success, msg, _ = FeedbackService.submit_review(4)

    assert success is False
    assert "Please wait" in msg


class TestFetchCommunityReviews:
    def test_success_returns_payload(self, mocker):
        response = mocker.Mock(status_code=200)
        response.json.return_value = {"reviews": [{"rating": 5}]}
        get = mocker.patch("requests.get", return_value=response)

        success, data = FeedbackService.fetch_community_reviews(limit=3)

        assert success is True
        assert data == {"reviews": [{"rating": 5}]}
        assert "limit=3" in get.call_args.args[0]

    def test_non_200_returns_empty(self, mocker):
        mocker.patch("requests.get", return_value=mocker.Mock(status_code=500))

        assert FeedbackService.fetch_community_reviews() == (False, {})

    def test_network_error_returns_empty(self, mocker):
        mocker.patch(
            "requests.get", side_effect=requests.exceptions.ConnectionError("offline")
        )

        assert FeedbackService.fetch_community_reviews() == (False, {})


class TestFeedbackWorker:
    def test_emits_callable_result(self, qapp):
        worker = FeedbackWorker(lambda value: (True, value, {"v": value}), "done")
        emitted = []
        worker.finished.connect(lambda *args: emitted.append(args))

        worker.run()

        assert emitted == [(True, "done", {"v": "done"})]

    def test_emits_failure_when_callable_raises(self, qapp):
        def boom():
            raise RuntimeError("exploded")

        worker = FeedbackWorker(boom)
        emitted = []
        worker.finished.connect(lambda *args: emitted.append(args))

        worker.run()

        assert emitted == [(False, "Error: exploded", {})]

