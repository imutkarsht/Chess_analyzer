"""
Service for sending in-app reviews, bug reports, and feature suggestions
to the Chess Analyzer Pro API (chessanalyzer.xyz).
"""

import os
import sys
import time
from typing import Any

import requests
from PyQt6.QtCore import QThread, pyqtSignal

from src.constants import (
    APP_VERSION,
    FEEDBACK_REVIEWS_URL,
    FEEDBACK_URL,
)
from src.utils.logger import logger
from src.utils.path_utils import get_user_data_dir


def get_platform_name() -> str:
    """Return normalized platform name: windows, macos, or linux."""
    if sys.platform.startswith("win"):
        return "windows"
    elif sys.platform.startswith("darwin"):
        return "macos"
    return "linux"


def get_formatted_version() -> str:
    """Return version string with 'v' prefix, e.g. v2.3.0."""
    return f"v{APP_VERSION}" if not APP_VERSION.startswith("v") else APP_VERSION


def get_recent_logs(max_chars: int = 1000) -> str:
    """
    Retrieve the last chunk of lines from the local log file,
    truncated to max_chars.
    """
    try:
        log_file = os.path.join(get_user_data_dir(), "chess_analyzer.log")
        if not os.path.exists(log_file):
            return ""

        with open(log_file, encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

        # Take the most recent lines
        recent = "".join(lines[-50:])
        if len(recent) > max_chars:
            recent = "..." + recent[-max_chars + 3:]
        return recent.strip()
    except Exception as e:
        logger.warning(f"FeedbackService: Failed to read log excerpt: {e}")
        return ""


class FeedbackService:
    """
    Handles API communication with chessanalyzer.xyz for:
      - Reviews (POST /api/reviews)
      - Bug Reports (POST /api/feedback, type=bug)
      - Feature Requests (POST /api/feedback, type=feature)
    """

    _last_submission_times = {}
    COOLDOWN_SECONDS = 10  # Anti-spam delay between submissions

    @classmethod
    def _check_cooldown(cls, action_type: str) -> str | None:
        now = time.time()
        last_time = cls._last_submission_times.get(action_type, 0)
        elapsed = now - last_time
        if elapsed < cls.COOLDOWN_SECONDS:
            wait_s = int(cls.COOLDOWN_SECONDS - elapsed) + 1
            return f"Please wait {wait_s} second{'s' if wait_s > 1 else ''} before submitting again."
        return None

    @classmethod
    def _record_submission(cls, action_type: str):
        cls._last_submission_times[action_type] = time.time()

    @classmethod
    def _post_feedback(
        cls,
        url: str,
        payload: dict[str, Any],
        action_type: str,
        *,
        log_label: str,
        success_message: str,
        timeout_message: str,
        timeout: int,
    ) -> tuple[bool, str, dict[str, Any]]:
        try:
            logger.info(f"FeedbackService: Submitting {log_label} to {url}")
            resp = requests.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=timeout,
            )

            try:
                data = resp.json()
            except Exception:
                data = {"raw": resp.text}

            if resp.status_code in (200, 201):
                cls._record_submission(action_type)
                msg = data.get("message", success_message)
                logger.info(
                    f"FeedbackService: {log_label.capitalize()} submitted successfully: {msg}"
                )
                return True, msg, data

            err_msg = (
                data.get("message")
                or data.get("error")
                or f"Server returned code {resp.status_code}"
            )
            logger.warning(
                f"FeedbackService: {log_label.capitalize()} returned error: {err_msg}"
            )
            return False, err_msg, data

        except requests.exceptions.Timeout:
            logger.error(f"FeedbackService: {log_label.capitalize()} timed out.")
            return False, timeout_message, {}
        except requests.exceptions.RequestException as e:
            logger.error(f"FeedbackService: Network error submitting {log_label}: {e}")
            return False, f"Could not connect to server: {e}", {}
        except Exception as e:
            logger.error(
                f"FeedbackService: Unexpected error submitting {log_label}: {e}"
            )
            return False, f"An unexpected error occurred: {e}", {}

    @classmethod
    def submit_review(
        cls,
        rating: int,
        comment: str = "",
        username: str = "",
        platform: str | None = None,
        app_version: str | None = None,
        timeout: int = 10,
    ) -> tuple[bool, str, dict[str, Any]]:
        """
        Submit star rating & review.
        Returns (success: bool, user_message: str, response_data: dict).
        """
        cooldown_err = cls._check_cooldown("review")
        if cooldown_err:
            return False, cooldown_err, {}

        payload = {
            "rating": int(rating),
            "comment": (comment.strip()[:2000]) if comment else "",
            "userName": (username.strip()[:80]) if username else "",
            "platform": platform or get_platform_name(),
            "appVersion": app_version or get_formatted_version(),
        }

        return cls._post_feedback(
            FEEDBACK_REVIEWS_URL,
            payload,
            "review",
            log_label="review",
            success_message=(
                "Review submitted successfully! Thank you for your feedback."
            ),
            timeout_message=(
                "Connection timed out. Please check your internet connection "
                "and try again."
            ),
            timeout=timeout,
        )

    @classmethod
    def submit_bug_report(
        cls,
        title: str,
        message: str,
        name: str = "",
        email: str = "",
        logs: str = "",
        platform: str | None = None,
        app_version: str | None = None,
        timeout: int = 10,
    ) -> tuple[bool, str, dict[str, Any]]:
        """
        Submit a bug report.
        Returns (success: bool, user_message: str, response_data: dict).
        """
        cooldown_err = cls._check_cooldown("bug")
        if cooldown_err:
            return False, cooldown_err, {}

        payload = {
            "type": "bug",
            "title": (title.strip()[:150]) if title else "Bug Report",
            "message": message.strip()[:3000],
            "name": (name.strip()[:80]) if name else "Anonymous",
            "email": (email.strip()[:150]) if email else "",
            "platform": platform or get_platform_name(),
            "appVersion": app_version or get_formatted_version(),
            "logs": logs[:1000] if logs else "",
        }

        return cls._post_feedback(
            FEEDBACK_URL,
            payload,
            "bug",
            log_label="bug report",
            success_message=(
                "Bug report logged successfully. Thank you for helping us fix issues!"
            ),
            timeout_message=(
                "Connection timed out. Please check your internet connection."
            ),
            timeout=timeout,
        )

    @classmethod
    def submit_feature_request(
        cls,
        title: str,
        message: str,
        name: str = "",
        email: str = "",
        platform: str | None = None,
        app_version: str | None = None,
        timeout: int = 10,
    ) -> tuple[bool, str, dict[str, Any]]:
        """
        Submit a feature request.
        Returns (success: bool, user_message: str, response_data: dict).
        """
        cooldown_err = cls._check_cooldown("feature")
        if cooldown_err:
            return False, cooldown_err, {}

        payload = {
            "type": "feature",
            "title": (title.strip()[:150]) if title else "Feature Request",
            "message": message.strip()[:3000],
            "name": (name.strip()[:80]) if name else "Anonymous",
            "email": (email.strip()[:150]) if email else "",
            "platform": platform or get_platform_name(),
            "appVersion": app_version or get_formatted_version(),
        }

        return cls._post_feedback(
            FEEDBACK_URL,
            payload,
            "feature",
            log_label="feature request",
            success_message=(
                "Feature request submitted successfully. Thank you for your suggestion!"
            ),
            timeout_message=(
                "Connection timed out. Please check your internet connection."
            ),
            timeout=timeout,
        )

    @staticmethod
    def fetch_community_reviews(limit: int = 5, timeout: int = 5) -> tuple[bool, dict[str, Any]]:
        """
        Fetch community reviews & rating stats.
        Returns (success: bool, data: dict).
        """
        try:
            url = f"{FEEDBACK_REVIEWS_URL}?limit={limit}"
            resp = requests.get(url, timeout=timeout)
            if resp.status_code == 200:
                return True, resp.json()
            return False, {}
        except Exception as e:
            logger.warning(f"FeedbackService: Failed to fetch community reviews: {e}")
            return False, {}


class FeedbackWorker(QThread):
    """
    QThread worker to submit feedback / reviews asynchronously without
    blocking the PyQt GUI event loop.
    """

    finished = pyqtSignal(bool, str, dict)  # success, message, data

    def __init__(self, target_callable, *args, **kwargs):
        super().__init__()
        self._callable = target_callable
        self._args = args
        self._kwargs = kwargs

    def run(self):
        try:
            success, msg, data = self._callable(*self._args, **self._kwargs)
            self.finished.emit(success, msg, data)
        except Exception as e:
            logger.error(f"FeedbackWorker exception: {e}")
            self.finished.emit(False, f"Error: {e}", {})
