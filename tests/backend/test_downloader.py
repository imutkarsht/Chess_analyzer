import sys
import os
import tarfile
import zipfile
import tempfile
import pytest
from unittest.mock import MagicMock, patch

from src.backend.engine import downloader
from src.backend.engine.downloader import (
    get_current_platform,
    get_expected_asset_name,
    get_official_releases,
    get_download_url,
    get_download_candidates,
    select_asset,
    select_assets,
    download_and_extract,
    probe_engine_binary,
    try_package_manager_install,
    ReleaseAsset,
    PLATFORM_ASSETS,
)


def _asset(name, url=None):
    return ReleaseAsset(name, url or f"https://example.com/{name}", 100)


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

    def test_linux_aarch64_normalized(self, mocker):
        mocker.patch.object(sys, "platform", "linux")
        mocker.patch("platform.machine", return_value="aarch64")
        assert get_current_platform() == ("linux", "arm64")

    def test_linux_amd64_normalized(self, mocker):
        mocker.patch.object(sys, "platform", "linux")
        mocker.patch("platform.machine", return_value="AMD64")
        assert get_current_platform() == ("linux", "x86_64")

    def test_unsupported_platform_raises(self, mocker):
        mocker.patch.object(sys, "platform", "cygwin")
        with pytest.raises(RuntimeError, match="Unsupported platform"):
            get_current_platform()


class TestGetExpectedAssetName:
    def test_macos_universal(self, mocker):
        mocker.patch.object(sys, "platform", "darwin")
        mocker.patch("platform.machine", return_value="arm64")
        assert get_expected_asset_name() == "stockfish-macos-universal.tar.gz"

    def test_windows_universal(self, mocker):
        mocker.patch.object(sys, "platform", "win32")
        assert get_expected_asset_name() == "stockfish-windows-x86-64-universal.zip"

    def test_linux_universal(self, mocker):
        mocker.patch.object(sys, "platform", "linux")
        mocker.patch("platform.machine", return_value="x86_64")
        assert get_expected_asset_name() == "stockfish-linux-x86-64-universal.tar.gz"


class TestSelectAssets:
    def _patch_platform(self, mocker, system, arch):
        mocker.patch(
            "src.backend.engine.downloader.get_current_platform",
            return_value=(system, arch),
        )

    def test_new_linux_x86_64_naming(self, mocker):
        self._patch_platform(mocker, "linux", "x86_64")
        releases = [
            _asset("stockfish-linux-arm64-universal.tar.gz"),
            _asset("stockfish-linux-riscv64-universal.tar.gz"),
            _asset("stockfish-linux-x86-64-universal.tar.gz"),
        ]
        best = select_asset(releases)
        assert best.name == "stockfish-linux-x86-64-universal.tar.gz"

    def test_new_linux_arm64_naming(self, mocker):
        self._patch_platform(mocker, "linux", "arm64")
        releases = [
            _asset("stockfish-linux-x86-64-universal.tar.gz"),
            _asset("stockfish-linux-arm64-universal.tar.gz"),
        ]
        assert select_asset(releases).name == "stockfish-linux-arm64-universal.tar.gz"

    def test_new_linux_riscv64_naming(self, mocker):
        self._patch_platform(mocker, "linux", "riscv64")
        releases = [
            _asset("stockfish-linux-x86-64-universal.tar.gz"),
            _asset("stockfish-linux-riscv64-universal.tar.gz"),
        ]
        assert select_asset(releases).name == "stockfish-linux-riscv64-universal.tar.gz"

    def test_legacy_ubuntu_naming_still_resolves(self, mocker):
        self._patch_platform(mocker, "linux", "x86_64")
        releases = [_asset("stockfish-ubuntu-x86-64-avx2.tar")]
        assert select_asset(releases).name == "stockfish-ubuntu-x86-64-avx2.tar"

    def test_legacy_macos_naming(self, mocker):
        self._patch_platform(mocker, "darwin", "arm64")
        releases = [_asset("stockfish-macos-m1-apple-silicon.tar")]
        assert select_asset(releases).name == "stockfish-macos-m1-apple-silicon.tar"

    def test_universal_preferred_when_no_exact_arch(self, mocker):
        self._patch_platform(mocker, "darwin", "arm64")
        releases = [_asset("stockfish-macos-universal.tar.gz")]
        assert select_asset(releases).name == "stockfish-macos-universal.tar.gz"

    def test_android_assets_excluded(self, mocker):
        self._patch_platform(mocker, "linux", "arm64")
        releases = [
            _asset("stockfish-android-arm64-universal.tar.gz"),
            _asset("stockfish-linux-arm64-universal.tar.gz"),
        ]
        assert select_asset(releases).name == "stockfish-linux-arm64-universal.tar.gz"

    def test_arch_mismatch_excluded(self, mocker):
        self._patch_platform(mocker, "linux", "arm64")
        releases = [_asset("stockfish-linux-x86-64-universal.tar.gz")]
        assert select_asset(releases) is None

    def test_no_match_returns_none(self, mocker):
        self._patch_platform(mocker, "linux", "x86_64")
        releases = [_asset("stockfish-macos-universal.tar.gz")]
        assert select_asset(releases) is None

    def test_ranked_list_ordering(self, mocker):
        self._patch_platform(mocker, "linux", "x86_64")
        releases = [
            _asset("stockfish-linux-x86-64.tar"),
            _asset("stockfish-linux-x86-64-universal.tar.gz"),
        ]
        names = [a.name for a in select_assets(releases)]
        assert names[0] == "stockfish-linux-x86-64-universal.tar.gz"

    def test_armv8_maps_to_arm64(self, mocker):
        self._patch_platform(mocker, "linux", "arm64")
        releases = [_asset("stockfish-linux-armv8.tar.gz")]
        assert select_asset(releases).name == "stockfish-linux-armv8.tar.gz"

    def test_armv8_skipped_on_x86_64(self, mocker):
        self._patch_platform(mocker, "linux", "x86_64")
        releases = [_asset("stockfish-linux-armv8.tar.gz")]
        assert select_asset(releases) is None

    def test_archless_name_is_skipped(self, mocker):
        self._patch_platform(mocker, "linux", "x86_64")
        releases = [_asset("stockfish-linux.tar.gz")]
        assert select_asset(releases) is None

    def test_unsupported_arch_is_skipped(self, mocker):
        self._patch_platform(mocker, "linux", "x86_64")
        releases = [
            _asset("stockfish-linux-ppc64le.tar.gz"),
            _asset("stockfish-linux-s390x.tar.gz"),
        ]
        assert select_asset(releases) is None

    def test_tar_zst_container_ranked(self, mocker):
        self._patch_platform(mocker, "linux", "x86_64")
        releases = [_asset("stockfish-linux-x86-64.tar.zst")]
        assert select_asset(releases).name == "stockfish-linux-x86-64.tar.zst"

    def test_distro_alias_maps_to_linux(self, mocker):
        self._patch_platform(mocker, "linux", "x86_64")
        releases = [_asset("stockfish-fedora-x86-64.tar.gz")]
        assert select_asset(releases).name == "stockfish-fedora-x86-64.tar.gz"


class TestGetOfficialReleases:
    def test_returns_list_of_assets(self, mocker):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "assets": [
                {"name": "stockfish-macos-universal.tar.gz",
                 "browser_download_url": "https://example.com/a.tar.gz",
                 "size": 12345},
            ]
        }
        mocker.patch("requests.get", return_value=mock_resp)

        assets = get_official_releases()
        assert len(assets) == 1
        assert assets[0].name == "stockfish-macos-universal.tar.gz"
        assert assets[0].url == "https://example.com/a.tar.gz"
        assert assets[0].size == 12345

    def test_raises_on_http_error(self, mocker):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = Exception("HTTP 404")
        mocker.patch("requests.get", return_value=mock_resp)

        with pytest.raises(Exception, match="HTTP 404"):
            get_official_releases()


class TestGetDownloadUrl:
    def test_finds_exact_matching_asset(self):
        releases = [
            ReleaseAsset("a.tar.gz", "https://example.com/a.tar.gz", 100),
            ReleaseAsset("b.zip", "https://example.com/b.zip", 200),
        ]
        assert get_download_url(releases, "b.zip") == "https://example.com/b.zip"

    def test_falls_back_to_token_selection(self, mocker):
        mocker.patch(
            "src.backend.engine.downloader.get_current_platform",
            return_value=("linux", "x86_64"),
        )
        releases = [_asset("stockfish-linux-x86-64-universal.tar.gz")]
        assert get_download_url(releases) == "https://example.com/stockfish-linux-x86-64-universal.tar.gz"

    def test_returns_none_when_not_found(self, mocker):
        mocker.patch(
            "src.backend.engine.downloader.get_current_platform",
            return_value=("linux", "x86_64"),
        )
        releases = [ReleaseAsset("a.tar.gz", "https://example.com/a.tar.gz", 100)]
        assert get_download_url(releases, "nonexistent.zip") is None


class TestGetDownloadCandidates:
    def test_uses_latest_release(self, mocker):
        mocker.patch(
            "src.backend.engine.downloader.get_current_platform",
            return_value=("linux", "x86_64"),
        )
        releases = [_asset("stockfish-linux-x86-64-universal.tar.gz")]
        urls = get_download_candidates(releases)
        assert urls == ["https://example.com/stockfish-linux-x86-64-universal.tar.gz"]

    def test_falls_back_to_pinned_tag(self, mocker):
        mocker.patch(
            "src.backend.engine.downloader.get_current_platform",
            return_value=("linux", "x86_64"),
        )
        mocker.patch(
            "src.backend.engine.downloader.get_releases_for_tag",
            return_value=[_asset("stockfish-ubuntu-x86-64-avx2.tar")],
        )
        urls = get_download_candidates([])
        assert urls == ["https://example.com/stockfish-ubuntu-x86-64-avx2.tar"]

    def test_no_candidates_returns_empty(self, mocker):
        mocker.patch(
            "src.backend.engine.downloader.get_current_platform",
            return_value=("linux", "x86_64"),
        )
        mocker.patch(
            "src.backend.engine.downloader.get_releases_for_tag",
            return_value=[],
        )
        assert get_download_candidates([]) == []


class TestDownloadAndExtract:
    def create_tar_fixture(self, tmp_path, binary_name="stockfish", gz=True):
        """Create a tar(.gz) with a Stockfish binary inside and return its path."""
        suffix = ".tar.gz" if gz else ".tar"
        archive = tmp_path / f"test{suffix}"
        inner_dir = tmp_path / "stockfish_dir"
        inner_dir.mkdir()
        binary = inner_dir / binary_name
        binary.write_text("fake stockfish binary")
        binary.chmod(0o755)

        mode = "w:gz" if gz else "w"
        with tarfile.open(str(archive), mode) as tf:
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

    def _mock_download(self, mocker, archive_path):
        mock_resp = MagicMock()
        mock_resp.headers = {"content-length": str(os.path.getsize(archive_path))}
        mock_resp.iter_content.return_value = [open(archive_path, "rb").read()]
        mocker.patch("requests.get", return_value=mock_resp)

    def test_download_and_extract_tar_gz(self, mocker, tmp_path):
        archive_path, _ = self.create_tar_fixture(tmp_path)
        self._mock_download(mocker, archive_path)

        dest = str(tmp_path / "dest")
        result = download_and_extract(
            "https://example.com/test.tar.gz", dest, validate=False
        )

        assert os.path.isfile(result)
        assert result == os.path.join(dest, "stockfish")
        assert os.access(result, os.X_OK)

    def test_download_and_extract_plain_tar(self, mocker, tmp_path):
        archive_path, _ = self.create_tar_fixture(tmp_path, gz=False)
        self._mock_download(mocker, archive_path)

        dest = str(tmp_path / "dest_tar")
        result = download_and_extract(
            "https://example.com/test.tar", dest, validate=False
        )
        assert os.path.isfile(result)

    def test_download_and_extract_mislabeled_archive(self, mocker, tmp_path):
        """A gzipped tar served with a .tar URL must still extract."""
        archive_path, _ = self.create_tar_fixture(tmp_path, gz=True)
        self._mock_download(mocker, archive_path)

        dest = str(tmp_path / "dest_mislabeled")
        result = download_and_extract(
            "https://example.com/stockfish.tar", dest, validate=False
        )
        assert os.path.isfile(result)

    def test_download_and_extract_zip(self, mocker, tmp_path):
        archive_path, _ = self.create_zip_fixture(tmp_path)
        self._mock_download(mocker, archive_path)
        mocker.patch.object(sys, "platform", "win32")

        dest = str(tmp_path / "dest_zip")
        result = download_and_extract(
            "https://example.com/test.zip", dest, validate=False
        )

        assert os.path.isfile(result)
        assert result.endswith("stockfish.exe")

    def test_progress_callback_called(self, mocker, tmp_path):
        archive_path, _ = self.create_tar_fixture(tmp_path)
        self._mock_download(mocker, archive_path)

        callback = MagicMock()
        download_and_extract(
            "https://example.com/test.tar.gz",
            str(tmp_path / "dest2"),
            progress_callback=callback,
            validate=False,
        )
        callback.assert_called()

    def test_falls_back_to_secondary_url(self, mocker, tmp_path):
        good_archive, _ = self.create_tar_fixture(tmp_path)
        bad_resp = MagicMock()
        bad_resp.raise_for_status.side_effect = Exception("boom")

        good_resp = MagicMock()
        good_resp.headers = {"content-length": str(os.path.getsize(good_archive))}
        good_resp.iter_content.return_value = [open(good_archive, "rb").read()]

        def side_effect(url, **kwargs):
            return bad_resp if "bad" in url else good_resp

        mocker.patch("requests.get", side_effect=side_effect)

        dest = str(tmp_path / "dest_fallback")
        result = download_and_extract(
            "https://example.com/bad.tar.gz",
            dest,
            validate=False,
            fallback_urls=["https://example.com/good.tar.gz"],
        )
        assert os.path.isfile(result)

    def test_raises_on_download_failure(self, mocker, tmp_path):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = Exception("Download failed")
        mocker.patch("requests.get", return_value=mock_resp)

        with pytest.raises(Exception, match="Download failed"):
            download_and_extract(
                "https://example.com/test.tar.gz",
                str(tmp_path / "dest3"),
                validate=False,
            )

    def test_validation_failure_tries_next_candidate(self, mocker, tmp_path):
        archive_path, _ = self.create_tar_fixture(tmp_path)
        self._mock_download(mocker, archive_path)
        mocker.patch(
            "src.backend.engine.downloader.probe_engine_binary",
            side_effect=[False, True],
        )
        dest = str(tmp_path / "dest_validate")
        result = download_and_extract(
            "https://example.com/test.tar.gz",
            dest,
            fallback_urls=["https://example.com/other.tar.gz"],
        )
        assert os.path.isfile(result)


class TestProbeEngineBinary:
    def test_returns_true_on_uciok(self, mocker):
        proc = MagicMock()
        proc.stdout = b"Stockfish 17\nuciok\n"
        proc.stderr = b""
        mocker.patch("subprocess.run", return_value=proc)
        assert probe_engine_binary("/fake/stockfish") is True

    def test_returns_false_on_garbage(self, mocker):
        proc = MagicMock()
        proc.stdout = b"not an engine"
        proc.stderr = b""
        mocker.patch("subprocess.run", return_value=proc)
        assert probe_engine_binary("/fake/stockfish") is False

    def test_returns_false_on_exception(self, mocker):
        mocker.patch("subprocess.run", side_effect=OSError("nope"))
        assert probe_engine_binary("/fake/stockfish") is False


class TestPackageManagerInstall:
    def test_returns_none_when_no_manager(self, mocker):
        mocker.patch("shutil.which", return_value=None)
        assert try_package_manager_install() is None

    def test_returns_path_on_success(self, mocker):
        def which(cmd, *a, **kw):
            return f"/usr/bin/{cmd}"

        mocker.patch("shutil.which", side_effect=which)
        proc = MagicMock()
        proc.returncode = 0
        mocker.patch("subprocess.run", return_value=proc)
        mocker.patch(
            "src.backend.engine.downloader.probe_engine_binary",
            return_value=True,
        )
        assert try_package_manager_install() == "/usr/bin/stockfish"
