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
from typing import Any

from openai import OpenAI

from src.constants import (
    EXPLANATION_MAX_TOKENS,
    EXPLANATION_REASONING_EFFORT,
    EXPLANATION_REQUEST_TIMEOUT_S,
    EXPLANATION_TEMPERATURE,
    PROVIDERS,
)
from src.utils.config import ConfigManager
from src.utils.logger import logger

# ---------------------------------------------------------------------------
# Language detection
# ---------------------------------------------------------------------------
_LANG_NAMES: dict[str, str] = {
    "en": "English",  # Default language
    "de": "German",
    "fr": "French",
    "es": "Spanish",
    "it": "Italian",
    "pt": "Portuguese",
    "nl": "Dutch",
    "pl": "Polish",
    "ru": "Russian",
    "tr": "Turkish",
    "ja": "Japanese",
    "zh": "Chinese",
    "ko": "Korean",
    "ar": "Arabic",
    "sv": "Swedish",
    "da": "Danish",
    "fi": "Finnish",
    "nb": "Norwegian",
    "cs": "Czech",
    "sk": "Slovak",
    "hu": "Hungarian",
    "ro": "Romanian",
}

# Localised section labels for the AI summary. Keys are the language
# codes that _LANG_NAMES also uses. The English keys are the defaults
# and are required; missing languages fall back to English.
_SECTION_LABELS: dict[str, dict[str, str]] = {
    "en": {"game_comment": "Game Comment", "summary": "Summary"},
    "de": {"game_comment": "Spielkommentar", "summary": "Zusammenfassung"},
}

# Prompt budgets. A normal game's move list is under 2 KB, so these only bite on
# pathological inputs, while keeping every request comfortably inside the
# context window of the smaller local models.
_MAX_PGN_CHARS = 5_000
_MAX_FACTS_CHARS = 3_500


def _detect_ui_locale_code() -> str:
    """Return the two-letter language code (e.g. 'de', 'en') of the UI locale.

    Same resolution as _detect_ui_language but stops at the code; used to
    look up _SECTION_LABELS.
    """
    try:
        lang_env = os.environ.get("LANG") or os.environ.get("LANGUAGE") or ""
        code = lang_env.split(".")[0].split("_")[0].lower()
        if not code:
            loc = locale.getlocale()
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
      2. Python locale.getlocale()
      3. Falls back to 'English'
    """
    try:
        lang_env = os.environ.get("LANG") or os.environ.get("LANGUAGE") or ""
        code = lang_env.split(".")[0].split("_")[0].lower()
        if not code:
            loc = locale.getlocale()
            code = (loc[0] or "").split("_")[0].lower()
    except Exception:
        code = ""
    return _LANG_NAMES.get(code, "English")


# ---------------------------------------------------------------------------
# Move explanation (Coach feature): prompt + mandatory reply validation
# ---------------------------------------------------------------------------

# The model is a translator, never a calculator: every chess fact it may mention
# is already in the fact sheet produced by
# src.backend.analysis.tactics.insight.format_move_insight_for_llm().
EXPLANATION_SYSTEM_PROMPT = (
    "You are a chess coach. Translate ONLY the facts below into 2-3 sentences. "
    "Never name a move, piece, or square that is not listed. "
    "Do not calculate. Do not add pleasantries. "
    "The facts give evaluations from White's perspective and win chances from the "
    "player's perspective. Quote both exactly as given: never flip a sign, never "
    "convert one perspective to the other, and never calculate a win chance from "
    "an evaluation."
)

# SAN-like move token, including castling and promotion.
SAN_TOKEN_RE = re.compile(r"\b(?:O-O-O|O-O|[KQRBN]?[a-h]?[1-8]?x?[a-h][1-8](?:=[QRBN])?)[+#]?\b")
# A bare board square, e.g. "e4".
SQUARE_TOKEN_RE = re.compile(r"\b[a-h][1-8]\b")
_SAN_DEST_RE = re.compile(r"[a-h][1-8]")


def _normalise_san(token: str) -> str:
    """Drop check/mate suffixes so ``Bxf7+`` and ``Bxf7#`` compare equal."""
    return token.rstrip("+#")


def _destination(token: str) -> str | None:
    """Destination square of a SAN token (``exd5`` -> ``d5``)."""
    match = _SAN_DEST_RE.search(token)
    return match.group(0) if match else None


def validate_explanation(
    reply: str,
    allowed_san: set[str],
    allowed_squares: set[str],
) -> tuple[bool, list[str]]:
    """
    Mandatory hallucination guard (D5): the LLM may only reference moves and
    squares that were handed to it in the fact sheet.

    Returns ``(is_valid, offending_tokens)``. The caller must **discard** an
    invalid reply entirely and fall back to the deterministic offline text —
    never patch or partially render it.
    """
    text = (reply or "").strip()
    if not text or text.startswith("Error"):
        return False, []

    allowed = {_normalise_san(token) for token in allowed_san}
    squares = set(allowed_squares)
    allowed_destinations = {_destination(token) for token in allowed}

    offending: list[str] = []
    for token in SAN_TOKEN_RE.findall(text):
        normalised = _normalise_san(token)
        if normalised in allowed:
            continue
        # A bare pawn-style token ("e4") is how the fact sheet also names a square.
        if len(normalised) <= 2 and normalised in squares:
            continue
        offending.append(token)
    for square in SQUARE_TOKEN_RE.findall(text):
        if square in squares or square in allowed_destinations:
            continue
        offending.append(square)

    if offending:
        offending = sorted(set(offending))
        logger.warning("explanation rejected: unknown tokens %s", offending)
        return False, offending
    return True, []


# ---------------------------------------------------------------------------
# Service class
# ---------------------------------------------------------------------------


def explanation_tuning(cfg=None) -> tuple[float, int, str]:
    """Read the user's move-explanation tuning with safe fallbacks.

    The settings UI constrains these values, but config.json is user-editable,
    so clamp again here rather than trusting whatever is on disk. ``cfg`` lets
    callers pass their injected ConfigManager (used by the settings Test button).
    """
    cfg = cfg or ConfigManager()
    try:
        temperature = float(cfg.get("explain_temperature", EXPLANATION_TEMPERATURE))
    except (TypeError, ValueError):
        temperature = EXPLANATION_TEMPERATURE
    try:
        max_tokens = int(cfg.get("explain_max_tokens", EXPLANATION_MAX_TOKENS))
    except (TypeError, ValueError):
        max_tokens = EXPLANATION_MAX_TOKENS

    effort = cfg.get("explain_reasoning_effort", EXPLANATION_REASONING_EFFORT) or ""
    if effort not in {"", "low", "medium", "high"}:
        effort = EXPLANATION_REASONING_EFFORT

    return (
        min(2.0, max(0.0, temperature)),
        min(4096, max(256, max_tokens)),
        effort,
    )


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
        api_key = profile.get("api_key", "") or ""
        model = profile.get("model", "") or ""
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
        return bool(re.fullmatch(r"x{2,}", candidate, flags=re.IGNORECASE))

    def _connect(self, provider: str, api_key: str, model: str, base_url: str) -> None:
        provider = self._normalise_provider(provider)
        base_url = self._normalise_base_url(base_url)
        preset = PROVIDERS.get(provider, PROVIDERS["custom"])

        self._provider = provider
        self._api_key = api_key
        self._model = model or preset["default_model"]
        self._base_url = base_url or preset["base_url"]

        requires_key = preset["requires_key"]
        if requires_key and self._is_placeholder_key(self._api_key):
            self.client = None
            return
        if requires_key and not self._api_key:
            self.client = None
            return

        if not self._base_url:
            self.client = None
            return

        try:
            self.client = OpenAI(
                api_key=self._api_key or "not-needed",
                base_url=self._base_url,
            )
            logger.info(
                "LLM client initialized: provider=%s, model=%s, base_url=%s",
                provider,
                self._model,
                self._base_url,
            )
        except Exception as e:
            logger.error("Failed to initialize OpenAI client for provider %s: %s", provider, e)
            self.client = None

    @property
    def model_name(self) -> str:
        return self._model

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _chat(
        self,
        prompt: str,
        system: str | None = None,
        *,
        timeout: float | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        max_retries: int | None = None,
        reasoning_effort: str | None = None,
    ) -> str:
        """Send a single-turn chat message and return the response text.

        ``prompt`` is always sent as the user message. ``system``, if given,
        is sent as a system message — this is the right place for
        language / role instructions, because models tend to *echo* a
        system-style instruction when it appears inside the user message.

        The optional keyword arguments are applied per request and default to
        the SDK's own behaviour, so existing callers are unaffected.
        """
        if not self.client:
            logger.warning("Attempted LLM completion but client is not configured")
            return "Error: LLM not configured. Go to Settings → API Configuration."
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        options: dict[str, Any] = {}
        if timeout is not None:
            options["timeout"] = timeout
        if max_tokens is not None:
            options["max_tokens"] = max_tokens
        if temperature is not None:
            options["temperature"] = temperature
        if reasoning_effort:
            options["reasoning_effort"] = reasoning_effort

        # Per-request retry policy (the SDK accepts it only on the client, so a
        # per-call copy is used instead of mutating the shared client).
        client = self.client
        if max_retries is not None:
            client = client.with_options(max_retries=max_retries)

        logger.info(
            "Sending LLM completion request: model=%s, prompt_len=%d, options=%s",
            self._model,
            len(prompt),
            sorted(options) or "defaults",
        )

        completion = None
        try:
            completion = client.chat.completions.create(
                model=self._model, messages=messages, **options
            )
        except Exception as exc:
            exc_type = type(exc).__name__
            logger.error("LLM completion failed [%s]: %s", exc_type, exc)
            return f"Error [{exc_type}]: {exc}"

        text = completion.choices[0].message.content
        logger.info("Received LLM completion response (%d chars)", len(text.strip()) if text else 0)
        return text.strip() if text else "No response generated."

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
            return ""  # LLMs default to English — no instruction needed
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

    def generate_summary(self, pgn_text: str, analysis_summary: str, time_stats: str = "") -> str:
        """
        Write the post-game report a strong coach would give for one game.

        ``analysis_summary`` must be ``build_game_report(game)`` — a compact text
        dossier of the engine's findings. The model is told to cite only those
        facts (move numbers, SAN, evaluations) so the narrative cannot drift away
        from what the analysis actually proved.
        """
        if not self.client:
            return "Error: LLM not configured. Go to Settings → API Configuration."

        if len(pgn_text) > _MAX_PGN_CHARS:
            pgn_text = pgn_text[:_MAX_PGN_CHARS] + "… (truncated)"
        if len(analysis_summary) > _MAX_FACTS_CHARS:
            analysis_summary = analysis_summary[:_MAX_FACTS_CHARS] + "… (truncated)"

        if time_stats:
            clock_section = f"\nCLOCK DATA:\n{time_stats}\n"
        else:
            clock_section = ""

        labels = self._section_labels()
        game_comment_lbl = labels["game_comment"]
        summary_lbl = labels["summary"]

        prompt = (
            "You are a chess coach writing the post-game report for the player.\n\n"
            "GROUND RULES\n"
            "- Use ONLY the facts in GAME FACTS, KEY MOMENTS and CLOCK DATA. Never invent a "
            "move, evaluation, tactic, opening name or clock situation.\n"
            "- Every claim about a mistake, a brilliancy or a turning point must cite the move "
            "number and SAN (e.g. 14.c3 or 23...Qxf2) plus the evaluation swing in pawns.\n"
            "- Evaluations are from White's perspective: positive means White is better. When you "
            'quote one for a player, make the side explicit (e.g. "-2.7 for White").\n'
            "- Win chances are labelled with the player they belong to. Quote them exactly as "
            "given: never calculate a win chance from an evaluation, and never present one "
            "player's win chance as another's. If a moment has no win chance in the facts, do "
            "not mention one.\n"
            '- The dossier says which side the report is for: address that player as "you" and '
            "judge the decisions from their point of view.\n"
            "- Do not mention the engine, the analysis, the data, or that you were given a dossier.\n"
            "- If something is not in the facts, say nothing about it. Accuracy beats colour.\n\n"
            "WHAT TO COVER, IN ORDER\n"
            "1. The character of the game in one short phrase.\n"
            "2. The story in order: how the opening went, where the balance first tipped, and how "
            "the result was actually decided.\n"
            "3. The decisive errors and the best moments, quantified with accuracy, ACPL and the "
            "evaluation swings from KEY MOMENTS.\n"
            "4. One concrete lesson the player can apply in the next game.\n\n"
            "LENGTH: 150-220 words of plain prose. No bullet points, no emojis, no markdown, no "
            "preamble and no closing pleasantries.\n\n"
            "Reply with EXACTLY this structure and nothing else:\n\n"
            f"{game_comment_lbl}: <2-5 word phrase, no trailing period>\n\n"
            f"{summary_lbl}:\n<the report>\n\n"
            "---\n"
            "INPUT — do not repeat any of this in your reply:\n\n"
            f"{analysis_summary or 'GAME FACTS: unavailable (game not analysed yet).'}\n"
            f"{clock_section}\n"
            f"MOVES (PGN):\n{pgn_text}"
        )
        return self._chat(prompt, system=self._lang_instruction())

    def explain_move(self, facts_text: str, classification: str) -> str:
        """
        Translate a grounded fact sheet into 2-3 instructive sentences.

        ``facts_text`` must be exactly
        ``format_move_insight_for_llm(insight)`` — all chess facts come from the
        deterministic builder, never from the model. The reply still has to pass
        ``validate_explanation()`` before it is shown.
        """
        if not self.client:
            return "Error: LLM not configured. Go to Settings → API Configuration."

        temperature, max_tokens, reasoning_effort = explanation_tuning()

        system = EXPLANATION_SYSTEM_PROMPT
        if classification:
            system += f" The move was classified as {classification}."
        lang_instruction = self._lang_instruction()
        if lang_instruction:
            system = f"{system}\n{lang_instruction}"

        return self._chat(
            facts_text,
            system=system,
            timeout=EXPLANATION_REQUEST_TIMEOUT_S,
            max_tokens=max_tokens,
            temperature=temperature,
            max_retries=0,
            reasoning_effort=reasoning_effort or None,
        )

    def generate_coach_insights(self, stats_text: str) -> str:
        """Generate structured coaching diagnostics from player performance dossier."""
        if not self.client:
            return "Error: LLM not configured. Go to Settings → API Configuration."

        prompt = (
            "You are an insightful, direct, and constructive chess coach analyzing a student's performance dossier.\n\n"
            f"{stats_text}\n\n"
            "Provide a rigorous, actionable coaching diagnostic divided into EXACTLY these 3 sections with markdown headers:\n\n"
            "### Strengths & Superpowers\n"
            "- **Title**: 1-2 concise sentences highlighting a specific proven strength (e.g. tactical vision, endgame technique, or opening preparation).\n"
            "- **Title**: 1-2 concise sentences highlighting another proven strength.\n\n"
            "### Critical Leaks & Blindspots\n"
            "- **Title**: 1-2 concise sentences diagnosing the primary rating leak (e.g. hanging pieces, moving too fast in Rapid/Classical, squandered winning leads, or endgame collapses).\n"
            "- **Title**: 1-2 concise sentences identifying another recurring mistake pattern.\n\n"
            "### Personalized Training Prescription\n"
            "- **Action**: Concrete practice routine addressing the primary leak (e.g. specific puzzle themes, clock pacing rules, or opening repertoire repairs).\n"
            "- **Action**: Concrete practice routine addressing the secondary leak.\n\n"
            "Critical Guidelines:\n"
            "- TIME MANAGEMENT RULE: NEVER praise fast move times in Rapid or Classical games as a strength! "
            "If the student moves in under 8 seconds per move in Rapid/Classical and leaves excess time on their clock while blundering, "
            "classify this as a CRITICAL LEAK ('Moving Too Fast / Blitzing in Rapid'). Instruct them to slow down and calculate.\n"
            "- Rely strictly on the data provided in the dossier.\n"
            "- Do NOT use emojis.\n"
            "- Keep the tone professional, direct, analytical, and encouraging.\n"
            "- Do NOT include conversational pleasantries, introductory greetings, or sign-offs."
        )
        return self._chat(prompt, system=self._lang_instruction())
