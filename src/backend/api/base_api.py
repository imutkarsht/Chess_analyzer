"""
Base API class for chess platforms.
Provides shared HTTP request handling and error logging.
"""

from dataclasses import dataclass
from typing import Any, Literal

import requests

from src.constants import APP_VERSION, GITHUB_REPO_URL
from src.utils.logger import logger

ApiStatus = Literal[
    "ok", "not_found", "rate_limited", "unauthorized", "offline", "error"
]

# Avatars are small public profile images; reject anything unexpectedly large
# rather than letting a CDN response bloat the local cache.
MAX_AVATAR_BYTES = 512 * 1024


@dataclass(frozen=True)
class ProfileResult:
    """Normalized profile plus the transport status needed by the GUI."""

    profile: dict | None
    status: ApiStatus
    avatar_bytes: bytes | None = None
    avatar_mime: str | None = None


class BaseChessAPI:
    """Base class for chess platform APIs."""

    DEFAULT_HEADERS = {
        "User-Agent": f"ChessAnalyzerPro/{APP_VERSION} ({GITHUB_REPO_URL})"
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
    def _request_json(
        url: str,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        timeout: int = 30,
    ) -> tuple[Any | None, ApiStatus]:
        """Fetch JSON and classify failures so profile UI can explain them.

        Unlike :meth:`_make_request`, this preserves the distinction between an
        unknown username (404), rate limiting (429), an invalid token (401) and
        a network outage. Existing import paths keep using ``_make_request``.
        """
        try:
            final_headers = {**BaseChessAPI.DEFAULT_HEADERS, **(headers or {})}
            response = requests.get(url, headers=final_headers, params=params, timeout=timeout)
        except requests.exceptions.Timeout:
            logger.warning("API request timed out: %s", url)
            return None, "offline"
        except requests.exceptions.ConnectionError as e:
            logger.warning("API connection failed for %s: %s", url, e)
            return None, "offline"
        except requests.exceptions.RequestException as e:
            logger.error("API request failed for %s: %s", url, e)
            return None, "error"

        if response.status_code == 404:
            return None, "not_found"
        if response.status_code == 429:
            logger.warning("API rate limit hit for %s", url)
            return None, "rate_limited"
        if response.status_code in (401, 403):
            return None, "unauthorized"
        if not response.ok:
            logger.error("API returned HTTP %s for %s", response.status_code, url)
            return None, "error"

        try:
            return response.json(), "ok"
        except ValueError:
            logger.error("Failed to parse JSON response from %s", url)
            return None, "error"

    @staticmethod
    def fetch_avatar(
        url: str | None,
        headers: dict[str, str] | None = None,
        timeout: int = 5,
    ) -> tuple[bytes | None, str | None]:
        """Download a public avatar image, validating type and size.

        Avatar failures are non-fatal: callers fall back to an initials badge
        or to the previously cached image.
        """
        if not url:
            return None, None

        try:
            final_headers = {**BaseChessAPI.DEFAULT_HEADERS, **(headers or {})}
            with requests.get(
                url, headers=final_headers, timeout=timeout, stream=True
            ) as response:
                if response.status_code != 200:
                    return None, None
                mime = (response.headers.get("Content-Type") or "").split(";")[0].strip().lower()
                if not mime.startswith("image/"):
                    return None, None

                chunks: list[bytes] = []
                total = 0
                for chunk in response.iter_content(chunk_size=64 * 1024):
                    if not chunk:
                        continue
                    total += len(chunk)
                    if total > MAX_AVATAR_BYTES:
                        logger.warning("Avatar exceeds size limit, skipping: %s", url)
                        return None, None
                    chunks.append(chunk)
                data = b"".join(chunks)
                return (data, mime) if data else (None, None)
        except requests.exceptions.RequestException as e:
            logger.debug("Avatar download failed for %s: %s", url, e)
            return None, None

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
