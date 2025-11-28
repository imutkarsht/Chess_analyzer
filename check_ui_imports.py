import sys
import os

# Add src to path
sys.path.append(os.getcwd())

try:
    from src.gui.main_window import MainWindow
    print("Successfully imported MainWindow")
except Exception as e:
    print(f"Failed to import MainWindow: {e}")
    import traceback
    traceback.print_exc()
