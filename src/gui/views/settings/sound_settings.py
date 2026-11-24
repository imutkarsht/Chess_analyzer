"""Sound feedback settings."""

from PyQt6.QtWidgets import QGroupBox, QVBoxLayout

from src.gui.components import SliderCounter
from src.gui.views.settings.components import SettingsBinder, SettingsForm


class SoundSettings(QGroupBox):
    """Move, capture, check, and game-end sound controls."""

    def __init__(self, config_manager, parent=None):
        super().__init__("Sound && Feedback", parent)
        self.config_manager = config_manager
        self.setProperty("settingsCard", True)
        self.setup_ui()

    def setup_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 8, 0, 0)

        self.form = SettingsForm(self)
        self.binder = SettingsBinder(self.config_manager, self.form, self)
        outer.addWidget(self.form)

        self.sound_checkbox = self.binder.add("sound_enabled")

        self.volume_input = SliderCounter(0, 100, step=5, parent=self)
        self.volume_input.setMaximumWidth(220)
        self.binder.add(
            "sound_volume",
            self.volume_input,
            hint="0–100; applies to every sound effect.",
            width=None,
        )

    # ------------------------------------------------------------------
    # Lifecycle hooks used by SettingsView
    # ------------------------------------------------------------------
    def reload_from_config(self):
        self.binder.load()

    def set_advanced_visible(self, visible):
        self.binder.set_advanced_visible(visible)

    def refresh_styles(self, *args, **kwargs):
        self.setProperty("settingsCard", True)
        self.form.refresh_styles()
        self.volume_input.refresh_styles()
