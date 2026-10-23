"""
Keyboard Shortcuts settings card: preset picker plus a live cheat-sheet.
"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QComboBox, QGroupBox, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from src.constants import DEFAULT_SHORTCUT_PRESET, SHORTCUT_PRESET_LABELS

from ...styles import Styles
from .helpers import create_icon_button


class ShortcutSettings(QGroupBox):
    """Lets the user pick a shortcut preset and shows the active bindings.

    The card does not own the shortcuts: MainWindow listens to
    ``preset_changed`` and pushes the resulting bindings back via
    ``set_bindings`` so the cheat-sheet always reflects what is live.
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
        layout.setContentsMargins(20, 30, 20, 20)
        layout.setSpacing(12)

        preset_row = QHBoxLayout()
        self.preset_label = QLabel("Preset:")
        preset_row.addWidget(self.preset_label)

        self.preset_combo = QComboBox()
        for preset_id, label in SHORTCUT_PRESET_LABELS.items():
            self.preset_combo.addItem(label, preset_id)
        self._select_preset(self.config_manager.get("shortcut_preset", DEFAULT_SHORTCUT_PRESET))
        self.preset_combo.currentIndexChanged.connect(self._on_preset_selected)
        preset_row.addWidget(self.preset_combo, 1)
        layout.addLayout(preset_row)

        self.sheet = QWidget()
        self.sheet_layout = QVBoxLayout(self.sheet)
        self.sheet_layout.setContentsMargins(0, 4, 0, 4)
        self.sheet_layout.setSpacing(6)
        layout.addWidget(self.sheet)

        self.help_btn = create_icon_button(
            "View All Shortcuts", "fa5s.keyboard", self._open_help, self
        )
        layout.addWidget(self.help_btn)

        self.refresh_styles()

    def current_preset(self) -> str:
        return self.preset_combo.currentData()

    def set_bindings(self, bindings: list[dict]):
        """Rebuild the cheat-sheet from ``ShortcutManager.get_bindings()``."""
        self._bindings = bindings
        while self.sheet_layout.count():
            item = self.sheet_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for binding in bindings:
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            desc = QLabel(binding["description"])
            desc.setStyleSheet(self._desc_style())
            keys = QLabel("  /  ".join(binding["keys"]))
            keys.setStyleSheet(self._keys_style())
            keys.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            row_layout.addWidget(desc)
            row_layout.addStretch()
            row_layout.addWidget(keys)
            self.sheet_layout.addWidget(row)

    def reload_from_config(self):
        self.preset_combo.blockSignals(True)
        self._select_preset(self.config_manager.get("shortcut_preset", DEFAULT_SHORTCUT_PRESET))
        self.preset_combo.blockSignals(False)

    def set_advanced_visible(self, visible):
        # Shortcuts are useful to every user, so the card stays in basic mode too.
        pass

    def refresh_styles(self, *args, **kwargs):
        self.setStyleSheet(Styles.get_group_box_style())
        self.preset_label.setStyleSheet(f"font-size: 14px; {Styles.get_transparent_label_style()}")
        self.preset_combo.setStyleSheet(Styles.get_combobox_style())
        self.help_btn.setStyleSheet(Styles.get_settings_default_button_style())
        self.sheet.setStyleSheet(Styles.get_transparent_label_style())
        if self._bindings:
            self.set_bindings(self._bindings)

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

    @staticmethod
    def _desc_style() -> str:
        return f"font-size: 12px; color: {Styles.COLOR_TEXT_SECONDARY}; background: transparent;"

    @staticmethod
    def _keys_style() -> str:
        return (
            f"font-size: 12px; font-weight: 600; color: {Styles.COLOR_TEXT_PRIMARY};"
            " font-family: 'Consolas', 'Monaco', 'Courier New', monospace; background: transparent;"
        )
