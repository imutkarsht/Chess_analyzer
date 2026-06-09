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
        logger.info(f"ResourceManager: Assets dir resolved to: {self.assets_dir}")
        
        self.images_path = os.path.join(self.assets_dir, "images")
        self.sounds_path = os.path.join(self.assets_dir, "sounds")
        
        logger.info(f"ResourceManager: Images path: {self.images_path}")
        if not os.path.exists(self.images_path):
            logger.error(f"ResourceManager: Images path does not exist!")
        else:
            try:
                files = os.listdir(self.images_path)
                logger.info(f"ResourceManager: Found {len(files)} files in images path")
            except Exception as e:
                logger.error(f"ResourceManager: Failed to list images path: {e}")
        
        # Cache
        self._icon_cache = {}
        # Each sound is backed by a small pool of QSoundEffect instances so
        # that rapid retriggers (e.g. stepping through a game move by move)
        # do not collide with a still-playing instance. A single QSoundEffect
        # silently drops reentrant play() calls while it is still busy, which
        # previously caused the move sound to be inaudible from the 4th step
        # onwards.
        self.SOUND_POOL_SIZE = 4
        self.sounds = {}              # name -> list[QSoundEffect]
        self._sound_index = {}        # name -> next pool index (round-robin)
        
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
        """Pre-load each sound into a pool of QSoundEffect instances."""
        for name, filename in self.sound_map.items():
            path = os.path.join(self.sounds_path, filename)
            if not os.path.exists(path):
                logger.warning(f"Sound file not found: {path}")
                continue
            pool = []
            for _ in range(self.SOUND_POOL_SIZE):
                effect = QSoundEffect()
                effect.setSource(QUrl.fromLocalFile(path))
                effect.setVolume(0.5)
                pool.append(effect)
            self.sounds[name] = pool
            self._sound_index[name] = 0

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
             
        self._icon_cache[name] = icon
        return icon

    def play_sound(self, name: str):
        """Plays the sound for the given event name using QSoundEffect.

        Uses a round-robin pool so that consecutive triggers of the same
        event (common while stepping through a game) do not collide with
        a still-playing instance of the same sound.
        """
        from .config import ConfigManager
        if not ConfigManager().get("sound_enabled", True):
            return

        pool = self.sounds.get(name)
        if not pool:
            return
        idx = self._sound_index[name]
        effect = pool[idx]
        self._sound_index[name] = (idx + 1) % len(pool)
        # Explicitly stop first: a QSoundEffect in a still-playing state
        # silently drops reentrant play() calls, so we always reset.
        if effect.isPlaying():
            effect.stop()
        effect.play()
