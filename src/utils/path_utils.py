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
        base_path = os.path.abspath(".")

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
