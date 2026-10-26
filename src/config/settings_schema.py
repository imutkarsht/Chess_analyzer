"""Single-source settings metadata and defaults.

Keep this module Qt-free so both the backend config store and the GUI can use it.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Literal

from src.constants import (
    DEFAULT_ANALYSIS_CACHE_MAX_ENTRIES,
    DEFAULT_ANALYSIS_DEPTH,
    DEFAULT_ENGINE_HASH_MB,
    DEFAULT_ENGINE_THREADS,
    DEFAULT_EXPLORER_CACHE_TTL_HOURS,
    DEFAULT_LIVE_ANALYSIS_TIME,
    DEFAULT_LIVE_MULTI_PV,
    DEFAULT_MULTI_PV,
    DEFAULT_PROFILE_CACHE_TTL_HOURS,
    EXPLANATION_MAX_TOKENS,
    EXPLANATION_REASONING_EFFORT,
    EXPLANATION_TEMPERATURE,
)

SettingKind = Literal[
    "bool", "int", "float", "text", "path", "secret", "choice", "json"
]
SettingTier = Literal["basic", "advanced", "internal"]
ApplyMode = Literal["live", "save", "restart", "derived"]


@dataclass(frozen=True)
class Choice:
    value: Any
    label: str


@dataclass(frozen=True)
class SettingSpec:
    key: str
    category: str
    subcategory: str
    label: str
    description: str
    kind: SettingKind
    default: Any
    tier: SettingTier = "basic"
    apply: ApplyMode = "save"
    choices: tuple[Choice, ...] = ()
    minimum: float | None = None
    maximum: float | None = None
    step: float | None = None
    secret: bool = False
    nullable: bool = False
    persist_default: bool = True
    ui: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


def _specs() -> tuple[SettingSpec, ...]:
    return (
        # ------------------------------------------------------------
        # Analysis / Engine
        # ------------------------------------------------------------
        SettingSpec(
            "engine_path",
            "Analysis",
            "Engine",
            "Stockfish path",
            "Path or command name for the UCI engine binary.",
            "path",
            "stockfish",
            apply="restart",
        ),
        SettingSpec(
            "engine_threads",
            "Analysis",
            "Engine",
            "Engine threads",
            "CPU threads used by Stockfish. Higher values increase heat and power use.",
            "int",
            DEFAULT_ENGINE_THREADS,
            tier="advanced",
            apply="derived",
            minimum=1,
            maximum=64,
            step=1,
            persist_default=False,
        ),
        SettingSpec(
            "engine_hash",
            "Analysis",
            "Engine",
            "Engine hash (MB)",
            "Transposition-table memory used by Stockfish.",
            "int",
            DEFAULT_ENGINE_HASH_MB,
            tier="advanced",
            apply="derived",
            minimum=16,
            maximum=4096,
            step=16,
            persist_default=False,
        ),
        SettingSpec(
            "analysis_depth",
            "Analysis",
            "Full Analysis",
            "Analysis depth",
            "Stockfish search depth for full-game analysis.",
            "int",
            DEFAULT_ANALYSIS_DEPTH,
            minimum=10,
            maximum=25,
            step=1,
        ),
        SettingSpec(
            "time_per_move",
            "Analysis",
            "Full Analysis",
            "Time cap per position",
            "Analysis stops at this time or at the depth above, whichever comes first. "
            "'No cap' searches to the selected depth only.",
            "float",
            1.0,
            nullable=True,
            minimum=0.5,
            maximum=10.0,
            step=0.5,
        ),
        SettingSpec(
            "multi_pv",
            "Analysis",
            "Full Analysis",
            "Multi-PV lines",
            "Number of candidate lines returned by the engine.",
            "int",
            DEFAULT_MULTI_PV,
            tier="advanced",
            apply="restart",
            minimum=1,
            maximum=5,
            step=1,
        ),
        SettingSpec(
            "use_cache",
            "Analysis",
            "Full Analysis",
            "Reuse cached evaluations",
            "Reuse stored engine results for positions already analyzed at the same or higher depth.",
            "bool",
            True,
            apply="live",
        ),
        SettingSpec(
            "live_analysis_time",
            "Analysis",
            "Live Analysis",
            "Live analysis budget (s)",
            "Time budget per position for the live engine panel.",
            "float",
            DEFAULT_LIVE_ANALYSIS_TIME,
            tier="advanced",
            minimum=0.5,
            maximum=10.0,
            step=0.1,
        ),
        SettingSpec(
            "live_multi_pv",
            "Analysis",
            "Live Analysis",
            "Live engine lines",
            "Candidate lines shown by the live engine in the analysis and explorer panels.",
            "int",
            DEFAULT_LIVE_MULTI_PV,
            tier="advanced",
            apply="live",
            minimum=1,
            maximum=5,
            step=1,
        ),
        SettingSpec(
            "engine_lines_enabled",
            "Analysis",
            "Live Analysis",
            "Show engine lines",
            "Start the live engine lines panel automatically after a move is selected.",
            "bool",
            False,
            apply="live",
        ),
        SettingSpec(
            "polyglot_book_path",
            "Opening Explorer",
            "Books & Databases",
            "Polyglot book",
            "Optional .bin Polyglot opening book.",
            "path",
            "",
        ),
        # ------------------------------------------------------------
        # Appearance
        # ------------------------------------------------------------
        SettingSpec(
            "theme_mode",
            "Appearance",
            "Theme & Accent",
            "Theme mode",
            "System, light, or dark application theme.",
            "choice",
            "system",
            apply="live",
            choices=(Choice("system", "System"), Choice("light", "Light"), Choice("dark", "Dark")),
        ),
        SettingSpec(
            "accent_mode",
            "Appearance",
            "Theme & Accent",
            "Accent mode",
            "Follow the system accent or use a custom colour.",
            "choice",
            "system",
            apply="live",
            choices=(Choice("system", "System"), Choice("custom", "Custom")),
        ),
        SettingSpec(
            "accent_color",
            "Appearance",
            "Theme & Accent",
            "Accent colour",
            "Custom accent colour in #RRGGBB form.",
            "text",
            "#FF9500",
            apply="live",
        ),
        SettingSpec(
            "board_theme",
            "Appearance",
            "Board & Pieces",
            "Board theme",
            "Colour theme for both analysis and explorer boards.",
            "choice",
            "Green",
            apply="live",
        ),
        SettingSpec(
            "piece_theme",
            "Appearance",
            "Board & Pieces",
            "Piece style",
            "Installed SVG piece set.",
            "choice",
            "Standard",
            apply="live",
        ),
        SettingSpec(
            "board_show_coordinates",
            "Appearance",
            "Board & Pieces",
            "Show coordinates",
            "Draw file/rank labels on the board.",
            "bool",
            True,
            apply="live",
        ),
        SettingSpec(
            "board_show_classification",
            "Appearance",
            "Board & Pieces",
            "Show move quality badges",
            "Show the classification badge on board move overlays.",
            "bool",
            True,
            apply="live",
        ),
        SettingSpec(
            "board_show_best_move_arrow",
            "Appearance",
            "Board & Pieces",
            "Show best-move arrow",
            "Draw the engine's top move as an arrow in Explorer and variation analysis.",
            "bool",
            True,
            tier="advanced",
            apply="live",
        ),
        SettingSpec(
            "board_show_last_move",
            "Appearance",
            "Board & Pieces",
            "Highlight last move",
            "Tint the squares of the last played move.",
            "bool",
            True,
            tier="advanced",
            apply="live",
        ),
        SettingSpec(
            "board_show_eval_bar",
            "Appearance",
            "Board & Pieces",
            "Show evaluation bar",
            "Show the vertical evaluation bar beside the analysis and explorer boards.",
            "bool",
            True,
            tier="advanced",
            apply="live",
        ),
        SettingSpec(
            "sidebar_start_collapsed",
            "Appearance",
            "Window & Layout",
            "Start sidebar collapsed",
            "Open the main sidebar in its collapsed state.",
            "bool",
            False,
            apply="live",
        ),
        SettingSpec(
            "remember_window_geometry",
            "Appearance",
            "Window & Layout",
            "Remember window layout",
            "Restore the window size and position from the last session.",
            "bool",
            True,
            apply="save",
        ),
        SettingSpec(
            "sound_enabled",
            "Appearance",
            "Sound & Feedback",
            "Sound effects",
            "Play move, capture, check, and game-end sounds.",
            "bool",
            True,
            apply="live",
        ),
        SettingSpec(
            "sound_volume",
            "Appearance",
            "Sound & Feedback",
            "Sound volume",
            "Volume for move, capture, check, and game-end sounds (0–100).",
            "int",
            50,
            tier="advanced",
            apply="live",
            minimum=0,
            maximum=100,
            step=5,
        ),
        SettingSpec(
            "history_view_mode",
            "Appearance",
            "Game History",
            "History view",
            "Default layout when Game History opens. The list header toggle "
            "still lets you switch at any time.",
            "choice",
            "compact",
            choices=(
                Choice("compact", "Compact list"),
                Choice("detailed", "Detailed cards"),
            ),
        ),
        SettingSpec(
            "window_state",
            "Appearance",
            "Window & Layout",
            "Window state",
            "Last window geometry.",
            "json",
            {"x": None, "y": None, "width": None, "height": None},
            tier="internal",
            ui=False,
        ),
        # ------------------------------------------------------------
        # Accounts / API
        # ------------------------------------------------------------
        SettingSpec(
            "chesscom_username",
            "Integrations",
            "Chess.com",
            "Chess.com username",
            "Username used for chess.com imports.",
            "text",
            "",
        ),
        SettingSpec(
            "lichess_username",
            "Integrations",
            "Lichess",
            "Lichess username",
            "Username used for Lichess imports.",
            "text",
            "",
        ),
        SettingSpec(
            "lichess_token",
            "Integrations",
            "Lichess",
            "Lichess API token",
            "Optional token for Lichess imports and the online opening explorer: raises the import cap from 20 to 30 games and unlocks private archives.",
            "secret",
            "",
            secret=True,
        ),
        SettingSpec(
            "lichess_explorer_enabled",
            "Integrations",
            "Lichess",
            "Online opening explorer",
            "Use the Lichess opening explorer (requires a Lichess token). Falls back to the local Polyglot book when unavailable.",
            "bool",
            True,
        ),
        SettingSpec(
            "api_games_limit",
            "Integrations",
            "Network",
            "Games fetch limit",
            "Maximum number of recent games to fetch (20 without a Lichess token, 30 with one).",
            "int",
            20,
            minimum=1,
            maximum=30,
            step=1,
        ),
        SettingSpec(
            "profile_cache_ttl_hours",
            "Integrations",
            "Network",
            "Profile cache TTL",
            "How long a fetched player profile stays fresh. Cached profiles are still shown offline.",
            "int",
            DEFAULT_PROFILE_CACHE_TTL_HOURS,
            minimum=1,
            maximum=168,
            step=1,
            nullable=True,
            choices=(
                Choice(1, "1 hour"),
                Choice(6, "6 hours"),
                Choice(24, "24 hours"),
                Choice(168, "7 days"),
                Choice(None, "Never expire"),
            ),
        ),
        SettingSpec(
            "llm_profiles",
            "AI Coach",
            "Providers & Profiles",
            "LLM profiles",
            "Configured OpenAI-compatible providers.",
            "json",
            [],
            tier="internal",
            ui=False,
        ),
        SettingSpec(
            "llm_active_profile",
            "AI Coach",
            "Providers & Profiles",
            "Active LLM profile",
            "Currently selected provider profile.",
            "text",
            "",
            tier="internal",
            ui=False,
        ),
        SettingSpec(
            "explain_llm_for_trivial_moves",
            "AI Coach",
            "Explanations",
            "Explain sound moves",
            "Also explain Best, Excellent, Good, and Book moves.",
            "bool",
            False,
            tier="basic",
        ),
        SettingSpec(
            "explain_temperature",
            "AI Coach",
            "Explanations",
            "Explanation temperature",
            "Lower is more literal; higher is more varied. Facts are still "
            "validated, but high values can add noise.",
            "float",
            EXPLANATION_TEMPERATURE,
            tier="advanced",
            minimum=0.0,
            maximum=2.0,
            step=0.1,
        ),
        SettingSpec(
            "explain_max_tokens",
            "AI Coach",
            "Explanations",
            "Max explanation tokens",
            "Caps the reply length. Reasoning models spend hidden tokens, so too "
            "low a value can return an empty explanation.",
            "int",
            EXPLANATION_MAX_TOKENS,
            tier="advanced",
            minimum=256,
            maximum=4096,
            step=128,
        ),
        SettingSpec(
            "explain_reasoning_effort",
            "AI Coach",
            "Explanations",
            "Reasoning effort",
            "Only reasoning models use this. Leave it on Provider default for "
            "models that do not support reasoning effort.",
            "choice",
            EXPLANATION_REASONING_EFFORT,
            tier="advanced",
            choices=(
                Choice("", "Provider default"),
                Choice("low", "Low"),
                Choice("medium", "Medium"),
                Choice("high", "High"),
            ),
        ),
        SettingSpec(
            "explain_cache_ttl_days",
            "Data & Storage",
            "Retention",
            "Explanation cache TTL",
            "How long LLM explanations are reused. 'Never expire' keeps them forever.",
            "int",
            30,
            tier="advanced",
            apply="live",
            minimum=7,
            maximum=365,
            step=1,
            nullable=True,
        ),
        # ------------------------------------------------------------
        # Data & Storage
        # ------------------------------------------------------------
        SettingSpec(
            "explorer_cache_ttl_hours",
            "Data & Storage",
            "Retention",
            "Explorer cache TTL",
            "How long cached opening-explorer responses are reused.",
            "int",
            DEFAULT_EXPLORER_CACHE_TTL_HOURS,
            tier="advanced",
            apply="live",
            minimum=1,
            maximum=8760,
            step=1,
            nullable=True,
        ),
        SettingSpec(
            "analysis_cache_max_entries",
            "Data & Storage",
            "Retention",
            "Cached evaluations kept",
            "Oldest cached engine evaluations are pruned beyond this count.",
            "int",
            DEFAULT_ANALYSIS_CACHE_MAX_ENTRIES,
            tier="advanced",
            apply="live",
            minimum=10000,
            maximum=1000000,
            step=10000,
        ),
        # ------------------------------------------------------------
        # Keyboard / internal UI state
        # ------------------------------------------------------------
        SettingSpec(
            "shortcut_preset",
            "Keyboard",
            "Presets",
            "Shortcut preset",
            "Standard or Vim navigation bindings.",
            "choice",
            "standard",
            apply="live",
            choices=(Choice("standard", "Standard"), Choice("vim", "Vim")),
        ),
        SettingSpec(
            "settings_mode",
            "General",
            "Updates",
            "Settings mode",
            "Basic or advanced settings visibility.",
            "choice",
            "basic",
            tier="internal",
            ui=False,
            choices=(Choice("basic", "Basic"), Choice("advanced", "Advanced")),
        ),
        SettingSpec(
            "games_analyzed_count",
            "General",
            "Updates",
            "Games analyzed",
            "Internal review-prompt counter.",
            "int",
            0,
            tier="internal",
            ui=False,
        ),
        SettingSpec(
            "review_submitted",
            "General",
            "Updates",
            "Review submitted",
            "Internal review-prompt state.",
            "bool",
            False,
            tier="internal",
            ui=False,
        ),
        SettingSpec(
            "review_prompt_dismissed",
            "General",
            "Updates",
            "Review prompt dismissed",
            "Internal review-prompt state.",
            "bool",
            False,
            tier="internal",
            ui=False,
        ),
        SettingSpec(
            "review_next_prompt_count",
            "General",
            "Updates",
            "Next review prompt",
            "Internal review-prompt threshold.",
            "int",
            3,
            tier="internal",
            ui=False,
        ),
        SettingSpec(
            "last_update_check",
            "General",
            "Updates",
            "Last update check",
            "Date of the last automatic update check.",
            "text",
            "",
            tier="internal",
            ui=False,
        ),
        SettingSpec(
            "tour_seen_pages",
            "General",
            "Updates",
            "Seen tour pages",
            "Tour pages already shown.",
            "json",
            {},
            tier="internal",
            ui=False,
        ),
        SettingSpec(
            "schema_version",
            "General",
            "Updates",
            "Config schema version",
            "Internal settings schema version.",
            "int",
            1,
            tier="internal",
            ui=False,
        ),
    )


SETTINGS: tuple[SettingSpec, ...] = _specs()
SETTINGS_BY_KEY: dict[str, SettingSpec] = {spec.key: spec for spec in SETTINGS}


def get_spec(key: str) -> SettingSpec | None:
    return SETTINGS_BY_KEY.get(key)


def default_config() -> dict[str, Any]:
    """Build the persisted default map.

    Specs marked ``persist_default=False`` deliberately stay absent so existing
    module-level fallbacks (engine threads/hash) keep working.
    """
    defaults: dict[str, Any] = {}
    for spec in SETTINGS:
        if not spec.persist_default:
            continue
        defaults[spec.key] = deepcopy(spec.default)
    return defaults


# Secret material is moved to secrets.json and never written to config.json.
SECRET_KEYS = frozenset({"lichess_token"})
SECRET_PROFILE_PREFIX = "llm_profile:"
