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
