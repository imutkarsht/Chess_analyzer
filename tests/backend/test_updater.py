"""Tests for the GitHub update checker and platform asset resolution rules."""
from unittest.mock import patch, MagicMock
from src.backend.updater.update_checker import UpdateChecker, _pick_asset, UpdateInfo
from src.constants import APP_VERSION


def test_pick_asset_darwin():
    """On macOS, .dmg installers take priority."""
    assets = [
        {"name": "ChessAnalyzerPro-2.3.0-Windows-Setup.exe", "browser_download_url": "http://win.exe"},
        {"name": "ChessAnalyzerPro-2.3.0-macOS.dmg", "browser_download_url": "http://mac.dmg"},
        {"name": "ChessAnalyzerPro-2.3.0.zip", "browser_download_url": "http://zip.zip"},
    ]
    with patch("src.backend.updater.update_checker._CURRENT_PLATFORM", "darwin"):
        url, label, hint = _pick_asset(assets)
        assert url == "http://mac.dmg"
        assert "macOS" in label


def test_pick_asset_windows():
    """On Windows, .exe Setup installers take priority."""
    assets = [
        {"name": "ChessAnalyzerPro-2.3.0-macOS.dmg", "browser_download_url": "http://mac.dmg"},
        {"name": "ChessAnalyzerPro-2.3.0-Windows-Setup.exe", "browser_download_url": "http://win.exe"},
    ]
    with patch("src.backend.updater.update_checker._CURRENT_PLATFORM", "win32"):
        url, label, hint = _pick_asset(assets)
        assert url == "http://win.exe"
        assert "Windows" in label


def test_check_for_updates_newer_version():
    """When a higher semver release exists on GitHub, update is marked available."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "tag_name": "v99.0.0",
        "body": "Major release notes",
        "html_url": "https://github.com/repo/releases/v99.0.0",
        "assets": [
            {"name": "ChessAnalyzerPro-99.0.0-macOS.dmg", "browser_download_url": "http://dl.dmg"},
        ],
    }

    with patch("requests.get", return_value=mock_resp):
        with patch("src.backend.updater.update_checker._CURRENT_PLATFORM", "darwin"):
            info = UpdateChecker.check_for_updates()
            assert info.available is True
            assert info.latest == "99.0.0"
            assert info.changelog == "Major release notes"


def test_check_for_updates_same_or_older_version():
    """When the release version is same or older, available is False."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "tag_name": f"v{APP_VERSION}",
        "body": "Current release",
        "html_url": "https://github.com/repo/releases",
        "assets": [],
    }

    with patch("requests.get", return_value=mock_resp):
        info = UpdateChecker.check_for_updates()
        assert info.available is False

