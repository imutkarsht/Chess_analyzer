import json
import os
from copy import deepcopy

from src.config.settings_schema import (
    SECRET_PROFILE_PREFIX,
    default_config,
    get_spec,
)
from src.utils.logger import logger
from src.utils.path_utils import get_user_data_dir
from src.utils.secrets import SecretStore


class ConfigManager:
    CONFIG_FILE = "config.json"
    SCHEMA_VERSION = 1
    _shared_config = None
    _shared_config_path = None

    # Derived from the settings registry so defaults have one source of truth.
    DEFAULT_CONFIG = default_config()

    _PROVIDER_LABELS = {
        "groq": "Groq",
        "lmstudio": "LM Studio",
        "minimax": "MiniMax",
        "custom": "Custom",
    }

    def __init__(self):
        self.config_path = os.path.join(get_user_data_dir(), self.CONFIG_FILE)
        self.secrets = SecretStore(
            os.path.join(os.path.dirname(self.config_path), SecretStore.FILE)
        )
        if (
            self.__class__._shared_config is None
            or self.__class__._shared_config_path != self.config_path
        ):
            self.__class__._shared_config = self.load_config()
            self.__class__._shared_config_path = self.config_path
        self.config = self.__class__._shared_config

    # ------------------------------------------------------------------
    # Load / save / migration
    # ------------------------------------------------------------------
    def load_config(self):
        if not os.path.exists(self.config_path):
            cfg = deepcopy(self.DEFAULT_CONFIG)
            self._ensure_default_profile(cfg)
            return cfg

        try:
            with open(self.config_path) as f:
                data = json.load(f)
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            cfg = deepcopy(self.DEFAULT_CONFIG)
            self._ensure_default_profile(cfg)
            return cfg

        changed = False
        for spec in self.DEFAULT_CONFIG:
            if spec not in data:
                data[spec] = deepcopy(self.DEFAULT_CONFIG[spec])
                changed = True

        changed = self._migrate_legacy_llm(data) or changed
        changed = self._migrate_secrets(data) or changed
        if "schema_version" not in data:
            data["schema_version"] = self.SCHEMA_VERSION
            changed = True

        if changed:
            self._write_config(data)
        return data

    def _migrate_legacy_llm(self, data: dict) -> bool:
        """Build the profile list from the pre-profile flat config."""
        if data.get("llm_profiles"):
            return False

        provider = (
            data.get("llm_provider")
            or (data.get("groq_api_key") and "groq")
            or "groq"
        )
        api_key = data.get("llm_api_key", "") or data.get("groq_api_key", "")
        model = data.get("llm_model", "") or data.get("groq_model", "")
        base_url = data.get("llm_base_url", "")
        name = self._PROVIDER_LABELS.get(provider, provider.capitalize())
        data["llm_profiles"] = [
            {
                "name": name,
                "provider": provider,
                "api_key": api_key,
                "model": model or "llama-3.3-70b-versatile",
                "base_url": base_url,
            }
        ]
        data["llm_active_profile"] = name
        logger.info("Config: migrated single LLM config to profile '%s'", name)

        legacy = (
            "groq_api_key",
            "groq_model",
            "llm_api_key",
            "llm_model",
            "llm_provider",
            "llm_base_url",
        )
        for key in legacy:
            data.pop(key, None)
        return True

    def _migrate_secrets(self, data: dict) -> bool:
        """Move legacy inline secrets into secrets.json."""
        changed = False

        token = data.get("lichess_token", "")
        if token:
            self.secrets.set("lichess_token", token)
            if self.secrets.get("lichess_token") == token:
                data["lichess_token"] = ""
                changed = True

        for profile in data.get("llm_profiles", []):
            api_key = profile.get("api_key", "")
            if api_key:
                name = profile.get("name", "")
                secret_key = f"{SECRET_PROFILE_PREFIX}{name}"
                self.secrets.set(secret_key, api_key)
                if self.secrets.get(secret_key) == api_key:
                    profile.pop("api_key", None)
                    changed = True

        return changed

    def _write_config(self, data: dict) -> None:
        payload = deepcopy(data)

        token = payload.get("lichess_token", "")
        if token and self.secrets.get("lichess_token") == token:
            payload["lichess_token"] = ""

        for profile in payload.get("llm_profiles", []):
            api_key = profile.get("api_key", "")
            name = profile.get("name", "")
            if api_key and self.secrets.get(f"{SECRET_PROFILE_PREFIX}{name}") == api_key:
                profile.pop("api_key", None)

        try:
            with open(self.config_path, "w") as f:
                json.dump(payload, f, indent=4)
            logger.debug("Configuration saved successfully")
        except Exception as e:
            logger.error(f"Failed to save config: {e}")

    def _ensure_default_profile(self, cfg: dict) -> None:
        if not cfg.get("llm_profiles"):
            cfg["llm_profiles"] = [
                {
                    "name": "Groq",
                    "provider": "groq",
                    "api_key": "",
                    "model": "llama-3.3-70b-versatile",
                    "base_url": "",
                }
            ]
            cfg["llm_active_profile"] = "Groq"

    # ------------------------------------------------------------------
    # Profiles
    # ------------------------------------------------------------------
    def get_active_profile(self) -> dict:
        profiles = self.get_profiles()
        active_name = self.config.get("llm_active_profile", "")
        if profiles:
            for profile in profiles:
                if profile.get("name") == active_name:
                    return profile
            return profiles[0]
        return {}

    def get_profiles(self) -> list:
        profiles = deepcopy(self.config.get("llm_profiles", []))
        for profile in profiles:
            name = profile.get("name", "")
            profile["api_key"] = self.secrets.get(f"{SECRET_PROFILE_PREFIX}{name}")
        return profiles

    def set_profiles(self, profiles: list, active_name: str = "") -> None:
        sanitized = []
        for profile in profiles:
            entry = dict(profile)
            name = entry.get("name", "")
            self.secrets.set(
                f"{SECRET_PROFILE_PREFIX}{name}", entry.pop("api_key", "")
            )
            sanitized.append(entry)
        self.config["llm_profiles"] = sanitized
        if active_name:
            self.config["llm_active_profile"] = active_name
        self.save_config()

    # ------------------------------------------------------------------
    # Typed accessors
    # ------------------------------------------------------------------
    def _setting_default(self, key: str):
        spec = get_spec(key)
        return spec.default if spec is not None else None

    @property
    def board_theme(self) -> str:
        return self.get_choice("board_theme", str(self._setting_default("board_theme")))

    @property
    def piece_theme(self) -> str:
        return self.get_choice("piece_theme", str(self._setting_default("piece_theme")))

    @property
    def theme_mode(self) -> str:
        return self.get_choice("theme_mode", str(self._setting_default("theme_mode")))

    @property
    def accent_color(self) -> str:
        value = self.get("accent_color", self._setting_default("accent_color"))
        return str(value or "")

    @property
    def accent_mode(self) -> str:
        return self.get_choice("accent_mode", str(self._setting_default("accent_mode")))

    @property
    def toast_position(self) -> str:
        return self.get_choice(
            "toast_position", str(self._setting_default("toast_position"))
        )

    @property
    def sidebar_start_collapsed(self) -> bool:
        return self.get_bool(
            "sidebar_start_collapsed",
            bool(self._setting_default("sidebar_start_collapsed")),
        )

    @property
    def remember_window_geometry(self) -> bool:
        return self.get_bool(
            "remember_window_geometry",
            bool(self._setting_default("remember_window_geometry")),
        )

    @property
    def window_state(self) -> dict:
        value = self.get("window_state", self._setting_default("window_state") or {})
        return deepcopy(value) if isinstance(value, dict) else {}

    @property
    def sound_enabled(self) -> bool:
        return self.get_bool("sound_enabled", bool(self._setting_default("sound_enabled")))

    @property
    def sound_volume(self) -> int:
        return self.get_int("sound_volume", int(self._setting_default("sound_volume")))

    @property
    def settings_mode(self) -> str:
        return self.get_choice("settings_mode", str(self._setting_default("settings_mode")))

    @property
    def history_view_mode(self) -> str:
        return self.get_choice(
            "history_view_mode", str(self._setting_default("history_view_mode"))
        )

    @property
    def metrics_card_order(self) -> list:
        value = self.get(
            "metrics_card_order", self._setting_default("metrics_card_order") or []
        )
        return deepcopy(value) if isinstance(value, list) else []

    @property
    def shortcut_preset(self) -> str:
        return self.get_choice(
            "shortcut_preset", str(self._setting_default("shortcut_preset"))
        )

    @property
    def tour_seen_pages(self) -> dict:
        value = self.get("tour_seen_pages", self._setting_default("tour_seen_pages") or {})
        return deepcopy(value) if isinstance(value, dict) else {}

    @property
    def import_show_boards(self) -> bool:
        return self.get_bool(
            "import_show_boards", bool(self._setting_default("import_show_boards"))
        )

    # ------------------------------------------------------------------
    # Accounts / prompts accessors
    # ------------------------------------------------------------------
    @property
    def chesscom_username(self) -> str:
        return str(
            self.get("chesscom_username", self._setting_default("chesscom_username"))
            or ""
        )

    @property
    def lichess_username(self) -> str:
        return str(
            self.get("lichess_username", self._setting_default("lichess_username")) or ""
        )

    @property
    def player_usernames(self) -> tuple[str, ...]:
        """Configured usernames, stripped and casefolded for comparison."""
        names = (self.chesscom_username, self.lichess_username)
        return tuple(name.strip().casefold() for name in names if name.strip())

    @property
    def lichess_token(self) -> str:
        return str(
            self.get("lichess_token", self._setting_default("lichess_token")) or ""
        )

    @property
    def lichess_explorer_enabled(self) -> bool:
        return self.get_bool(
            "lichess_explorer_enabled",
            bool(self._setting_default("lichess_explorer_enabled")),
        )

    @property
    def llm_profiles(self) -> list[dict]:
        value = self.get("llm_profiles", self._setting_default("llm_profiles") or [])
        return value if isinstance(value, list) else []

    @property
    def llm_active_profile(self) -> str:
        return str(
            self.get("llm_active_profile", self._setting_default("llm_active_profile"))
            or ""
        )

    @property
    def explain_temperature(self) -> float:
        return self.get_float(
            "explain_temperature", float(self._setting_default("explain_temperature"))
        )

    @property
    def explain_max_tokens(self) -> int:
        return self.get_int(
            "explain_max_tokens", int(self._setting_default("explain_max_tokens"))
        )

    @property
    def explain_reasoning_effort(self) -> str:
        return self.get_choice(
            "explain_reasoning_effort",
            str(self._setting_default("explain_reasoning_effort") or ""),
        )

    @property
    def last_update_check(self) -> str:
        return str(
            self.get("last_update_check", self._setting_default("last_update_check"))
            or ""
        )

    @property
    def games_analyzed_count(self) -> int:
        return self.get_int(
            "games_analyzed_count", int(self._setting_default("games_analyzed_count"))
        )

    @property
    def review_submitted(self) -> bool:
        return self.get_bool(
            "review_submitted", bool(self._setting_default("review_submitted"))
        )

    @property
    def review_prompt_dismissed(self) -> bool:
        return self.get_bool(
            "review_prompt_dismissed",
            bool(self._setting_default("review_prompt_dismissed")),
        )

    @property
    def review_next_prompt_count(self) -> int:
        return self.get_int(
            "review_next_prompt_count",
            int(self._setting_default("review_next_prompt_count")),
        )

    # ------------------------------------------------------------------
    # Engine / analysis accessors
    # ------------------------------------------------------------------
    @property
    def engine_path(self) -> str:
        return str(self.get("engine_path", self._setting_default("engine_path")) or "")

    @property
    def polyglot_book_path(self) -> str:
        return str(
            self.get("polyglot_book_path", self._setting_default("polyglot_book_path"))
            or ""
        )

    @property
    def engine_threads(self) -> int:
        return self.get_int("engine_threads", int(self._setting_default("engine_threads")))

    @property
    def engine_hash(self) -> int:
        return self.get_int("engine_hash", int(self._setting_default("engine_hash")))

    @property
    def analysis_depth(self) -> int:
        return self.get_int(
            "analysis_depth", int(self._setting_default("analysis_depth"))
        )

    @property
    def multi_pv(self) -> int:
        return self.get_int("multi_pv", int(self._setting_default("multi_pv")))

    @property
    def time_per_move(self) -> float | None:
        value = self.get("time_per_move", self._setting_default("time_per_move"))
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            fallback = self._setting_default("time_per_move")
            return float(fallback) if fallback is not None else None

    @property
    def use_cache(self) -> bool:
        return self.get_bool("use_cache", bool(self._setting_default("use_cache")))

    @property
    def engine_lines_enabled(self) -> bool:
        return self.get_bool(
            "engine_lines_enabled", bool(self._setting_default("engine_lines_enabled"))
        )

    @property
    def live_analysis_time(self) -> float:
        return self.get_float(
            "live_analysis_time", float(self._setting_default("live_analysis_time"))
        )

    @property
    def live_multi_pv(self) -> int:
        return self.get_int(
            "live_multi_pv", int(self._setting_default("live_multi_pv"))
        )

    @property
    def coach_persona(self) -> str:
        return self.get_choice(
            "coach_persona", str(self._setting_default("coach_persona"))
        )

    @property
    def explain_llm_for_trivial_moves(self) -> bool:
        return self.get_bool(
            "explain_llm_for_trivial_moves",
            bool(self._setting_default("explain_llm_for_trivial_moves")),
        )

    @property
    def explain_cache_ttl_days(self) -> int | None:
        return self._nullable_int("explain_cache_ttl_days")

    @property
    def analysis_cache_max_entries(self) -> int:
        return self.get_int(
            "analysis_cache_max_entries",
            int(self._setting_default("analysis_cache_max_entries")),
        )

    @property
    def explorer_cache_ttl_hours(self) -> int | None:
        return self._nullable_int("explorer_cache_ttl_hours")

    @property
    def profile_cache_ttl_hours(self) -> int | None:
        return self._nullable_int("profile_cache_ttl_hours")

    @property
    def api_games_limit(self) -> int:
        return self.get_int(
            "api_games_limit", int(self._setting_default("api_games_limit"))
        )

    def _nullable_int(self, key: str) -> int | None:
        value = self.get(key, self._setting_default(key))
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            fallback = self._setting_default(key)
            return int(fallback) if fallback is not None else None

    # ------------------------------------------------------------------
    # Public accessors
    # ------------------------------------------------------------------
    def reload_config(self):
        self.secrets.reload()
        new_data = self.load_config()
        if self.__class__._shared_config is not None:
            self.__class__._shared_config.clear()
            self.__class__._shared_config.update(new_data)
        else:
            self.__class__._shared_config = new_data
        self.config = self.__class__._shared_config

    def save_config(self):
        self._migrate_secrets(self.config)
        self._write_config(self.config)

    def get(self, key, default=None):
        if key == "llm_profiles":
            return self.get_profiles()
        if key == "lichess_token":
            return self.secrets.get("lichess_token", default or "")
        return self.config.get(key, default)

    def get_bool(self, key: str, default: bool = False) -> bool:
        value = self.get(key, default)
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}
        return default

    def get_int(self, key: str, default: int = 0) -> int:
        try:
            return int(self.get(key, default))
        except (TypeError, ValueError):
            return default

    def get_float(self, key: str, default: float = 0.0) -> float:
        try:
            return float(self.get(key, default))
        except (TypeError, ValueError):
            return default

    def get_choice(self, key: str, default: str = "") -> str:
        spec = get_spec(key)
        value = str(self.get(key, default))
        if (
            spec
            and spec.choices
            and not spec.open_choice
            and value not in {c.value for c in spec.choices}
        ):
            return default
        return value

    def set(self, key, value):
        if key == "llm_profiles":
            self.set_profiles(value)
            return
        if key == "lichess_token":
            self.secrets.set("lichess_token", value or "")
            self.config[key] = ""
            return
        self.config[key] = self._coerce(key, value)
        self.save_config()

    def _coerce(self, key: str, value):
        """Validate/coerce known settings against the registry."""
        spec = get_spec(key)
        if spec is None:
            return value
        try:
            if spec.kind == "bool":
                if not isinstance(value, bool):
                    raise ValueError("expected bool")
                return value
            if spec.kind in {"int", "float"} and value is None:
                if spec.nullable:
                    return None
                raise ValueError("expected a number, got None")
            if spec.kind == "int":
                if isinstance(value, bool):
                    raise ValueError("bool is not an int setting")
                number = int(value)
                if spec.minimum is not None:
                    number = max(int(spec.minimum), number)
                if spec.maximum is not None:
                    number = min(int(spec.maximum), number)
                return number
            if spec.kind == "float":
                number = float(value)
                if spec.minimum is not None:
                    number = max(float(spec.minimum), number)
                if spec.maximum is not None:
                    number = min(float(spec.maximum), number)
                return number
            if spec.kind == "choice":
                if (
                    spec.choices
                    and not spec.open_choice
                    and value not in {c.value for c in spec.choices}
                ):
                    raise ValueError(f"expected one of {[c.value for c in spec.choices]}")
                return value
            if spec.kind in {"text", "path", "secret", "json"}:
                return value
        except (TypeError, ValueError) as exc:
            logger.warning("Config: invalid value for %s (%r): %s", key, value, exc)
            return self.config.get(key, spec.default)
        return value
