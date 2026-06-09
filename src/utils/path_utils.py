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

