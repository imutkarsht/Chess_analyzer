"""
Keyboard Shortcuts settings card: preset picker with quick access to all shortcuts.
"""

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QComboBox, QGroupBox, QHBoxLayout, QLabel, QVBoxLayout

from src.constants import DEFAULT_SHORTCUT_PRESET, SHORTCUT_PRESET_LABELS

from ...styles import Styles
from .helpers import create_icon_button


class ShortcutSettings(QGroupBox):
    """Lets the user pick a shortcut preset and view all shortcuts in the help dialog.

    The card does not own the shortcuts: MainWindow listens to
    ``preset_changed`` to apply the chosen scheme.
    """

    preset_changed = pyqtSignal(str)

    def __init__(self, config_manager, parent=None):
        super().__init__("Keyboard Shortcuts", parent)
        self.config_manager = config_manager
        self._bindings: list[dict] = []
        self.setStyleSheet(Styles.get_group_box_style())
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 12, 0, 0)
        layout.setSpacing(12)

        self.desc_label = QLabel(
            "Select your preferred navigation keymap preset. "
            "Use the button below or press F1 to view all active shortcuts."
        )
        self.desc_label.setWordWrap(True)
        layout.addWidget(self.desc_label)

        preset_row = QHBoxLayout()
        self.preset_label = QLabel("Preset:")
        preset_row.addWidget(self.preset_label)

        self.preset_combo = QComboBox()
        for preset_id, label in SHORTCUT_PRESET_LABELS.items():
            self.preset_combo.addItem(label, preset_id)
        self.preset_combo.setMaximumWidth(420)
        self._select_preset(self.config_manager.get("shortcut_preset", DEFAULT_SHORTCUT_PRESET))
        self.preset_combo.currentIndexChanged.connect(self._on_preset_selected)
        preset_row.addWidget(self.preset_combo, 1)
        layout.addLayout(preset_row)

        self.help_btn = create_icon_button(
            "View All Shortcuts", "fa5s.keyboard", self._open_help, self
        )
        self.help_btn.setMaximumWidth(220)
        layout.addWidget(self.help_btn)

        self.refresh_styles()

    def current_preset(self) -> str:
        return self.preset_combo.currentData()

    def set_bindings(self, bindings: list[dict]):
        """Keep reference to active bindings (all shortcuts are viewed in the help dialog)."""
        self._bindings = bindings

    def reload_from_config(self):
        self.preset_combo.blockSignals(True)
        self._select_preset(self.config_manager.get("shortcut_preset", DEFAULT_SHORTCUT_PRESET))
        self.preset_combo.blockSignals(False)

    def set_advanced_visible(self, visible):
        # Shortcuts are useful to every user, so the card stays in basic mode too.
        pass

    def refresh_styles(self, *args, **kwargs):
        self.setStyleSheet(Styles.get_group_box_style())
        self.desc_label.setStyleSheet(
            f"font-size: 12px; color: {Styles.COLOR_TEXT_SECONDARY}; {Styles.get_transparent_label_style()}"
        )
        self.preset_label.setStyleSheet(f"font-size: 14px; {Styles.get_transparent_label_style()}")
        self.preset_combo.setStyleSheet(Styles.get_combobox_style())
        self.help_btn.setStyleSheet(Styles.get_settings_default_button_style())

    def _select_preset(self, preset_id: str):
        index = self.preset_combo.findData(preset_id)
        self.preset_combo.setCurrentIndex(max(index, 0))

    def _on_preset_selected(self, _index: int):
        preset_id = self.current_preset()
        self.config_manager.set("shortcut_preset", preset_id)
        self.preset_changed.emit(preset_id)

    def _open_help(self):
        window = self.window()
        if hasattr(window, "show_shortcuts_help"):
            window.show_shortcuts_help()

