"""
Service for sending in-app reviews, bug reports, and feature suggestions
to the Chess Analyzer Pro API (chessanalyzer.xyz).
"""
import os
import sys
import requests
from typing import Optional, Tuple, Dict, Any
from PyQt6.QtCore import QThread, pyqtSignal

from src.constants import (
    APP_VERSION,
    FEEDBACK_API_BASE,
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
    """Return version string with 'v' prefix, e.g. v2.2.0."""
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

        with open(log_file, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

        # Take the most recent lines
        recent = "".join(lines[-50:])
        if len(recent) > max_chars:
            recent = "..." + recent[-max_chars + 3:]
        return recent.strip()
    except Exception as e:
        logger.warning(f"FeedbackService: Failed to read log excerpt: {e}")
        return ""


import time

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
    def _check_cooldown(cls, action_type: str) -> Optional[str]:
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

    @staticmethod
    def submit_review(
        rating: int,
        comment: str = "",
        username: str = "",
        platform: Optional[str] = None,
        app_version: Optional[str] = None,
        timeout: int = 10,
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Submit star rating & review.
        Returns (success: bool, user_message: str, response_data: dict).
        """
        cooldown_err = FeedbackService._check_cooldown("review")
        if cooldown_err:
            return False, cooldown_err, {}

        payload = {
            "rating": int(rating),
            "comment": (comment.strip()[:2000]) if comment else "",
            "userName": (username.strip()[:80]) if username else "",
            "platform": platform or get_platform_name(),
            "appVersion": app_version or get_formatted_version(),
        }

        try:
            logger.info(f"FeedbackService: Submitting review (rating={rating}) to {FEEDBACK_REVIEWS_URL}")
            resp = requests.post(
                FEEDBACK_REVIEWS_URL,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=timeout,
            )

            try:
                data = resp.json()
            except Exception:
                data = {"raw": resp.text}

            if resp.status_code in (200, 201):
                FeedbackService._record_submission("review")
                msg = data.get("message", "Review submitted successfully! Thank you for your feedback.")
                logger.info(f"FeedbackService: Review submitted successfully: {msg}")
                return True, msg, data
            else:
                err_msg = data.get("message") or data.get("error") or f"Server returned code {resp.status_code}"
                logger.warning(f"FeedbackService: Review submission returned error: {err_msg}")
                return False, err_msg, data

        except requests.exceptions.Timeout:
            logger.error("FeedbackService: Review submission timed out.")
            return False, "Connection timed out. Please check your internet connection and try again.", {}
        except requests.exceptions.RequestException as e:
            logger.error(f"FeedbackService: Network error submitting review: {e}")
            return False, f"Could not connect to server: {e}", {}
        except Exception as e:
            logger.error(f"FeedbackService: Unexpected error submitting review: {e}")
            return False, f"An unexpected error occurred: {e}", {}

    @staticmethod
    def submit_bug_report(
        title: str,
        message: str,
        name: str = "",
        email: str = "",
        logs: str = "",
        platform: Optional[str] = None,
        app_version: Optional[str] = None,
        timeout: int = 10,
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Submit a bug report.
        Returns (success: bool, user_message: str, response_data: dict).
        """
        cooldown_err = FeedbackService._check_cooldown("bug")
        if cooldown_err:
            return False, cooldown_err, {}

        # Ensure logs string is not exceeding 1000 chars
        truncated_logs = logs[:1000] if logs else ""

        payload = {
            "type": "bug",
            "title": (title.strip()[:150]) if title else "Bug Report",
            "message": message.strip()[:3000],
            "name": (name.strip()[:80]) if name else "Anonymous",
            "email": (email.strip()[:150]) if email else "",
            "platform": platform or get_platform_name(),
            "appVersion": app_version or get_formatted_version(),
            "logs": truncated_logs,
        }

        try:
            logger.info(f"FeedbackService: Submitting bug report to {FEEDBACK_URL}")
            resp = requests.post(
                FEEDBACK_URL,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=timeout,
            )

            try:
                data = resp.json()
            except Exception:
                data = {"raw": resp.text}

            if resp.status_code in (200, 201):
                FeedbackService._record_submission("bug")
                msg = data.get("message", "Bug report logged successfully. Thank you for helping us fix issues!")
                logger.info(f"FeedbackService: Bug report logged: {msg}")
                return True, msg, data
            else:
                err_msg = data.get("message") or data.get("error") or f"Server returned code {resp.status_code}"
                logger.warning(f"FeedbackService: Bug report returned error: {err_msg}")
                return False, err_msg, data

        except requests.exceptions.Timeout:
            logger.error("FeedbackService: Bug report timed out.")
            return False, "Connection timed out. Please check your internet connection.", {}
        except requests.exceptions.RequestException as e:
            logger.error(f"FeedbackService: Network error submitting bug report: {e}")
            return False, f"Could not connect to server: {e}", {}
        except Exception as e:
            logger.error(f"FeedbackService: Unexpected error submitting bug report: {e}")
            return False, f"An unexpected error occurred: {e}", {}

    @staticmethod
    def submit_feature_request(
        title: str,
        message: str,
        name: str = "",
        email: str = "",
        platform: Optional[str] = None,
        app_version: Optional[str] = None,
        timeout: int = 10,
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Submit a feature request.
        Returns (success: bool, user_message: str, response_data: dict).
        """
        cooldown_err = FeedbackService._check_cooldown("feature")
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

        try:
            logger.info(f"FeedbackService: Submitting feature request to {FEEDBACK_URL}")
            resp = requests.post(
                FEEDBACK_URL,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=timeout,
            )

            try:
                data = resp.json()
            except Exception:
                data = {"raw": resp.text}

            if resp.status_code in (200, 201):
                FeedbackService._record_submission("feature")
                msg = data.get("message", "Feature request submitted successfully. Thank you for your suggestion!")
                logger.info(f"FeedbackService: Feature request logged: {msg}")
                return True, msg, data
            else:
                err_msg = data.get("message") or data.get("error") or f"Server returned code {resp.status_code}"
                logger.warning(f"FeedbackService: Feature request returned error: {err_msg}")
                return False, err_msg, data

        except requests.exceptions.Timeout:
            logger.error("FeedbackService: Feature request timed out.")
            return False, "Connection timed out. Please check your internet connection.", {}
        except requests.exceptions.RequestException as e:
            logger.error(f"FeedbackService: Network error submitting feature request: {e}")
            return False, f"Could not connect to server: {e}", {}
        except Exception as e:
            logger.error(f"FeedbackService: Unexpected error submitting feature request: {e}")
            return False, f"An unexpected error occurred: {e}", {}

    @staticmethod
    def fetch_community_reviews(limit: int = 5, timeout: int = 5) -> Tuple[bool, Dict[str, Any]]:
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

