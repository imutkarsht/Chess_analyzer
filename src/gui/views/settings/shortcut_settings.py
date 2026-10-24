"""Keyboard shortcut preset settings."""

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QGroupBox, QLabel, QVBoxLayout

from src.constants import SHORTCUT_PRESET_LABELS

from ...styles import Styles
from .components import SettingsBinder, SettingsForm, make_combo
from .helpers import create_icon_button


class ShortcutSettings(QGroupBox):
    """Lets the user pick a shortcut preset and view all shortcuts."""

    preset_changed = pyqtSignal(str)

    def __init__(self, config_manager, parent=None):
        super().__init__("Keyboard Shortcuts", parent)
        self.config_manager = config_manager
        self._bindings: list[dict] = []
        self.setStyleSheet(Styles.get_group_box_style())
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(10)

        self.desc_label = QLabel(
            "Select your preferred navigation keymap preset. "
            "Use the button below or press F1 to view all active shortcuts."
        )
        self.desc_label.setWordWrap(True)
        layout.addWidget(self.desc_label)

        self.form = SettingsForm(self)
        self.binder = SettingsBinder(self.config_manager, self.form, self)
        self.preset_combo = make_combo(300)
        for preset_id, label in SHORTCUT_PRESET_LABELS.items():
            self.preset_combo.addItem(label, preset_id)
        self.binder.add(
            "shortcut_preset",
            self.preset_combo,
            on_change=lambda _value: self.preset_changed.emit(self.current_preset()),
        )
        layout.addWidget(self.form)

        self.help_btn = create_icon_button(
            "View All Shortcuts", "fa5s.keyboard", self._open_help, self
        )
        self.help_btn.setMaximumWidth(200)
        layout.addWidget(self.help_btn)
        layout.addStretch(1)

        self.refresh_styles()

    def current_preset(self) -> str:
        return self.preset_combo.currentData()

    def set_bindings(self, bindings: list[dict]):
        self._bindings = bindings

    def reload_from_config(self):
        self.binder.load()

    def set_advanced_visible(self, visible):
        # Shortcuts are useful to every user.
        pass

    def refresh_styles(self, *args, **kwargs):
        self.setStyleSheet(Styles.get_group_box_style())
        self.desc_label.setStyleSheet(
            f"font-size: 12px; color: {Styles.COLOR_TEXT_SECONDARY}; "
            + Styles.get_transparent_label_style()
        )
        self.form.refresh_styles()
        self.preset_combo.setStyleSheet(Styles.get_combobox_style())
        self.help_btn.setStyleSheet(Styles.get_settings_default_button_style())

    def _open_help(self):
        window = self.window()
        if hasattr(window, "show_shortcuts_help"):
            window.show_shortcuts_help()
