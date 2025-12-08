"""
Tests for ConfigManager - loading, saving, defaults.
"""
import pytest
import json
import os
from unittest.mock import patch


class TestConfigManager:
    """Tests for ConfigManager functionality."""
    
    def test_default_config(self, tmp_path):
        """Test default config values when no file exists."""
        # Patch get_app_path to return temp directory
        with patch('src.utils.config.get_app_path', return_value=str(tmp_path)):
            from src.utils.config import ConfigManager
            manager = ConfigManager()
            
            assert manager.get("engine_path") == "stockfish"
            assert manager.get("theme") == "dark"
            assert manager.get("gemini_api_key") == ""

    def test_get_nonexistent_key(self, tmp_path):
        """Test getting a key that doesn't exist returns default."""
        with patch('src.utils.config.get_app_path', return_value=str(tmp_path)):
            from src.utils.config import ConfigManager
            manager = ConfigManager()
            
            assert manager.get("nonexistent") is None
            assert manager.get("nonexistent", "default_val") == "default_val"

    def test_set_and_get(self, tmp_path):
        """Test setting and retrieving a value."""
        with patch('src.utils.config.get_app_path', return_value=str(tmp_path)):
            from src.utils.config import ConfigManager
            manager = ConfigManager()
            
            manager.set("custom_key", "custom_value")
            assert manager.get("custom_key") == "custom_value"

    def test_config_persists_to_file(self, tmp_path):
        """Test config changes are saved to disk."""
        with patch('src.utils.config.get_app_path', return_value=str(tmp_path)):
            from src.utils.config import ConfigManager
            manager = ConfigManager()
            
            manager.set("test_key", "test_value")
            
            # Read the file directly
            config_file = tmp_path / "config.json"
            assert config_file.exists()
            
            with open(config_file, 'r') as f:
                saved_config = json.load(f)
            
            assert saved_config["test_key"] == "test_value"

    def test_load_existing_config(self, tmp_path):
        """Test loading config from existing file."""
        # Create a config file first
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({
            "engine_path": "/custom/path",
            "theme": "light"
        }))
        
        with patch('src.utils.config.get_app_path', return_value=str(tmp_path)):
            from src.utils.config import ConfigManager
            manager = ConfigManager()
            
            assert manager.get("engine_path") == "/custom/path"
            assert manager.get("theme") == "light"

    def test_corrupted_config_uses_defaults(self, tmp_path):
        """Test corrupted config file falls back to defaults."""
        config_file = tmp_path / "config.json"
        config_file.write_text("not valid json {{{")
        
        with patch('src.utils.config.get_app_path', return_value=str(tmp_path)):
            from src.utils.config import ConfigManager
            manager = ConfigManager()
            
            # Should use defaults
            assert manager.get("engine_path") == "stockfish"
