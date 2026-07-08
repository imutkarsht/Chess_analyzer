import sys
import os
import tarfile
import zipfile
import tempfile
import pytest
from unittest.mock import MagicMock, patch

from src.backend.engine.downloader import (
    get_current_platform,
    get_expected_asset_name,
    get_official_releases,
    get_download_url,
    download_and_extract,
    ReleaseAsset,
    PLATFORM_ASSETS,
)


class TestGetCurrentPlatform:
    def test_darwin_arm64(self, mocker):
        mocker.patch.object(sys, "platform", "darwin")
        mocker.patch("platform.machine", return_value="arm64")
        assert get_current_platform() == ("darwin", "arm64")

    def test_darwin_x86_64(self, mocker):
        mocker.patch.object(sys, "platform", "darwin")
        mocker.patch("platform.machine", return_value="x86_64")
        assert get_current_platform() == ("darwin", "x86_64")

    def test_win32(self, mocker):
        mocker.patch.object(sys, "platform", "win32")
        assert get_current_platform() == ("win32", "x86_64")

    def test_linux(self, mocker):
        mocker.patch.object(sys, "platform", "linux")
        mocker.patch("platform.machine", return_value="x86_64")
        assert get_current_platform() == ("linux", "x86_64")

    def test_unsupported_platform_raises(self, mocker):
        mocker.patch.object(sys, "platform", "cygwin")
        with pytest.raises(RuntimeError, match="Unsupported platform"):
            get_current_platform()


class TestGetExpectedAssetName:
    def test_macos_universal(self, mocker):
        mocker.patch.object(sys, "platform", "darwin")
        mocker.patch("platform.machine", return_value="arm64")
        assert get_expected_asset_name() == "stockfish-macos-m1-apple-silicon.tar"

    def test_windows_universal(self, mocker):
        mocker.patch.object(sys, "platform", "win32")
        assert get_expected_asset_name() == "stockfish-windows-x86-64-avx2.zip"

    def test_linux_universal(self, mocker):
        mocker.patch.object(sys, "platform", "linux")
        mocker.patch("platform.machine", return_value="x86_64")
        assert get_expected_asset_name() == "stockfish-ubuntu-x86-64-avx2.tar"


class TestGetOfficialReleases:
    def test_returns_list_of_assets(self, mocker):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "assets": [
                {"name": "stockfish-macos-m1-apple-silicon.tar",
                 "browser_download_url": "https://example.com/a.tar.gz",
                 "size": 12345},
            ]
        }
        mocker.patch("requests.get", return_value=mock_resp)

        assets = get_official_releases()
        assert len(assets) == 1
        assert assets[0].name == "stockfish-macos-m1-apple-silicon.tar"
        assert assets[0].url == "https://example.com/a.tar.gz"
        assert assets[0].size == 12345

    def test_raises_on_http_error(self, mocker):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = Exception("HTTP 404")
        mocker.patch("requests.get", return_value=mock_resp)

        with pytest.raises(Exception, match="HTTP 404"):
            get_official_releases()


class TestGetDownloadUrl:
    def test_finds_matching_asset(self):
        releases = [
            ReleaseAsset("a.tar.gz", "https://example.com/a.tar.gz", 100),
            ReleaseAsset("b.zip", "https://example.com/b.zip", 200),
        ]
        url = get_download_url(releases, "b.zip")
        assert url == "https://example.com/b.zip"

    def test_returns_none_when_not_found(self):
        releases = [ReleaseAsset("a.tar.gz", "https://example.com/a.tar.gz", 100)]
        url = get_download_url(releases, "nonexistent.zip")
        assert url is None


class TestDownloadAndExtract:
    def create_tar_fixture(self, tmp_path, binary_name="stockfish"):
        """Create a .tar.gz with a Stockfish binary inside and return its path."""
        archive = tmp_path / "test.tar.gz"
        inner_dir = tmp_path / "stockfish_dir"
        inner_dir.mkdir()
        binary = inner_dir / binary_name
        binary.write_text("fake stockfish binary")
        binary.chmod(0o755)

        with tarfile.open(str(archive), "w:gz") as tf:
            tf.add(str(inner_dir), arcname="stockfish_dir")

        return str(archive), str(binary)

    def create_zip_fixture(self, tmp_path, binary_name="stockfish.exe"):
        """Create a .zip with a Stockfish binary inside and return its path."""
        archive = tmp_path / "test.zip"
        inner_dir = tmp_path / "stockfish_dir"
        inner_dir.mkdir()
        binary = inner_dir / binary_name
        binary.write_text("fake stockfish binary")

        with zipfile.ZipFile(str(archive), "w") as zf:
            zf.write(str(binary), arcname=f"stockfish_dir/{binary_name}")

        return str(archive), str(binary)

    def test_download_and_extract_tar_gz(self, mocker, tmp_path):
        archive_path, expected_binary = self.create_tar_fixture(tmp_path)

        mock_resp = MagicMock()
        mock_resp.headers = {"content-length": "1000"}
        mock_resp.iter_content.return_value = [
            open(archive_path, "rb").read()
        ]

        mocker.patch("requests.get", return_value=mock_resp)
        dest = str(tmp_path / "dest")
        result = download_and_extract("https://example.com/test.tar.gz", dest)

        assert os.path.isfile(result)
        assert result.endswith("stockfish")
        assert os.access(result, os.X_OK)

    def test_download_and_extract_zip(self, mocker, tmp_path):
        archive_path, expected_binary = self.create_zip_fixture(tmp_path)

        mock_resp = MagicMock()
        mock_resp.headers = {"content-length": "1000"}
        mock_resp.iter_content.return_value = [
            open(archive_path, "rb").read()
        ]

        mocker.patch("requests.get", return_value=mock_resp)
        mocker.patch.object(sys, "platform", "win32")
        dest = str(tmp_path / "dest")
        result = download_and_extract("https://example.com/test.zip", dest)

        assert os.path.isfile(result)
        assert result.endswith("stockfish.exe")

    def test_progress_callback_called(self, mocker, tmp_path):
        archive_path, _ = self.create_tar_fixture(tmp_path)

        mock_resp = MagicMock()
        mock_resp.headers = {"content-length": str(os.path.getsize(archive_path))}
        mock_resp.iter_content.return_value = [
            open(archive_path, "rb").read()
        ]

        mocker.patch("requests.get", return_value=mock_resp)

        callback = MagicMock()
        download_and_extract(
            "https://example.com/test.tar.gz",
            str(tmp_path / "dest2"),
            progress_callback=callback,
        )

        callback.assert_called()

    def test_raises_on_download_failure(self, mocker, tmp_path):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = Exception("Download failed")
        mocker.patch("requests.get", return_value=mock_resp)

        with pytest.raises(Exception, match="Download failed"):
            download_and_extract(
                "https://example.com/test.tar.gz",
                str(tmp_path / "dest3"),
            )
