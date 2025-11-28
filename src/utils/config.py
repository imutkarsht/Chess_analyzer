import json
import os
from .logger import logger
from .path_utils import get_app_path

class ConfigManager:
    CONFIG_FILE = "config.json"
    
    DEFAULT_CONFIG = {
        "engine_path": "stockfish",
        "theme": "dark",
        "gemini_api_key": ""
    }

    def __init__(self):
        self.config_path = os.path.join(get_app_path(), self.CONFIG_FILE)
        self.config = self.load_config()

    def load_config(self):
        if not os.path.exists(self.config_path):
            return self.DEFAULT_CONFIG.copy()
        
        try:
            with open(self.config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            return self.DEFAULT_CONFIG.copy()

    def save_config(self):
        try:
            with open(self.config_path, 'w') as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            logger.error(f"Failed to save config: {e}")

    def get(self, key, default=None):
        return self.config.get(key, default)

    def set(self, key, value):
        self.config[key] = value
        self.save_config()
