import os
from PyQt6.QtGui import QIcon
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtCore import QUrl
from .logger import logger

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
        self.base_path = os.getcwd()
        self.assets_dir = os.path.join(self.base_path, "assets")
        self.images_path = os.path.join(self.assets_dir, "images")
        self.sounds_path = os.path.join(self.assets_dir, "sounds")
        
        # Cache
        self._icon_cache = {}
        self.players = {} # Cache players to avoid recreation
        self.audio_outputs = {}
        
        # Mappings
        self.icon_map = {
            "Brilliant": "brilliant.svg",
            "Great": "great_find.svg",
            "Best": "best.svg",
            "Excellent": "excellent.svg",
            "Good": "good.svg",
            "Book": "book.svg",
            "Inaccuracy": "inaccuracy.svg",
            "Mistake": "mistake.svg",
            "Miss": "missed_win.svg",
            "Blunder": "blunder.svg"
        }
        
        self.sound_map = {
            "move": "move-self.webm",
            "capture": "capture.webm",
            "check": "move-self.webm", # Fallback as no specific check sound
            "castle": "castle.webm",
            "game_end": "game-end.webm",
            "notify": "game-start.webm" # Use game-start for notify/start
        }

    def get_icon(self, name: str) -> QIcon:
        """Returns QIcon for the given classification name."""
        if name not in self.icon_map:
            # logger.warning(f"Icon name '{name}' not found in icon_map.")
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
             # logger.debug(f"Loaded icon '{name}' from {path}")
             pass
             
        self._icon_cache[name] = icon
        return icon

    def play_sound(self, name: str):
        """Plays the sound for the given event name using QMediaPlayer."""
        if name not in self.sound_map:
            return
            
        filename = self.sound_map[name]
        path = os.path.join(self.sounds_path, filename)
        
        if not os.path.exists(path):
            logger.warning(f"Sound file not found: {path}")
            return

        try:
            # Create player if not exists
            if name not in self.players:
                player = QMediaPlayer()
                audio_output = QAudioOutput()
                player.setAudioOutput(audio_output)
                audio_output.setVolume(1.0) # 100% volume
                player.setSource(QUrl.fromLocalFile(path))
                
                self.players[name] = player
                self.audio_outputs[name] = audio_output
            
            player = self.players[name]
            if player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
                player.stop()
            player.play()
            
        except Exception as e:
            logger.error(f"Error playing sound '{name}': {e}")
