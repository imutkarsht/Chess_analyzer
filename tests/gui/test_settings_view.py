import pytest
from unittest.mock import patch, MagicMock
import json
from PyQt6.QtWidgets import QMessageBox

@pytest.fixture
def isolated_config(tmp_path, monkeypatch):
    """Point the ConfigManager at a per-test directory."""
    monkeypatch.setattr("src.utils.config.get_user_data_dir", lambda: str(tmp_path))
    monkeypatch.delenv("LICHESS_TOKEN", raising=False)
    return tmp_path / "config.json"

def test_settings_view_clamping_without_token(qapp, qtbot, isolated_config):
    """Without Lichess API Token, game limit should be capped at 20."""
    from src.gui.views.settings_view import SettingsView
    
    with patch("src.utils.config.get_user_data_dir", return_value=str(isolated_config.parent)):
        view = SettingsView()
        qtbot.addWidget(view)
        
        # Set text inputs
        view.chesscom_input.setText("TestUserChessCom")
        view.lichess_input.setText("TestUserLichess")
        view.lichess_token_input.setText("")  # No token
        view.games_limit_input.setText("25")  # Exceeds max 20 without token
        
        # Mock QMessageBox.warning to prevent blocking the test
        with patch.object(QMessageBox, "warning") as mock_warning:
            view.save_usernames()
            mock_warning.assert_called_once()
            
        # Verify clamped value is written to config and UI input
        assert view.config_manager.get("api_games_limit") == 20
        assert view.games_limit_input.text() == "20"

def test_settings_view_clamping_with_token(qapp, qtbot, isolated_config):
    """With Lichess API Token, game limit up to 30 is accepted and above 30 is capped."""
    from src.gui.views.settings_view import SettingsView
    
    with patch("src.utils.config.get_user_data_dir", return_value=str(isolated_config.parent)):
        view = SettingsView()
        qtbot.addWidget(view)
        
        # 1. Test accepting value <= 30 (e.g. 25) with token
        view.lichess_token_input.setText("test_token")
        view.games_limit_input.setText("25")
        
        with patch.object(QMessageBox, "information") as mock_info:
            view.save_usernames()
            mock_info.assert_called_once()
            
        assert view.config_manager.get("api_games_limit") == 25
        assert view.games_limit_input.text() == "25"
        
        # 2. Test clamping value > 30 (e.g. 35) with token
        view.games_limit_input.setText("35")
        
        with patch.object(QMessageBox, "warning") as mock_warning:
            view.save_usernames()
            mock_warning.assert_called_once()
            
        assert view.config_manager.get("api_games_limit") == 30
        assert view.games_limit_input.text() == "30"

def test_save_all_settings_flow(qapp, qtbot, isolated_config):
    """Test the consolidated save_all_settings flow."""
    from src.gui.views.settings_view import SettingsView
    
    with patch("src.utils.config.get_user_data_dir", return_value=str(isolated_config.parent)):
        view = SettingsView()
        qtbot.addWidget(view)
        
        # Modify some UI fields
        view.path_input.setText("mock-stockfish")
        view.threads_input.setText("3")
        view.hash_input.setText("128")
        view.chesscom_input.setText("NewUserChessCom")
        view.lichess_input.setText("NewUserLichess")
        view.games_limit_input.setText("15")
        
        # Mock validation and signals
        view.validate_engine_path = MagicMock()
        view.engine_path_changed = MagicMock()
        view.engine_settings_changed = MagicMock()
        view.llm_config_changed = MagicMock()
        view.usernames_changed = MagicMock()
        
        with patch.object(QMessageBox, "information") as mock_info:
            view.save_all_settings()
            mock_info.assert_called_once()
            
        # Verify changes are stored in the config
        assert view.config_manager.get("engine_path") == "mock-stockfish"
        assert view.config_manager.get("engine_threads") == 3
        assert view.config_manager.get("engine_hash") == 128
        assert view.config_manager.get("chesscom_username") == "NewUserChessCom"
        assert view.config_manager.get("lichess_username") == "NewUserLichess"
        assert view.config_manager.get("api_games_limit") == 15
        
        # Verify signals are emitted
        view.engine_path_changed.emit.assert_called_once_with("mock-stockfish")
        view.engine_settings_changed.emit.assert_called_once()
        view.llm_config_changed.emit.assert_called_once()
        view.usernames_changed.emit.assert_called_once()
