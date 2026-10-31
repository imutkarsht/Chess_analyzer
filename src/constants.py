"""
Global application constants.
"""

# App Version
APP_VERSION = "2.5.0"

# GitHub & Project URLs
GITHUB_REPO_URL = "https://github.com/imutkarsht/Chess_analyzer"
GITHUB_RELEASES_API = "https://api.github.com/repos/imutkarsht/Chess_analyzer/releases/latest"
WEBSITE_URL = "https://chessanalyzer.xyz"
ABOUT_URL = "https://chessanalyzer.xyz/about"

# Project author
AUTHOR_NAME = "Utkarsh Tiwari"
AUTHOR_GITHUB_URL = "https://github.com/imutkarsht"
AUTHOR_LINKEDIN_URL = "https://www.linkedin.com/in/imutkarsht/"
AUTHOR_EMAIL = "uktiwari023@gmail.com"

# PGN Load Source IDs
SRC_PGN_FILE = 0
SRC_PGN_TEXT = 1
SRC_CHESSCOM = 2
SRC_LICHESS = 3

# API Constants
CHESSCOM_BASE_URL = "https://api.chess.com/pub"
CHESSCOM_HEADERS = {
    "User-Agent": f"ChessAnalyzerPro/{APP_VERSION} (https://github.com/imutkarsht/Chess_analyzer)"
}
LICHESS_BASE_URL = "https://lichess.org/api/games/user"
LICHESS_USER_URL = "https://lichess.org/api/user"
LICHESS_ACCOUNT_URL = "https://lichess.org/api/account"
LICHESS_EXPORT_URL = "https://lichess.org/game/export"
CHESSCOM_CALLBACK_LIVE = "https://www.chess.com/callback/live/game"
CHESSCOM_CALLBACK_DAILY = "https://www.chess.com/callback/daily/game"
LICHESS_EXPLORER_URL = "https://explorer.lichess.org/lichess"

# Feedback & Review API
FEEDBACK_API_BASE = "https://chessanalyzer.xyz"
FEEDBACK_REVIEWS_URL = "https://chessanalyzer.xyz/api/reviews"
FEEDBACK_URL = "https://chessanalyzer.xyz/api/feedback"
DEFAULT_REVIEW_PROMPT_THRESHOLD = 3
REVIEW_SNOOZE_INTERVAL = 5

# Matplotlib defaults
MATPLOTLIB_DPI = 100

# Default board theme for new installs. A warm wood tone sits better next to
# the app's neutral surfaces than the flat grey/green defaults.
DEFAULT_BOARD_THEME = "Brown"

# Platform Rules for Updater
PLATFORM_RULES = {
    "win32": {
        "priority_suffixes": ("-windows-setup.exe", "-setup.exe", ".exe"),
        "fallback_keywords": ("win", "windows"),
        "fallback_suffixes": (".exe", ".msi", ".zip"),
        "label": "Windows Installer (.exe)",
        "install_hint": "Run the downloaded Setup.exe to install.",
    },
    "darwin": {
        "priority_suffixes": ("-macos.dmg", ".dmg"),
        "fallback_keywords": ("mac", "macos", "darwin", "osx"),
        "fallback_suffixes": (".dmg", ".pkg", ".zip"),
        "label": "macOS Disk Image (.dmg)",
        "install_hint": "Open the .dmg and drag Chess Analyzer Pro to Applications.",
    },
    "linux": {
        "priority_suffixes": ("-x86_64.appimage", ".appimage"),
        "fallback_keywords": ("linux", "ubuntu", "debian"),
        "fallback_suffixes": (".appimage", ".tar.gz", ".tar.xz"),
        "label": "Linux AppImage",
        "install_hint": "chmod +x the AppImage, then run it — no installation needed.",
    },
}

# Engine Defaults (conservative — see issue #5)
DEFAULT_ENGINE_THREADS = 1
DEFAULT_ENGINE_HASH_MB = 128
DEFAULT_MULTI_PV = 2
DEFAULT_LIVE_MULTI_PV = 2
DEFAULT_LIVE_ANALYSIS_TIME = 0.5
DEFAULT_ANALYSIS_DEPTH = 18

# LLM Providers Catalogue
PROVIDERS = {
    "groq": {
        "label": "Groq (Cloud)",
        "base_url": "https://api.groq.com/openai/v1",
        "default_model": "llama-3.3-70b-versatile",
        "requires_key": True,
        "key_placeholder": "gsk_…",
        "model_placeholder": "llama-3.3-70b-versatile",
        "help_url": "https://console.groq.com",
    },
    "openai": {
        "label": "OpenAI (Cloud)",
        "base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4o-mini",
        "requires_key": True,
        "key_placeholder": "sk-proj-…",
        "model_placeholder": "gpt-4o-mini",
        "help_url": "https://platform.openai.com",
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
        "base_url": "https://api.minimax.io/v1",
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

# Minimum per-move accuracy (%), prevents harmonic mean collapse from outliers
MIN_MOVE_ACCURACY = 10.0

# ---------------------------------------------------------------------------
# Coach ("why was this a blunder?") feature
# ---------------------------------------------------------------------------
# Bump to invalidate every cached explanation (prompt/schema changes).
EXPLANATION_PROMPT_VERSION = 2
EXPLANATION_CACHE_TTL_DAYS = 30
EXPLANATION_REQUEST_TIMEOUT_S = 20.0
EXPLANATION_DEBOUNCE_MS = 400
EXPLANATION_MIN_INTERVAL_S = 3.0
EXPLANATION_MAX_PER_MINUTE = 20
# Reasoning models (e.g. openai/gpt-oss-*) spend tokens on hidden reasoning, so a
# small max_tokens silently yields an empty reply. 1024 plus a low effort (when
# the model supports reasoning_effort) is the combination validated in the R&D lab.
EXPLANATION_MAX_TOKENS = 1024
EXPLANATION_TEMPERATURE = 0.3
# Default omits the parameter so non-reasoning models never receive an
# unsupported option. Reasoning models can opt into low/medium/high.
EXPLANATION_REASONING_EFFORT = ""

# Classification buckets, expressed once and reused by the fact builder
# (offline wording) and the GUI (whether the Ask button is offered at all).
SOUND_CLASSIFICATIONS = frozenset({"Best", "Excellent", "Good", "Book"})
SACRIFICIAL_CLASSIFICATIONS = frozenset({"Brilliant", "Great"})
PROBLEM_CLASSIFICATIONS = frozenset({"Inaccuracy", "Mistake", "Miss", "Blunder"})
LLM_WORTHY_CLASSIFICATIONS = SACRIFICIAL_CLASSIFICATIONS | PROBLEM_CLASSIFICATIONS

# ---------------------------------------------------------------------------
# Local data retention
# ---------------------------------------------------------------------------
# Defaults shared by the storage layer and the settings schema so the two can
# never drift apart.
DEFAULT_EXPLORER_CACHE_TTL_HOURS = 48
DEFAULT_ANALYSIS_CACHE_MAX_ENTRIES = 250_000
# Chess.com refreshes public profile/stats data at most every 12–24 hours, so
# one day is the smallest useful default before re-fetching a preview.
DEFAULT_PROFILE_CACHE_TTL_HOURS = 24
# Expired profiles stay available for offline viewing, but are removed after
# this grace period so trying many usernames cannot grow the DB forever.
PROFILE_CACHE_MAX_AGE_DAYS = 90

# ---------------------------------------------------------------------------
# Keyboard shortcuts (issue #67)
# ---------------------------------------------------------------------------
# Indices into MainWindow.stack, in sidebar order.
PAGE_ANALYSIS = 0
PAGE_EXPLORER = 1
PAGE_HISTORY = 2
PAGE_METRICS = 3
PAGE_SETTINGS = 4

# Labels for the 1-5 "go to page" shortcuts. The order must match the indices above.
PAGE_NAMES = ("Analyze", "Explore", "History", "Metrics", "Settings")

# Delay between moves during Space auto-replay, in milliseconds.
REPLAY_INTERVAL_MS = 1000

# Classifications that N / Shift+Right and P / Shift+Left jump between.
# Inaccuracies are left out on purpose: they are too frequent to be "critical".
CRITICAL_CLASSIFICATIONS = frozenset({"Mistake", "Miss", "Blunder"})

# Each preset maps action ids to replacement keys. Actions a preset leaves out
# keep the defaults registered in NavigationMixin._setup_shortcuts(), where
# Right/J and Left/K always step through moves. Vim adds H/L on top; every
# preset keeps the defaults so switching never takes a binding away.
SHORTCUT_PRESETS = {
    "standard": {},
    "vim": {
        "nav_next": ("Right", "J", "L"),
        "nav_prev": ("Left", "K", "H"),
    },
}
SHORTCUT_PRESET_LABELS = {
    "standard": "Standard (Arrows + J/K)",
    "vim": "Vim (J/K/H/L)",
}
DEFAULT_SHORTCUT_PRESET = "standard"
