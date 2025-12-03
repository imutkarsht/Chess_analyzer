import os
from PyQt6.QtGui import QIcon
from PyQt6.QtMultimedia import QSoundEffect
from PyQt6.QtCore import QUrl
from .logger import logger
from .path_utils import get_resource_path

class ResourceManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ResourceManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        
        # Base paths
        self.assets_dir = get_resource_path("assets")
        self.images_path = os.path.join(self.assets_dir, "images")
        self.sounds_path = os.path.join(self.assets_dir, "sounds")
        
        # Cache
        self._icon_cache = {}
        self.sounds = {} # Cache QSoundEffect objects
        
        # Mappings
        self.icon_map = {
            "Brilliant": "brilliant.svg",
            "Great": "great_find.svg",
            "Best": "best_v2.svg",
            "Excellent": "excellent.svg",
            "Good": "good.svg",
            "Book": "book.svg",
            "Inaccuracy": "inaccuracy.svg",
            "Mistake": "mistake.svg",
            "Miss": "missed_win.svg",
            "Blunder": "blunder.svg"
        }
        
        self.sound_map = {
            "move": "move.wav",
            "capture": "capture.wav",
            "check": "check.wav",
            "castle": "castle.wav",
            "game_end": "game_end.wav",
            "notify": "game_start.wav"
        }
        
        # Pre-load sounds
        self._preload_sounds()

    def _preload_sounds(self):
        """Pre-loads all sounds for low latency."""
        for name, filename in self.sound_map.items():
            path = os.path.join(self.sounds_path, filename)
            if os.path.exists(path):
                effect = QSoundEffect()
                effect.setSource(QUrl.fromLocalFile(path))
                effect.setVolume(0.5)
                self.sounds[name] = effect
            else:
                logger.warning(f"Sound file not found: {path}")

    def get_icon(self, name: str) -> QIcon:
        """Returns QIcon for the given classification name."""
        if name not in self.icon_map:
            return QIcon()
            
        if name in self._icon_cache:
            return self._icon_cache[name]
            
        filename = self.icon_map[name]
        path = os.path.join(self.images_path, filename)
        
        if not os.path.exists(path):
            logger.error(f"Icon file not found: {path}")
            return QIcon()
            
        icon = QIcon(path)
        if icon.isNull():
             logger.error(f"Failed to load icon from {path}")
        else:
             pass
             
        self._icon_cache[name] = icon
        return icon

    def play_sound(self, name: str):
        """Plays the sound for the given event name using QSoundEffect."""
        if name in self.sounds:
            self.sounds[name].play()
        else:
            # logger.warning(f"Sound '{name}' not loaded.")
            pass
