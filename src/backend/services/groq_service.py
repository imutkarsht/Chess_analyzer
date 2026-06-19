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
import re
from typing import Optional

from openai import OpenAI

from src.utils.config import ConfigManager
from src.utils.logger import logger

from src.constants import PROVIDERS

# ---------------------------------------------------------------------------
# Language detection
# ---------------------------------------------------------------------------
_LANG_NAMES: dict[str, str] = {
    "en": "English",  # Default language
    "de": "German",   "fr": "French",    "es": "Spanish",
    "it": "Italian",  "pt": "Portuguese", "nl": "Dutch",
    "pl": "Polish",   "ru": "Russian",   "tr": "Turkish",
    "ja": "Japanese", "zh": "Chinese",   "ko": "Korean",
    "ar": "Arabic",   "sv": "Swedish",   "da": "Danish",
    "fi": "Finnish",  "nb": "Norwegian", "cs": "Czech",
    "sk": "Slovak",   "hu": "Hungarian", "ro": "Romanian",
}

# Localised section labels for the AI summary. Keys are the language
# codes that _LANG_NAMES also uses. The English keys are the defaults
# and are required; missing languages fall back to English.
_SECTION_LABELS: dict[str, dict[str, str]] = {
    "en": {"game_comment": "Game Comment", "summary": "Summary"},
    "de": {"game_comment": "Spielkommentar", "summary": "Zusammenfassung"},
}


def _detect_ui_locale_code() -> str:
    """Return the two-letter language code (e.g. 'de', 'en') of the UI locale.

    Same resolution as _detect_ui_language but stops at the code; used to
    look up _SECTION_LABELS.
    """
    try:
        lang_env = os.environ.get("LANG") or os.environ.get("LANGUAGE") or ""
        code = lang_env.split(".")[0].split("_")[0].lower()
        if not code:
            loc = locale.getdefaultlocale()
            code = (loc[0] or "").split("_")[0].lower()
        return code or "en"
    except Exception:
        return "en"


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

        # Env-var fallback for OpenAI (honours existing .env / OPENAI_API_KEY)
        if provider == "openai" and not api_key:
            api_key = os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_KEY") or ""

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
        """Detect unfilled secret references that are clearly placeholders.

        Catches the common template/secret-manager formats people accidentally
        paste into config files:

        - ``${VAR}``            shell / docker-compose style
        - ``${input:VAR}``     GitHub Actions / 1Password CLI style
        - ``{{ secrets.X }}``  GitHub Actions Jinja style
        - ``<YOUR_KEY_HERE>``  README placeholders
        - ``xxxxxx…``           redaction artifacts

        A real Groq key starts with ``gsk_``; a real OpenAI key with ``sk-``.
        We only treat a string as a placeholder when it matches one of the
        explicit patterns above — never a blanket length check, so a
        legitimately short key isn't rejected.
        """
        if not key:
            return False
        # Strip surrounding whitespace once; comparison happens case-sensitively
        # because all the placeholder formats are themselves case-sensitive.
        candidate = key.strip()
        if not candidate:
            return True
        # Shell-style / GitHub Actions / 1Password: ${...} or ${input:...}
        if candidate.startswith("${") and candidate.endswith("}"):
            return True
        # GitHub Actions Jinja / template rendering: {{ ... }}
        if candidate.startswith("{{") and candidate.endswith("}}"):
            return True
        # README placeholders: <…>, <your-…-here>
        if candidate.startswith("<") and candidate.endswith(">"):
            lower = candidate.lower()
            if "your" in lower or "key" in lower or "token" in lower or "api" in lower:
                return True
        # Redaction artifact: 'xxxxxx' or 'XXXXXXXX' of any length >= 2
        # (single 'x' is too short to be a useful redaction marker)
        if re.fullmatch(r"x{2,}", candidate, flags=re.IGNORECASE):
            return True
        return False

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

    def _chat(self, prompt: str, system: Optional[str] = None) -> str:
        """Send a single-turn chat message and return the response text.

        ``prompt`` is always sent as the user message. ``system``, if given,
        is sent as a system message — this is the right place for
        language / role instructions, because models tend to *echo* a
        system-style instruction when it appears inside the user message.
        """
        if not self.client:
            return "Error: LLM not configured. Go to Settings → API Configuration."
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        try:
            completion = self.client.chat.completions.create(
                model=self._model,
                messages=messages,
            )
            text = completion.choices[0].message.content
            return text.strip() if text else "No response generated."
        except Exception as exc:
            logger.error(f"LLMService: request failed: {exc}", exc_info=True)
            # Keep full error text — UI dialog lets the user copy it.
            exc_type = type(exc).__name__
            return f"Error [{exc_type}]: {exc}"

    @staticmethod
    def _lang_code() -> str:
        """Two-letter language code (e.g. "de", "en") for the active UI locale."""
        return _detect_ui_locale_code()

    @staticmethod
    def _lang_instruction() -> str:
        """Return a language instruction for the system message.

        We send it as a separate system message (not as a suffix on the
        user prompt) because reasoning models tend to *echo* the
        instruction at the top of the answer when it appears inside the
        user message.
        """
        lang = _detect_ui_language()
        if lang == "English":
            return ""   # LLMs default to English — no instruction needed
        return f"Write your entire response in {lang}."

    @staticmethod
    def _section_labels() -> dict[str, str]:
        """Return the section-label translations for the active UI locale.

        Falls back to English for any language we don't ship labels for.
        """
        code = GroqService._lang_code()
        return _SECTION_LABELS.get(code, _SECTION_LABELS["en"])

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

        labels = self._section_labels()
        game_comment_lbl = labels["game_comment"]
        summary_lbl = labels["summary"]

        prompt = (
            "You are a chess expert. Analyze the following chess game and the provided "
            "analysis summary.\n\n"
            f"First, provide a short '{game_comment_lbl}' (e.g. Sharp, Tactical, "
            "Brilliant, Chaotic, Positional Masterpiece …) that captures the essence "
            "of the game.\n"
            f"Then provide a concise, insightful '{summary_lbl}' (max 200 words). "
            "Highlight key turning points, brilliant moves, and major mistakes."
            + time_block +
            "\n\nReply with EXACTLY this structure and nothing else — "
            "do not include any other section headers, do not echo the input "
            "labels, do not add a preamble or closing remark:\n\n"
            f"{game_comment_lbl}: <one short phrase>\n\n"
            f"{summary_lbl}:\n<the summary in prose>\n\n"
            "---\n"
            "INPUT — do not repeat any of this in your reply:\n\n"
            f"Analysis Summary:\n{analysis_summary}\n\n"
            f"PGN:\n{pgn_text}"
        )
        return self._chat(prompt, system=self._lang_instruction())

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
        )
        return self._chat(prompt, system=self._lang_instruction())
