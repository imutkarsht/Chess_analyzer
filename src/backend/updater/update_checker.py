"""
Update Checker - Checks GitHub releases for new versions.

Platform asset detection maps the current OS to the naming convention used
by the release pipeline:

  Windows  → ChessAnalyzerPro-X.Y.Z-Windows-Setup.exe   (Inno Setup 6)
  macOS    → ChessAnalyzerPro-X.Y.Z-macOS.dmg            (create-dmg)
  Linux    → ChessAnalyzerPro-X.Y.Z-x86_64.AppImage      (AppImageKit)
"""
import sys
import requests
from packaging import version
from PyQt6.QtCore import QThread, pyqtSignal
from src.utils.logger import logger

from src.constants import APP_VERSION, GITHUB_RELEASES_API, PLATFORM_RULES

_PLATFORM_RULES = PLATFORM_RULES

# Use "linux" rules for any non-win32/darwin platform
_CURRENT_PLATFORM = sys.platform if sys.platform in PLATFORM_RULES else "linux"


def _pick_asset(assets: list) -> tuple[str | None, str, str]:
    """Return (download_url, platform_label, install_hint) for the best matching asset.

    Selection strategy (in order):
      1. Asset name ends with one of the priority suffixes for this OS.
      2. Asset name contains a platform keyword AND ends with a fallback suffix.
      3. Asset name ends with any fallback suffix (first one found).
      4. Falls back to (None, …) — caller should use html_url instead.
    """
    rules = PLATFORM_RULES[_CURRENT_PLATFORM]
    label = rules["label"]
    hint = rules["install_hint"]

    # Pass 1 — priority suffix match (exact installer format)
    for asset in assets:
        name_lower = asset.get("name", "").lower()
        if any(name_lower.endswith(sfx) for sfx in rules["priority_suffixes"]):
            logger.debug(f"Update asset (priority match): {asset['name']}")
            return asset["browser_download_url"], label, hint

    # Pass 2 — keyword + fallback suffix
    for asset in assets:
        name_lower = asset.get("name", "").lower()
        has_keyword = any(kw in name_lower for kw in rules["fallback_keywords"])
        has_suffix = any(name_lower.endswith(sfx) for sfx in rules["fallback_suffixes"])
        if has_keyword and has_suffix:
            logger.debug(f"Update asset (keyword match): {asset['name']}")
            return asset["browser_download_url"], label, hint

    # Pass 3 — any asset with an acceptable suffix
    for asset in assets:
        name_lower = asset.get("name", "").lower()
        if any(name_lower.endswith(sfx) for sfx in rules["fallback_suffixes"]):
            logger.debug(f"Update asset (suffix fallback): {asset['name']}")
            return asset["browser_download_url"], label, hint

    # Nothing found
    return None, label, hint


class UpdateInfo:
    """Container for update information returned by UpdateChecker."""

    def __init__(
        self,
        available: bool = False,
        current: str = APP_VERSION,
        latest: str | None = None,
        download_url: str | None = None,
        changelog: str | None = None,
        html_url: str | None = None,
        platform_label: str = "",
        install_hint: str = "",
    ):
        self.available = available
        self.current = current
        self.latest = latest
        self.download_url = download_url   # Direct asset URL or release page
        self.changelog = changelog
        self.html_url = html_url           # Always the GitHub release page
        self.platform_label = platform_label  # e.g. "Windows Installer (.exe)"
        self.install_hint = install_hint      # One-line user instruction


class UpdateChecker:
    """Synchronous update checker."""

    @staticmethod
    def check_for_updates() -> UpdateInfo:
        """Fetch the latest GitHub release and return an UpdateInfo."""
        try:
            headers = {
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "ChessAnalyzerPro",
            }
            response = requests.get(GITHUB_RELEASES_API, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()

            # Strip leading "V" / "v" from the tag name
            tag_name = data.get("tag_name", "")
            latest_version = tag_name.lstrip("Vv")

            html_url = data.get("html_url", "")
            assets = data.get("assets", [])
            changelog = data.get("body", "")

            # Pick the best platform-matching asset
            download_url, platform_label, install_hint = _pick_asset(assets)
            if not download_url:
                # Fall back to the release page so the user can download manually
                download_url = html_url
                logger.warning(
                    "No platform-specific asset found in release; "
                    "falling back to release page."
                )

            # Compare versions
            try:
                is_newer = version.parse(latest_version) > version.parse(APP_VERSION)
            except Exception:
                is_newer = False

            if is_newer:
                logger.info(f"Update available: {APP_VERSION} -> {latest_version}")
                return UpdateInfo(
                    available=True,
                    current=APP_VERSION,
                    latest=latest_version,
                    download_url=download_url,
                    changelog=changelog,
                    html_url=html_url,
                    platform_label=platform_label,
                    install_hint=install_hint,
                )
            else:
                logger.debug(f"App is up to date (v{APP_VERSION})")
                return UpdateInfo(
                    available=False,
                    current=APP_VERSION,
                    latest=latest_version,
                )

        except requests.exceptions.RequestException as e:
            logger.warning(f"Failed to check for updates: {e}")
            return UpdateInfo(available=False)
        except Exception as e:
            logger.error(f"Error checking for updates: {e}")
            return UpdateInfo(available=False)


class UpdateCheckerWorker(QThread):
    """Background worker — runs UpdateChecker without blocking the UI."""

    update_checked = pyqtSignal(object)  # Emits UpdateInfo

    def run(self):
        result = UpdateChecker.check_for_updates()
        self.update_checked.emit(result)
