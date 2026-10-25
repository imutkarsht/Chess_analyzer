"""
Tests for ConfigManager - loading, saving, defaults.
"""
import json
from unittest.mock import patch

import pytest


class TestConfigManager:
    """Tests for ConfigManager functionality."""

    def test_default_config(self, tmp_path):
        """Test default config values when no file exists."""
        # Patch get_user_data_dir to return temp directory
        with patch('src.utils.config.get_user_data_dir', return_value=str(tmp_path)):
            from src.utils.config import ConfigManager
            manager = ConfigManager()

            assert manager.get("engine_path") == "stockfish"
            assert manager.get("theme_mode") == "system"
            assert manager.get("multi_pv") == 2
            assert manager.get("live_analysis_time") == 0.5
            assert manager.get("live_multi_pv") == 2
            assert manager.get("analysis_depth") == 18
            assert manager.get("time_per_move") == 1.0
            assert manager.get("use_cache") is True
            assert manager.get("engine_lines_enabled") is False
            assert manager.get("board_show_best_move_arrow") is True
            assert manager.get("board_show_last_move") is True
            assert manager.get("board_show_eval_bar") is True
            assert manager.get("remember_window_geometry") is True
            assert manager.get("sound_volume") == 50
            assert manager.get("api_games_limit") == 20
            assert manager.get("explorer_cache_ttl_hours") == 48
            assert manager.get("analysis_cache_max_entries") == 250_000
            assert manager.get("explain_cache_ttl_days") == 30

    def test_get_nonexistent_key(self, tmp_path):
        """Test getting a key that doesn't exist returns default."""
        with patch('src.utils.config.get_user_data_dir', return_value=str(tmp_path)):
            from src.utils.config import ConfigManager
            manager = ConfigManager()

            assert manager.get("nonexistent") is None
            assert manager.get("nonexistent", "default_val") == "default_val"

    def test_set_and_get(self, tmp_path):
        """Test setting and retrieving a value."""
        with patch('src.utils.config.get_user_data_dir', return_value=str(tmp_path)):
            from src.utils.config import ConfigManager
            manager = ConfigManager()

            manager.set("custom_key", "custom_value")
            assert manager.get("custom_key") == "custom_value"

    def test_config_persists_to_file(self, tmp_path):
        """Test config changes are saved to disk."""
        with patch('src.utils.config.get_user_data_dir', return_value=str(tmp_path)):
            from src.utils.config import ConfigManager
            manager = ConfigManager()

            manager.set("test_key", "test_value")

            # Read the file directly
            config_file = tmp_path / "config.json"
            assert config_file.exists()

            with open(config_file) as f:
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

        with patch('src.utils.config.get_user_data_dir', return_value=str(tmp_path)):
            from src.utils.config import ConfigManager
            manager = ConfigManager()

            assert manager.get("engine_path") == "/custom/path"
            assert manager.get("theme") == "light"

    def test_corrupted_config_uses_defaults(self, tmp_path):
        """Test corrupted config file falls back to defaults."""
        config_file = tmp_path / "config.json"
        config_file.write_text("not valid json {{{")

        with patch('src.utils.config.get_user_data_dir', return_value=str(tmp_path)):
            from src.utils.config import ConfigManager
            manager = ConfigManager()

            # Should use defaults
            assert manager.get("engine_path") == "stockfish"

    def test_window_state_default(self, tmp_path):
        """window_state should default to an all-null dict."""
        with patch('src.utils.config.get_user_data_dir', return_value=str(tmp_path)):
            from src.utils.config import ConfigManager
            manager = ConfigManager()

            state = manager.get("window_state")
            assert state == {"x": None, "y": None, "width": None, "height": None}

    def test_window_state_round_trip(self, tmp_path):
        """Setting window_state persists the new geometry."""
        with patch('src.utils.config.get_user_data_dir', return_value=str(tmp_path)):
            from src.utils.config import ConfigManager
            manager = ConfigManager()

            new_state = {"x": 100, "y": 200, "width": 1280, "height": 720}
            manager.set("window_state", new_state)
            assert manager.get("window_state") == new_state

            # Reload from disk to make sure it actually wrote
            reloaded = ConfigManager()
            assert reloaded.get("window_state") == new_state

    def test_window_state_migrates_into_legacy_config(self, tmp_path):
        """An existing config without window_state should gain the default."""
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({"engine_path": "stockfish", "theme": "dark"}))

        with patch('src.utils.config.get_user_data_dir', return_value=str(tmp_path)):
            from src.utils.config import ConfigManager
            manager = ConfigManager()

            state = manager.get("window_state")
            assert state is not None
            assert state == {"x": None, "y": None, "width": None, "height": None}

    def test_reload_config_in_place(self, tmp_path):
        """test reload_config updates shared config dict in-place so all instances see updates."""
        with patch('src.utils.config.get_user_data_dir', return_value=str(tmp_path)):
            from src.utils.config import ConfigManager
            manager1 = ConfigManager()
            manager2 = ConfigManager()

            # Initially same
            assert manager1.get("theme_mode") == "system"
            assert manager2.get("theme_mode") == "system"

            # Manually update config.json on disk to simulate external changes or reloads
            config_file = tmp_path / "config.json"
            config_file.write_text(json.dumps({
                "engine_path": "stockfish",
                "theme": "light"
            }))

            # Reload on manager1
            manager1.reload_config()

            # Verify both see it because dictionary is updated in-place
            assert manager1.get("theme") == "light"
            assert manager2.get("theme") == "light"

    @pytest.mark.parametrize(
        "key", ["explain_cache_ttl_days", "explorer_cache_ttl_hours"]
    )
    def test_nullable_int_setting_accepts_none(self, tmp_path, key):
        """Cache TTLs store ``None`` for "never expire"."""
        with patch('src.utils.config.get_user_data_dir', return_value=str(tmp_path)):
            from src.utils.config import ConfigManager
            manager = ConfigManager()

            manager.set(key, None)

            assert manager.get(key) is None

    def test_nullable_float_setting_accepts_none(self, tmp_path):
        """The time cap stores ``None`` for a depth-only search."""
        with patch('src.utils.config.get_user_data_dir', return_value=str(tmp_path)):
            from src.utils.config import ConfigManager
            manager = ConfigManager()

            manager.set("time_per_move", None)

            assert manager.get("time_per_move") is None

    def test_non_nullable_int_setting_rejects_none(self, tmp_path):
        """Specs without ``nullable`` keep their previous value instead of going null."""
        with patch('src.utils.config.get_user_data_dir', return_value=str(tmp_path)):
            from src.utils.config import ConfigManager
            manager = ConfigManager()
            manager.set("analysis_depth", 22)

            manager.set("analysis_depth", None)

            assert manager.get("analysis_depth") == 22
