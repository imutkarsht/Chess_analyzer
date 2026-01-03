"""
Update Checker - Checks GitHub releases for new versions.
"""
import requests
from packaging import version
from PyQt6.QtCore import QThread, pyqtSignal
from ..utils.logger import logger

# Current application version (matches your GitHub tag: V1.5)
APP_VERSION = "1.5"

# GitHub API endpoint for latest release
GITHUB_RELEASES_API = "https://api.github.com/repos/imutkarsht/Chess_analyzer/releases/latest"


class UpdateInfo:
    """Container for update information."""
    def __init__(self, available=False, current=APP_VERSION, latest=None, 
                 download_url=None, changelog=None, html_url=None):
        self.available = available
        self.current = current
        self.latest = latest
        self.download_url = download_url
        self.changelog = changelog
        self.html_url = html_url


class UpdateChecker:
    """Synchronous update checker."""
    
    @staticmethod
    def check_for_updates() -> UpdateInfo:
        """Check GitHub for the latest release."""
        try:
            headers = {
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "ChessAnalyzerPro"
            }
            response = requests.get(GITHUB_RELEASES_API, headers=headers, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            # Extract version from tag (e.g., "V1.6" -> "1.6")
            tag_name = data.get("tag_name", "")
            # Handle both uppercase V and lowercase v
            latest_version = tag_name.lstrip("Vv")
            
            # Get download URL (first asset or release page)
            assets = data.get("assets", [])
            download_url = None
            for asset in assets:
                # Prefer Windows executable
                if asset.get("name", "").endswith((".exe", ".zip", ".msi")):
                    download_url = asset.get("browser_download_url")
                    break
            
            # Fallback to release page
            html_url = data.get("html_url", "")
            if not download_url:
                download_url = html_url
            
            # Get changelog from release body
            changelog = data.get("body", "")
            
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
                    html_url=html_url
                )
            else:
                logger.debug(f"App is up to date (v{APP_VERSION})")
                return UpdateInfo(available=False, current=APP_VERSION, latest=latest_version)
                
        except requests.exceptions.RequestException as e:
            logger.warning(f"Failed to check for updates: {e}")
            return UpdateInfo(available=False)
        except Exception as e:
            logger.error(f"Error checking for updates: {e}")
            return UpdateInfo(available=False)


class UpdateCheckerWorker(QThread):
    """Background worker for checking updates without blocking UI."""
    update_checked = pyqtSignal(object)  # Emits UpdateInfo
    
    def run(self):
        result = UpdateChecker.check_for_updates()
        self.update_checked.emit(result)
