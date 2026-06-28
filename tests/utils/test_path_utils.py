import sys
import pytest
from src.utils.path_utils import (
    get_stockfish_common_paths,
    get_engine_data_dir,
    get_user_data_dir,
)


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
        assert engine_dir == "/base/data/engine"

    def test_creates_directory(self, mocker, tmp_path):
        base = str(tmp_path / "data")
        mocker.patch("src.utils.path_utils.get_user_data_dir", return_value=base)
        engine_dir = get_engine_data_dir()
        assert engine_dir == f"{base}/engine"
        import os
        assert os.path.isdir(engine_dir)
