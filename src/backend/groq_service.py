"""
Provider-agnostic LLM service using the OpenAI-compatible API.

All supported providers expose an OpenAI-compatible /v1/chat/completions
endpoint, so a single openai.OpenAI client covers them all:

  - Groq       https://api.groq.com/openai/v1
  - LM Studio  http://localhost:1234/v1  (local, no key required)
  - MiniMax    https://api.minimax.chat/v1
  - Custom     any OpenAI-compatible base URL

The class is still named GroqService for backward compatibility with all
existing import sites.
"""

import locale
import os

from openai import OpenAI

from ..utils.config import ConfigManager
from ..utils.logger import logger

# ---------------------------------------------------------------------------
# Provider catalogue — drives both the service logic and the Settings UI.
# ---------------------------------------------------------------------------
PROVIDERS: dict[str, dict] = {
    "groq": {
        "label": "Groq (Cloud)",
        "base_url": "https://api.groq.com/openai/v1",
        "default_model": "llama-3.3-70b-versatile",
        "requires_key": True,
        "key_placeholder": "gsk_…",
        "model_placeholder": "llama-3.3-70b-versatile",
        "help_url": "https://console.groq.com",
    },
    "lmstudio": {
        "label": "LM Studio (Local)",
        "base_url": "http://localhost:1234/v1",
        "default_model": "local-model",
        "requires_key": False,
        "key_placeholder": "(not required)",
        "model_placeholder": "local-model",
        "help_url": "https://lmstudio.ai",
    },
    "minimax": {
        "label": "MiniMax (Cloud)",
        "base_url": "https://api.minimax.io/v1",   # international; China: api.minimaxi.com/v1
        "default_model": "MiniMax-M3",
        "requires_key": True,
        "key_placeholder": "your MiniMax API key",
        "model_placeholder": "MiniMax-M3",
        "help_url": "https://platform.minimax.io",
    },
    "custom": {
        "label": "Custom (OpenAI-compatible)",
        "base_url": "",
        "default_model": "",
        "requires_key": False,
        "key_placeholder": "API key (if required)",
        "model_placeholder": "model-name",
        "help_url": "",
    },
}

# ---------------------------------------------------------------------------
# Language detection
# ---------------------------------------------------------------------------
_LANG_NAMES: dict[str, str] = {
    "de": "German",   "fr": "French",    "es": "Spanish",
    "it": "Italian",  "pt": "Portuguese", "nl": "Dutch",
    "pl": "Polish",   "ru": "Russian",   "tr": "Turkish",
    "ja": "Japanese", "zh": "Chinese",   "ko": "Korean",
    "ar": "Arabic",   "sv": "Swedish",   "da": "Danish",
    "fi": "Finnish",  "nb": "Norwegian", "cs": "Czech",
    "sk": "Slovak",   "hu": "Hungarian", "ro": "Romanian",
}


def _detect_ui_language() -> str:
    """
    Return a human-readable language name that matches the current system UI
    locale so LLM responses can be requested in the user's language.

    Resolution order:
      1. LANG / LANGUAGE environment variables  (most reliable on Linux)
      2. Python locale.getdefaultlocale()
      3. Falls back to 'English'
    """
    try:
        lang_env = os.environ.get("LANG") or os.environ.get("LANGUAGE") or ""
        code = lang_env.split(".")[0].split("_")[0].lower()
        if not code:
            loc = locale.getdefaultlocale()
            code = (loc[0] or "").split("_")[0].lower()
    except Exception:
        code = ""
    return _LANG_NAMES.get(code, "English")


# ---------------------------------------------------------------------------
# Service class
# ---------------------------------------------------------------------------

class GroqService:
    """
    OpenAI-compatible LLM service with pluggable, multi-profile provider
    selection.

    Reads its configuration from ConfigManager (active LLM profile).
    The 'client' attribute is non-None when the service is ready to use,
    matching the existing 'if not self.groq_service.client' guard pattern.
    """

    def __init__(self) -> None:
        self.client: OpenAI | None = None
        self._provider = "groq"
        self._api_key = ""
        self._model = ""
        self._base_url = ""
        self._connect_from_config()

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def _connect_from_config(self) -> None:
        """Read the active LLM profile from ConfigManager and connect."""
        cfg = ConfigManager()
        profile = cfg.get_active_profile()

        provider = profile.get("provider", "groq")
        api_key  = profile.get("api_key", "") or ""
        model    = profile.get("model", "") or ""
        base_url = profile.get("base_url", "") or ""

        # Env-var fallback for Groq (honours existing .env / GROQ_API_KEY)
        if provider == "groq" and not api_key:
            api_key = os.getenv("GROQ_API_KEY") or os.getenv("GROQ_KEY") or ""

        self._connect(provider, api_key, model, base_url)

    def configure(self, provider: str, api_key: str, model: str = "", base_url: str = "") -> None:
        """Reconfigure the service at runtime (e.g. after Settings save)."""
        self._connect(provider, api_key, model, base_url)

    @staticmethod
    def _normalise_provider(provider: str) -> str:
        """Match the provider key case-insensitively against PROVIDERS."""
        if not provider:
            return "custom"
        lower = provider.lower().strip()
        for key in PROVIDERS:
            if key.lower() == lower:
                return key
        return "custom"

    @staticmethod
    def _normalise_base_url(url: str) -> str:
        """Strip a trailing /chat/completions so the OpenAI SDK can append it."""
        if not url:
            return ""
        url = url.strip().rstrip("/")
        for suffix in ("/chat/completions", "/chat/completions/"):
            if url.endswith(suffix):
                url = url[: -len(suffix)].rstrip("/")
                break
        return url

    @staticmethod
    def _is_placeholder_key(key: str) -> bool:
        """Detect obviously-invalid keys copied from another config (Cursor, etc.)."""
        if not key:
            return False
        return key.startswith("${") or "${input:" in key

    def _connect(self, provider: str, api_key: str, model: str, base_url: str) -> None:
        provider = self._normalise_provider(provider)
        base_url = self._normalise_base_url(base_url)
        preset = PROVIDERS.get(provider, PROVIDERS["custom"])

        self._provider = provider
        self._api_key  = api_key
        self._model    = model or preset["default_model"]
        self._base_url = base_url or preset["base_url"]

        requires_key = preset["requires_key"]
        if requires_key and self._is_placeholder_key(self._api_key):
            logger.error(
                f"LLMService: provider '{provider}' API key is a placeholder "
                f"({self._api_key!r}) — enter a real key in Settings."
            )
            self.client = None
            return
        if requires_key and not self._api_key:
            logger.info(f"LLMService: provider '{provider}' requires an API key — not connected.")
            self.client = None
            return

        if not self._base_url:
            logger.warning(f"LLMService: no base URL for provider '{provider}' — not connected.")
            self.client = None
            return

        try:
            self.client = OpenAI(
                api_key=self._api_key or "not-needed",
                base_url=self._base_url,
            )
            logger.info(
                f"LLMService connected — provider={provider}, "
                f"model={self._model}, base_url={self._base_url}"
            )
        except Exception as exc:
            logger.error(f"LLMService: failed to create client: {exc}")
            self.client = None

    @property
    def model_name(self) -> str:
        return self._model

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _chat(self, prompt: str) -> str:
        """Send a single-turn chat message and return the response text."""
        if not self.client:
            return "Error: LLM not configured. Go to Settings → API Configuration."
        try:
            completion = self.client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": prompt}],
            )
            text = completion.choices[0].message.content
            return text.strip() if text else "No response generated."
        except Exception as exc:
            logger.error(f"LLMService: request failed: {exc}", exc_info=True)
            # Keep full error text — UI dialog lets the user copy it.
            exc_type = type(exc).__name__
            return f"Error [{exc_type}]: {exc}"

    @staticmethod
    def _lang_instruction() -> str:
        """Return a language instruction appended to every prompt."""
        lang = _detect_ui_language()
        if lang == "English":
            return ""   # LLMs default to English — no instruction needed
        return f"\n\nIMPORTANT: Write your entire response in {lang}."

    # ------------------------------------------------------------------
    # Public prompts
    # ------------------------------------------------------------------

    def generate_summary(self, pgn_text: str, analysis_summary: str,
                        time_stats: str = "") -> str:
        """Generate a chess-expert narrative summary for a single game."""
        if not self.client:
            return "Error: LLM not configured. Go to Settings → API Configuration."

        if len(pgn_text) > 10_000:
            pgn_text = pgn_text[:10_000] + "… (truncated)"

        time_block = ""
        if time_stats:
            time_block = (
                "\nClock data (per move):\n"
                f"{time_stats}\n\n"
                "When relevant, comment on time pressure, very fast blunders, "
                "or long thinks that paid off.\n"
            )

        prompt = (
            "You are a chess expert. Analyze the following chess game and the provided "
            "analysis summary.\n\n"
            "First, provide a short 'Game Comment' (e.g. Sharp, Tactical, Brilliant, "
            "Chaotic, Positional Masterpiece …) that captures the essence of the game.\n"
            "Then provide a concise, insightful summary (max 200 words). "
            "Highlight key turning points, brilliant moves, and major mistakes."
            + time_block +
            "\nFormat:\n"
            "Game Comment: [Your Comment]\n\n"
            "Summary:\n[Your Summary]\n\n"
            f"Analysis Summary:\n{analysis_summary}\n\n"
            f"PGN:\n{pgn_text}"
            + self._lang_instruction()
        )
        return self._chat(prompt)

    def generate_coach_insights(self, stats_text: str) -> str:
        """Generate 3 coaching tips from aggregate player statistics."""
        if not self.client:
            return "Error: LLM not configured. Go to Settings → API Configuration."

        prompt = (
            "You are a chess coach. Analyze the following statistics for your student:\n\n"
            f"{stats_text}\n\n"
            "Provide 3 specific, actionable, and encouraging insights or tips based on "
            "this data. Focus on win rate, accuracy, and opening or phase-specific trends. "
            "Keep it concise (bullet points). Use emojis where appropriate.\n\n"
            "Format:\n"
            "1. [Insight 1]\n"
            "2. [Insight 2]\n"
            "3. [Insight 3]"
            + self._lang_instruction()
        )
        return self._chat(prompt)
