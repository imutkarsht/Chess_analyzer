"""Opening book settings."""

import os

from PyQt6.QtWidgets import QFileDialog, QGroupBox, QLabel, QVBoxLayout

from ...styles import Styles
from .components import PathField, SettingsBinder, SettingsForm


class BookSettings(QGroupBox):
    def __init__(self, config_manager, parent=None):
        super().__init__("Opening Book", parent)
        self.config_manager = config_manager
        self.setStyleSheet(Styles.get_group_box_style())
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 0)

        self.form = SettingsForm(self)
        self.binder = SettingsBinder(self.config_manager, self.form, self)

        self.path_field = PathField(
            "Path to Polyglot book (.bin)... (Optional)",
            browse_callback=self.browse_polyglot_book,
            clear_callback=self.clear_polyglot_book,
            parent=self,
        )
        self.polyglot_path_input = self.path_field.line_edit
        self.polyglot_browse_btn = self.path_field.browse_btn
        self.polyglot_clear_btn = self.path_field.clear_btn
        self.polyglot_path_input.editingFinished.connect(self.validate_polyglot_path)
        self.binder.add(
            "polyglot_book_path",
            self.path_field,
            hint="Optional .bin book. The built-in SQLite opening database is used when empty.",
            width=None,
        )
        layout.addWidget(self.form)

        self.polyglot_validation_label = QLabel()
        self.polyglot_validation_label.setStyleSheet(Styles.get_validation_label_style())
        self.polyglot_validation_label.setWordWrap(True)
        self.polyglot_validation_label.setVisible(False)
        layout.addWidget(self.polyglot_validation_label)
        self.validate_polyglot_path()

    def browse_polyglot_book(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Polyglot Opening Book", "", "Polyglot Books (*.bin);;All Files (*)"
        )
        if path:
            self.polyglot_path_input.setText(path)
            self.polyglot_path_input.editingFinished.emit()
            self.validate_polyglot_path()

    def clear_polyglot_book(self):
        self.polyglot_path_input.clear()
        self.polyglot_path_input.editingFinished.emit()
        self.validate_polyglot_path()

    def validate_polyglot_path(self):
        path = self.polyglot_path_input.text().strip()
        if not path:
            self.polyglot_validation_label.setText(
                "⚠️ No polyglot book specified (SQLite book will be used)"
            )
            self.polyglot_validation_label.setStyleSheet(
                f"color: {Styles.COLOR_MISTAKE}; font-size: 12px; font-weight: bold; background: transparent;"
            )
            self.polyglot_validation_label.setVisible(True)
            return

        is_file = os.path.exists(path) and os.path.isfile(path)
        if not is_file:
            self.polyglot_validation_label.setText("❌ File does not exist")
            self.polyglot_validation_label.setStyleSheet(
                f"color: {Styles.COLOR_BLUNDER}; font-size: 12px; font-weight: bold; background: transparent;"
            )
            self.polyglot_validation_label.setVisible(True)
            return

        if not path.endswith(".bin"):
            self.polyglot_validation_label.setText(
                "❌ Invalid file format (must be a .bin Polyglot book)"
            )
            self.polyglot_validation_label.setStyleSheet(
                f"color: {Styles.COLOR_BLUNDER}; font-size: 12px; font-weight: bold; background: transparent;"
            )
            self.polyglot_validation_label.setVisible(True)
            return

        try:
            import chess.polyglot

            with chess.polyglot.open_reader(path):
                pass
            self.polyglot_validation_label.setText("✓ Valid Polyglot Opening Book")
            self.polyglot_validation_label.setStyleSheet(
                f"color: {Styles.COLOR_BEST}; font-size: 12px; font-weight: bold; background: transparent;"
            )
        except Exception as e:
            self.polyglot_validation_label.setText(
                f"❌ Failed to parse Polyglot book: {e}"
            )
            self.polyglot_validation_label.setStyleSheet(
                f"color: {Styles.COLOR_BLUNDER}; font-size: 12px; font-weight: bold; background: transparent;"
            )

        self.polyglot_validation_label.setVisible(True)

    def reload_from_config(self):
        self.binder.load()
        self.validate_polyglot_path()

    def set_advanced_visible(self, visible):
        self.setVisible(visible)

    def refresh_styles(self, *args, **kwargs):
        self.setStyleSheet(Styles.get_group_box_style())
        self.form.refresh_styles()
        if hasattr(self, "polyglot_path_input"):
            self.polyglot_path_input.setStyleSheet(Styles.get_input_style())
        if hasattr(self, "polyglot_browse_btn"):
            self.polyglot_browse_btn.setStyleSheet(
                Styles.get_settings_default_button_style()
            )
        if hasattr(self, "polyglot_clear_btn"):
            self.polyglot_clear_btn.setStyleSheet(
                Styles.get_settings_default_button_style()
            )
        if hasattr(self, "polyglot_validation_label"):
            self.validate_polyglot_path()
