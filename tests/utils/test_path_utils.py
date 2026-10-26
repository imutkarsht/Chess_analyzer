import os
import sys

from src.utils.path_utils import (
    get_engine_data_dir,
    get_resource_path,
    get_stockfish_common_paths,
    get_user_data_dir,
)


class TestGetResourcePath:
    def test_uses_pyinstaller_bundle_dir(self, mocker):
        mocker.patch.object(sys, "_MEIPASS", "/tmp/bundle", create=True)
        assert get_resource_path("assets/logo.png") == os.path.join(
            "/tmp/bundle", "assets/logo.png"
        )

    def test_uses_project_root_in_development(self, mocker, monkeypatch):
        monkeypatch.delattr(sys, "_MEIPASS", raising=False)
        mocker.patch("src.utils.path_utils.os.path.abspath", return_value="/project")

        assert get_resource_path("assets/logo.png") == os.path.join(
            "/project", "assets/logo.png"
        )


class TestGetUserDataDir:
    def _patch_fs(self, mocker):
        mocker.patch("os.makedirs")
        mocker.patch("os.path.expanduser", side_effect=lambda path: "/home/tester" + path[1:])

    def test_macos_uses_application_support(self, mocker):
        self._patch_fs(mocker)
        mocker.patch.object(sys, "platform", "darwin")

        assert get_user_data_dir() == (
            "/home/tester/Library/Application Support/ChessAnalyzerPro"
        )

    def test_windows_prefers_appdata(self, mocker, monkeypatch):
        self._patch_fs(mocker)
        mocker.patch.object(sys, "platform", "win32")
        monkeypatch.setenv("APPDATA", "C:/Users/tester/AppData/Roaming")

        assert get_user_data_dir() == os.path.join(
            "C:/Users/tester/AppData/Roaming", "ChessAnalyzerPro"
        )

    def test_windows_without_appdata_uses_home(self, mocker, monkeypatch):
        self._patch_fs(mocker)
        mocker.patch.object(sys, "platform", "win32")
        monkeypatch.delenv("APPDATA", raising=False)

        assert get_user_data_dir() == (
            "/home/tester" + "\\AppData\\Roaming\\ChessAnalyzerPro"
        )

    def test_linux_prefers_xdg_data_home(self, mocker, monkeypatch):
        self._patch_fs(mocker)
        mocker.patch.object(sys, "platform", "linux")
        monkeypatch.setenv("XDG_DATA_HOME", "/xdg/data")

        assert get_user_data_dir() == os.path.join("/xdg/data", "chessanalyzerpro")

    def test_linux_falls_back_to_home_share(self, mocker, monkeypatch):
        self._patch_fs(mocker)
        mocker.patch.object(sys, "platform", "linux")
        monkeypatch.delenv("XDG_DATA_HOME", raising=False)

        assert get_user_data_dir() == "/home/tester/.local/share/chessanalyzerpro"

    def test_creates_directory(self, mocker, tmp_path):
        mocker.patch.object(sys, "platform", "darwin")
        mocker.patch("os.path.expanduser", return_value=str(tmp_path / "appdata"))

        assert os.path.isdir(get_user_data_dir())


class TestGetStockfishCommonPaths:
    def test_returns_list(self):
        paths = get_stockfish_common_paths()
        assert isinstance(paths, list)
        assert len(paths) > 0

    def test_macos_paths(self, mocker):
        mocker.patch.object(sys, "platform", "darwin")
        paths = get_stockfish_common_paths()
        assert "/opt/homebrew/bin/stockfish" in paths
        assert "/usr/local/bin/stockfish" in paths

    def test_windows_paths(self, mocker):
        mocker.patch.object(sys, "platform", "win32")
        paths = get_stockfish_common_paths()
        assert any(p.endswith("stockfish.exe") for p in paths)
        assert "C:\\Program Files\\Stockfish\\stockfish.exe" in paths

    def test_linux_paths(self, mocker):
        mocker.patch.object(sys, "platform", "linux")
        paths = get_stockfish_common_paths()
        assert "/usr/bin/stockfish" in paths
        assert "/usr/local/bin/stockfish" in paths


class TestGetEngineDataDir:
    def test_returns_subdir_of_user_data_dir(self, mocker):
        mocker.patch("src.utils.path_utils.get_user_data_dir", return_value="/base/data")
        mocker.patch("os.makedirs")
        engine_dir = get_engine_data_dir()
        assert engine_dir == os.path.join("/base/data", "engine")

    def test_creates_directory(self, mocker, tmp_path):
        base = str(tmp_path / "data")
        mocker.patch("src.utils.path_utils.get_user_data_dir", return_value=base)
        engine_dir = get_engine_data_dir()
        assert engine_dir == os.path.join(base, "engine")
        assert os.path.isdir(engine_dir)

