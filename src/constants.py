"""
Global application constants.
"""

# App Version
APP_VERSION = "2.0.1"

# GitHub Update Checker
GITHUB_RELEASES_API = "https://api.github.com/repos/imutkarsht/Chess_analyzer/releases/latest"

# PGN Load Source IDs
SRC_PGN_FILE = 0
SRC_PGN_TEXT = 1
SRC_CHESSCOM = 2
SRC_LICHESS = 3

# API Constants
CHESSCOM_BASE_URL = "https://api.chess.com/pub"
CHESSCOM_HEADERS = {
    "User-Agent": "ChessAnalyzer/1.0 (contact: your_email@example.com)"
}
LICHESS_BASE_URL = "https://lichess.org/api/games/user"

# Matplotlib defaults
MATPLOTLIB_DPI = 100

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
