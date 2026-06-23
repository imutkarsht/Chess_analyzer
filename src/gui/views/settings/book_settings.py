"""
Opening Book Settings group component.
"""
import os
from PyQt6.QtWidgets import QGroupBox, QVBoxLayout, QHBoxLayout, QLineEdit, QLabel, QFileDialog
from ...styles import Styles
from .helpers import create_icon_button

class BookSettings(QGroupBox):
    def __init__(self, config_manager, parent=None):
        super().__init__("Opening Book", parent)
        self.config_manager = config_manager
        self.setStyleSheet(Styles.get_group_box_style())
        
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 25, 20, 20)
        
        path_layout = QHBoxLayout()
        self.polyglot_path_input = QLineEdit()
        self.polyglot_path_input.setText(self.config_manager.get("polyglot_book_path", ""))
        self.polyglot_path_input.setPlaceholderText("Path to Polyglot book (.bin)... (Optional)")
        self.polyglot_path_input.setStyleSheet(Styles.get_input_style())
        path_layout.addWidget(self.polyglot_path_input)
        
        self.polyglot_browse_btn = create_icon_button("Browse", "fa5s.folder-open", self.browse_polyglot_book, self)
        path_layout.addWidget(self.polyglot_browse_btn)
        
        self.polyglot_clear_btn = create_icon_button("Clear", "fa5s.times", self.clear_polyglot_book, self)
        path_layout.addWidget(self.polyglot_clear_btn)
        
        layout.addLayout(path_layout)

        # Polyglot Validation status label
        self.polyglot_validation_label = QLabel()
        self.polyglot_validation_label.setStyleSheet("font-size: 12px; font-weight: bold; background: transparent; margin-top: 2px;")
        self.polyglot_validation_label.setWordWrap(True)
        self.polyglot_validation_label.setVisible(False)
        layout.addWidget(self.polyglot_validation_label)

        self.polyglot_path_input.editingFinished.connect(self.validate_polyglot_path)
        self.validate_polyglot_path()

    def browse_polyglot_book(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Polyglot Opening Book", "", "Polyglot Books (*.bin);;All Files (*)")
        if path:
            self.polyglot_path_input.setText(path)
            self.validate_polyglot_path()

    def clear_polyglot_book(self):
        self.polyglot_path_input.clear()
        self.validate_polyglot_path()

    def validate_polyglot_path(self):
        path = self.polyglot_path_input.text().strip()
        if not path:
            self.polyglot_validation_label.setText("⚠️ No polyglot book specified (SQLite book will be used)")
            self.polyglot_validation_label.setStyleSheet(f"color: {Styles.COLOR_MISTAKE}; font-size: 12px; font-weight: bold; background: transparent;")
            self.polyglot_validation_label.setVisible(True)
            return

        is_file = os.path.exists(path) and os.path.isfile(path)
        if not is_file:
            self.polyglot_validation_label.setText("❌ File does not exist")
            self.polyglot_validation_label.setStyleSheet(f"color: {Styles.COLOR_BLUNDER}; font-size: 12px; font-weight: bold; background: transparent;")
            self.polyglot_validation_label.setVisible(True)
            return

        if not path.endswith('.bin'):
            self.polyglot_validation_label.setText("❌ Invalid file format (must be a .bin Polyglot book)")
            self.polyglot_validation_label.setStyleSheet(f"color: {Styles.COLOR_BLUNDER}; font-size: 12px; font-weight: bold; background: transparent;")
            self.polyglot_validation_label.setVisible(True)
            return

        try:
            import chess.polyglot
            with chess.polyglot.open_reader(path) as reader:
                pass
            self.polyglot_validation_label.setText("✓ Valid Polyglot Opening Book")
            self.polyglot_validation_label.setStyleSheet(f"color: {Styles.COLOR_BEST}; font-size: 12px; font-weight: bold; background: transparent;")
        except Exception as e:
            self.polyglot_validation_label.setText(f"❌ Failed to parse Polyglot book: {str(e)}")
            self.polyglot_validation_label.setStyleSheet(f"color: {Styles.COLOR_BLUNDER}; font-size: 12px; font-weight: bold; background: transparent;")
            
        self.polyglot_validation_label.setVisible(True)

    def refresh_styles(self, combo_style, input_style, default_style):
        self.setStyleSheet(Styles.get_group_box_style())
        self.polyglot_browse_btn.setStyleSheet(default_style)
        self.polyglot_clear_btn.setStyleSheet(default_style)
        self.polyglot_path_input.setStyleSheet(input_style.replace("max-width: 140px;", ""))
