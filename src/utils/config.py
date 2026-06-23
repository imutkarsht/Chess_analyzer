import json
import os
from .logger import logger
from .path_utils import get_app_path, get_user_data_dir

class ConfigManager:
    CONFIG_FILE = "config.json"
    _shared_config = None
    _shared_config_path = None

    DEFAULT_CONFIG = {
        "engine_path": "stockfish",
        "polyglot_book_path": "",
        "theme": "dark",
        "sound_enabled": True,
        # Profile-based LLM config.  Each profile is a dict with keys:
        #   name, provider, api_key, model, base_url
        "llm_profiles": [],
        "llm_active_profile": "",
        # Legacy flat keys — kept only for the migration path below.
        "groq_api_key": "",
        "groq_model": "llama-3.3-70b-versatile",
        "analysis_depth": 18,
        "api_games_limit": 20,
        # Engine footprint controls (see issue #5).  multi_pv and
        # live_analysis_time are the new user-tunable knobs; we seed
        # them in DEFAULT_CONFIG so a brand-new install has safe
        # values and the analyzers' `config_manager.get(key, default)`
        # calls return the persisted number (not the literal default
        # fallback) on first run.
        #
        # Note: engine_threads and engine_hash are *intentionally*
        # absent from DEFAULT_CONFIG.  options_from_config() in
        # backend/engine.py already falls back to its own conservative
        # module-level constants when those keys are missing — adding
        # them here as `None` would break that fallback (a stored None
        # wins over a `.get(key, default)` fallback).
        "multi_pv": 1,
        "live_analysis_time": 2.0,
        # Last known main window geometry (x, y, width, height).
        # Any field may be None, meaning "use Qt's default for that dimension".
        "window_state": {"x": None, "y": None, "width": None, "height": None},
        "board_theme": "Green",
        "piece_theme": "Standard",
        "accent_color": "#FF9500",
        "lichess_token": "",
        "chesscom_username": "",
        "lichess_username": "",
    }

    # Human-readable name used when creating the first migration profile.
    _PROVIDER_LABELS = {
        "groq": "Groq", "lmstudio": "LM Studio",
        "minimax": "MiniMax", "custom": "Custom",
    }

    def __init__(self):
        self.config_path = os.path.join(get_user_data_dir(), self.CONFIG_FILE)
        if (self.__class__._shared_config is None or 
                self.__class__._shared_config_path != self.config_path):
            self.__class__._shared_config = self.load_config()
            self.__class__._shared_config_path = self.config_path
        self.config = self.__class__._shared_config

    def load_config(self):
        if not os.path.exists(self.config_path):
            cfg = self.DEFAULT_CONFIG.copy()
            self._ensure_default_profile(cfg)
            return cfg

        try:
            with open(self.config_path, 'r') as f:
                data = json.load(f)
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            cfg = self.DEFAULT_CONFIG.copy()
            self._ensure_default_profile(cfg)
            return cfg

        # Fill any missing top-level keys from defaults
        for key, value in self.DEFAULT_CONFIG.items():
            data.setdefault(key, value)

        # One-time migration: build profile list from previous flat config keys.
        migrated = False
        if not data.get("llm_profiles"):
            provider = (data.get("llm_provider")
                        or (data.get("groq_api_key") and "groq")
                        or "groq")
            api_key  = data.get("llm_api_key", "") or data.get("groq_api_key", "")
            model    = data.get("llm_model", "") or data.get("groq_model", "")
            base_url = data.get("llm_base_url", "")
            name = self._PROVIDER_LABELS.get(provider, provider.capitalize())
            data["llm_profiles"] = [{
                "name": name,
                "provider": provider,
                "api_key": api_key,
                "model": model or "llama-3.3-70b-versatile",
                "base_url": base_url,
            }]
            data["llm_active_profile"] = name
            logger.info(f"Config: migrated single LLM config to profile '{name}'")
            migrated = True

        if migrated:
            # Persist immediately so migration doesn't repeat on every startup.
            try:
                with open(self.config_path, 'w') as f:
                    json.dump(data, f, indent=4)
            except Exception:
                pass  # Non-critical: migration will silently repeat next startup

        return data

    def _ensure_default_profile(self, cfg: dict) -> None:
        """Guarantee at least one profile exists in a fresh config."""
        if not cfg.get("llm_profiles"):
            cfg["llm_profiles"] = [{
                "name": "Groq",
                "provider": "groq",
                "api_key": "",
                "model": "llama-3.3-70b-versatile",
                "base_url": "",
            }]
            cfg["llm_active_profile"] = "Groq"

    # ------------------------------------------------------------------
    # Active profile helpers
    # ------------------------------------------------------------------

    def get_active_profile(self) -> dict:
        """Return the active LLM profile dict, or the first profile as fallback."""
        profiles = self.config.get("llm_profiles", [])
        active_name = self.config.get("llm_active_profile", "")
        if profiles:
            for p in profiles:
                if p.get("name") == active_name:
                    return p
            return profiles[0]
        return {}

    def get_profiles(self) -> list:
        return self.config.get("llm_profiles", [])

    def set_profiles(self, profiles: list, active_name: str = "") -> None:
        self.config["llm_profiles"] = profiles
        if active_name:
            self.config["llm_active_profile"] = active_name
        self.save_config()

    def reload_config(self):
        new_data = self.load_config()
        if self.__class__._shared_config is not None:
            self.__class__._shared_config.clear()
            self.__class__._shared_config.update(new_data)
        else:
            self.__class__._shared_config = new_data
        self.config = self.__class__._shared_config

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
