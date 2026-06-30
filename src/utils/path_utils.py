import sys
import os

def get_resource_path(relative_path: str) -> str:
    """
    Get the absolute path to a resource, works for dev and for PyInstaller.
    
    Args:
        relative_path: The relative path to the resource (e.g., "assets/images/logo.png").
        
    Returns:
        The absolute path to the resource.
    """
    if hasattr(sys, '_MEIPASS'):
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    else:
        # Get the directory of path_utils.py and go up two levels to get the project root
        base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

    return os.path.join(base_path, relative_path)

def get_app_path() -> str:
    """
    Get the absolute path to the application directory.
    In dev: current working directory.
    In frozen exe: the directory containing the executable.
    
    Returns:
        The absolute path to the application directory.
    """
    if getattr(sys, 'frozen', False):
        # If the application is run as a bundle, the PyInstaller bootloader
        # extends the sys module by a flag frozen=True and sets the app 
        # path into variable _MEIPASS'.
        return os.path.dirname(sys.executable)
    else:
        return os.path.abspath(".")

def get_user_data_dir() -> str:
    """
    Get the platform-specific directory for user data.
    - macOS: ~/Library/Application Support/ChessAnalyzerPro
    - Windows: %APPDATA%/ChessAnalyzerPro
    - Linux: ~/.local/share/chessanalyzerpro
    """
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA")
        if appdata:
            base_dir = os.path.join(appdata, "ChessAnalyzerPro")
        else:
            base_dir = os.path.expanduser("~\\AppData\\Roaming\\ChessAnalyzerPro")
    elif sys.platform == "darwin":
        base_dir = os.path.expanduser("~/Library/Application Support/ChessAnalyzerPro")
    else:
        # Linux/Unix
        data_home = os.environ.get("XDG_DATA_HOME")
        if data_home:
            base_dir = os.path.join(data_home, "chessanalyzerpro")
        else:
            base_dir = os.path.expanduser("~/.local/share/chessanalyzerpro")

    os.makedirs(base_dir, exist_ok=True)
    return base_dir


def get_stockfish_common_paths() -> list[str]:
    """Return a list of common Stockfish binary paths for the current platform.

    These are checked during auto-detection before falling back to download.
    Order matters — more specific/likely paths come first.
    """
    if sys.platform == "darwin":
        return [
            "/opt/homebrew/bin/stockfish",     # Apple Silicon Homebrew
            "/usr/local/bin/stockfish",         # Intel Homebrew / manual
            "/opt/homebrew/bin/stockfish.exe",  # Wine cross-build (rare)
        ]
    elif sys.platform == "win32":
        return [
            "C:\\Program Files\\Stockfish\\stockfish.exe",
            "C:\\Program Files (x86)\\Stockfish\\stockfish.exe",
            os.path.expanduser("~\\AppData\\Local\\Stockfish\\stockfish.exe"),
        ]
    else:
        return [
            "/usr/bin/stockfish",
            "/usr/local/bin/stockfish",
            "/usr/games/stockfish",
        ]


def get_engine_data_dir() -> str:
    """Return the platform-specific directory for engine binaries.

    Returns a subdirectory of get_user_data_dir() named 'engine'.
    """
    engine_dir = os.path.join(get_user_data_dir(), "engine")
    os.makedirs(engine_dir, exist_ok=True)
    return engine_dir

