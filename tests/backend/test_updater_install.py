"""Tests for update download, platform install dispatch, and release parsing."""

import stat
import sys

import pytest
import requests

from src.backend.updater import updater
from src.backend.updater.update_checker import (
    UpdateChecker,
    UpdateCheckerWorker,
    _pick_asset,
)
from src.backend.updater.updater import (
    DownloadWorker,
    get_download_destination,
    install_and_quit,
)


class TestDownloadWorker:
    def _response(self, mocker, chunks, content_length="20"):
        response = mocker.MagicMock()
        response.headers = {"content-length": content_length}
        response.iter_content.return_value = chunks
        response.__enter__.return_value = response
        mocker.patch("requests.get", return_value=response)
        return response

    def test_successful_download_writes_file_and_reports_progress(self, mocker, tmp_path, qapp):
        self._response(mocker, [b"a" * 10, b"b" * 10])
        dest = tmp_path / "update.dmg"
        worker = DownloadWorker("https://example.com/update.dmg", str(dest))
        progress, finished, errors = [], [], []
        worker.progress.connect(progress.append)
        worker.finished.connect(finished.append)
        worker.error.connect(errors.append)

        worker.run()

        assert dest.read_bytes() == b"a" * 10 + b"b" * 10
        assert progress[-1] == 100
        assert finished == [str(dest)]
        assert errors == []

    def test_cancelled_download_removes_partial_file(self, mocker, tmp_path, qapp):
        self._response(mocker, [b"a" * 10])
        dest = tmp_path / "update.dmg"
        worker = DownloadWorker("https://example.com/update.dmg", str(dest))
        worker.cancel()
        finished, errors = [], []
        worker.finished.connect(finished.append)
        worker.error.connect(errors.append)

        worker.run()

        assert not dest.exists()
        assert finished == []
        assert errors == []

    def test_http_failure_emits_error_and_cleans_up(self, mocker, tmp_path, qapp):
        response = self._response(mocker, [b"data"])
        response.raise_for_status.side_effect = requests.HTTPError("404")
        dest = tmp_path / "update.dmg"
        dest.write_bytes(b"partial")
        worker = DownloadWorker("https://example.com/update.dmg", str(dest))
        errors = []
        worker.error.connect(errors.append)

        worker.run()

        assert not dest.exists()
        assert errors and "404" in errors[0]


class TestDownloadDestination:
    def test_macos_uses_downloads_directory(self, mocker, tmp_path):
        mocker.patch.object(updater, "PLATFORM", "darwin")
        mocker.patch(
            "src.backend.updater.updater.Path.home", return_value=tmp_path
        )

        dest = get_download_destination("https://example.com/Chess.dmg")

        assert dest == str(tmp_path / "Downloads" / "Chess.dmg")
        assert (tmp_path / "Downloads").is_dir()

    @pytest.mark.parametrize("platform", ["win32", "linux"])
    def test_other_platforms_use_temp_dir(self, mocker, tmp_path, platform):
        mocker.patch.object(updater, "PLATFORM", platform)
        mocker.patch(
            "src.backend.updater.updater.tempfile.gettempdir",
            return_value=str(tmp_path),
        )

        assert get_download_destination("https://example.com/Chess.AppImage") == str(
            tmp_path / "Chess.AppImage"
        )

    def test_url_without_filename_gets_default_name(self, mocker, tmp_path):
        mocker.patch.object(updater, "PLATFORM", "linux")
        mocker.patch(
            "src.backend.updater.updater.tempfile.gettempdir",
            return_value=str(tmp_path),
        )

        assert get_download_destination("https://example.com/") == str(
            tmp_path / "ChessAnalyzerPro-update"
        )


class TestInstallDispatch:
    @pytest.mark.parametrize(
        ("platform", "installer"),
        [
            ("win32", "_install_windows"),
            ("darwin", "_install_macos"),
            ("linux", "_install_linux"),
        ],
    )
    def test_dispatches_to_platform_installer(self, mocker, platform, installer):
        mocker.patch.object(updater, "PLATFORM", platform)
        install = mocker.patch(f"src.backend.updater.updater.{installer}")
        quit_app = mocker.Mock()

        install_and_quit("/tmp/installer", quit_app)

        install.assert_called_once_with("/tmp/installer")
        quit_app.assert_called_once()

    def test_quit_runs_even_when_install_fails(self, mocker):
        mocker.patch.object(updater, "PLATFORM", "darwin")
        mocker.patch(
            "src.backend.updater.updater._install_macos",
            side_effect=RuntimeError("mount failed"),
        )
        quit_app = mocker.Mock()

        with pytest.raises(RuntimeError, match="mount failed"):
            install_and_quit("/tmp/installer", quit_app)

        quit_app.assert_called_once()


def test_install_windows_launches_silent_setup(mocker):
    popen = mocker.patch("src.backend.updater.updater.subprocess.Popen")

    updater._install_windows("/tmp/ChessSetup.exe")

    args = popen.call_args.args[0]
    assert args[0] == "/tmp/ChessSetup.exe"
    assert {"/VERYSILENT", "/NORESTART", "/CLOSEAPPLICATIONS"} <= set(args)
    assert popen.call_args.kwargs["close_fds"] is True


def test_install_macos_strips_quarantine_and_opens_dmg(mocker):
    run = mocker.patch("src.backend.updater.updater.subprocess.run")
    popen = mocker.patch("src.backend.updater.updater.subprocess.Popen")

    updater._install_macos("/tmp/Chess.dmg")

    assert run.call_args.args[0][:2] == ["xattr", "-rd"]
    popen.assert_called_once_with(["open", "/tmp/Chess.dmg"])


def test_install_macos_tolerates_missing_xattr(mocker):
    mocker.patch(
        "src.backend.updater.updater.subprocess.run", side_effect=FileNotFoundError
    )
    popen = mocker.patch("src.backend.updater.updater.subprocess.Popen")

    updater._install_macos("/tmp/Chess.dmg")

    popen.assert_called_once_with(["open", "/tmp/Chess.dmg"])


class TestInstallLinux:
    def _prepare(self, mocker, tmp_path, monkeypatch, appimage):
        new_appimage = tmp_path / "new.AppImage"
        new_appimage.write_bytes(b"binary")
        mocker.patch(
            "src.backend.updater.updater.tempfile.gettempdir",
            return_value=str(tmp_path),
        )
        popen = mocker.patch("src.backend.updater.updater.subprocess.Popen")
        if appimage:
            monkeypatch.setenv("APPIMAGE", str(tmp_path / "current.AppImage"))
        else:
            monkeypatch.delenv("APPIMAGE", raising=False)
            mocker.patch.object(updater.sys, "executable", "/usr/bin/python")
        return new_appimage, popen

    def test_appimage_runtime_hot_swaps_and_relaunches(
        self, mocker, tmp_path, monkeypatch
    ):
        new_appimage, popen = self._prepare(mocker, tmp_path, monkeypatch, appimage=True)

        updater._install_linux(str(new_appimage))

        script_path = tmp_path / "chess_analyzer_updater.sh"
        script = script_path.read_text()
        assert f'TARGET="{tmp_path / "current.AppImage"}"' in script
        assert f'NEW_APPIMAGE="{new_appimage}"' in script
        assert 'exec "' in script
        # Windows only emulates the read-only bit; POSIX permission bits are
        # not meaningful there, so the mode assertions are Unix-only.
        if sys.platform != "win32":
            assert stat.S_IMODE(script_path.stat().st_mode) == 0o700
            assert new_appimage.stat().st_mode & stat.S_IXUSR
        popen.assert_called_once_with(
            ["bash", str(script_path)],
            start_new_session=True,
            stdin=mocker.ANY,
            stdout=mocker.ANY,
            stderr=mocker.ANY,
        )

    def test_development_mode_skips_relaunch(self, mocker, tmp_path, monkeypatch):
        new_appimage, _ = self._prepare(mocker, tmp_path, monkeypatch, appimage=False)

        updater._install_linux(str(new_appimage))

        script = (tmp_path / "chess_analyzer_updater.sh").read_text()
        assert "swap complete" in script
        assert 'exec "/usr/bin/python"' not in script


class TestPickAssetFallbacks:
    def test_keyword_plus_fallback_suffix(self, mocker):
        mocker.patch(
            "src.backend.updater.update_checker._CURRENT_PLATFORM", "darwin"
        )
        assets = [{"name": "Chess-macOS-build.zip", "browser_download_url": "http://mac.zip"}]

        assert _pick_asset(assets)[0] == "http://mac.zip"

    def test_any_fallback_suffix(self, mocker):
        mocker.patch(
            "src.backend.updater.update_checker._CURRENT_PLATFORM", "darwin"
        )
        assets = [{"name": "Chess-build.zip", "browser_download_url": "http://zip"}]

        assert _pick_asset(assets)[0] == "http://zip"

    def test_no_matching_asset_returns_none(self, mocker):
        mocker.patch(
            "src.backend.updater.update_checker._CURRENT_PLATFORM", "darwin"
        )

        url, label, hint = _pick_asset([{"name": "checksums.txt"}])

        assert url is None
        assert "macOS" in label
        assert hint


class TestUpdateChecker:
    def _release(self, mocker, **payload):
        response = mocker.Mock()
        response.json.return_value = payload
        mocker.patch("requests.get", return_value=response)
        return response

    def test_newer_release_without_asset_links_to_release_page(self, mocker):
        self._release(
            mocker,
            tag_name="v99.1.0",
            html_url="https://github.com/repo/releases/v99.1.0",
            assets=[],
            body="notes",
        )

        info = UpdateChecker.check_for_updates()

        assert info.available is True
        assert info.latest == "99.1.0"
        assert info.download_url == "https://github.com/repo/releases/v99.1.0"

    def test_invalid_version_is_not_an_update(self, mocker):
        self._release(mocker, tag_name="vnot-a-version", assets=[], html_url="")

        assert UpdateChecker.check_for_updates().available is False

    def test_network_failure_is_reported_as_unavailable(self, mocker):
        mocker.patch(
            "requests.get", side_effect=requests.exceptions.ConnectionError("offline")
        )

        assert UpdateChecker.check_for_updates().available is False

    def test_unexpected_payload_error_is_unavailable(self, mocker):
        response = mocker.Mock()
        response.json.side_effect = ValueError("bad json")
        mocker.patch("requests.get", return_value=response)

        assert UpdateChecker.check_for_updates().available is False


class TestUpdateCheckerWorker:
    def test_cancelled_worker_does_not_emit(self, mocker, qapp):
        check = mocker.patch.object(UpdateChecker, "check_for_updates")
        worker = UpdateCheckerWorker()
        worker.cancel()
        emitted = []
        worker.update_checked.connect(emitted.append)

        worker.run()

        check.assert_not_called()
        assert emitted == []

    def test_worker_emits_checker_result(self, mocker, qapp):
        sentinel = object()
        mocker.patch.object(UpdateChecker, "check_for_updates", return_value=sentinel)
        worker = UpdateCheckerWorker()
        emitted = []
        worker.update_checked.connect(emitted.append)

        worker.run()

        assert emitted == [sentinel]
