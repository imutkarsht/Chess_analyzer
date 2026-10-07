"""
Base API class for chess platforms.
Provides shared HTTP request handling and error logging.
"""

from typing import Any

import requests

from src.utils.logger import logger


class BaseChessAPI:
    """Base class for chess platform APIs."""

    DEFAULT_HEADERS = {
        "User-Agent": "ChessAnalyzer/1.0"
    }

    @staticmethod
    def _make_request(
        url: str,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        timeout: int = 30,
    ) -> requests.Response | None:
        """
        Makes an HTTP GET request with error handling.
        Returns Response object or None on failure.
        """
        try:
            final_headers = {**BaseChessAPI.DEFAULT_HEADERS, **(headers or {})}
            response = requests.get(url, headers=final_headers, params=params, timeout=timeout)
            response.raise_for_status()
            return response
        except requests.exceptions.Timeout:
            logger.error(f"Request timeout: {url}")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed for {url}: {e}")
            return None

    @staticmethod
    def _safe_json(response: requests.Response) -> dict | None:
        """Safely parse JSON from response."""
        try:
            return response.json()
        except ValueError:
            logger.error("Failed to parse JSON response")
            return None

    @staticmethod
    def _log_api_error(platform: str, operation: str, error: Exception):
        """Standardized API error logging."""
        logger.error(f"[{platform}] {operation} failed: {error}", exc_info=True)
