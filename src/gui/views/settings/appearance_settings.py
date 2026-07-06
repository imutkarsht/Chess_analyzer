"""
Appearance Settings group component.
"""
from PyQt6.QtWidgets import QGroupBox, QFormLayout, QLabel, QComboBox, QCheckBox, QColorDialog
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from ...styles import Styles
from ....utils.path_utils import get_resource_path
from .helpers import create_icon_button

class AppearanceSettings(QGroupBox):
    theme_refreshed = pyqtSignal()

    def __init__(self, config_manager, parent=None):
        super().__init__("Appearance", parent)
        self.config_manager = config_manager
        self.setStyleSheet(Styles.get_group_box_style())
        
        self.setup_ui()

    def setup_ui(self):
        appearance_layout = QFormLayout(self)
        appearance_layout.setContentsMargins(20, 30, 20, 20)
        appearance_layout.setSpacing(16)
        appearance_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        appearance_layout.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        appearance_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        
        label_style = f"color: {Styles.COLOR_TEXT_PRIMARY}; font-size: 14px; background: transparent;"
        combo_style = f"""
            QComboBox {{
                padding: 8px 12px;
                min-width: 120px;
                background-color: {Styles.COLOR_SURFACE_LIGHT};
                color: {Styles.COLOR_TEXT_PRIMARY};
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 6px;
                font-size: 14px;
            }}
            QComboBox:hover {{
                border: 1px solid {Styles.COLOR_ACCENT};
            }}
            QComboBox::drop-down {{
                border: none;
                padding-right: 8px;
            }}
        """
        
        # Board Theme Selector
        theme_lbl = QLabel("Board Theme:")
        theme_lbl.setStyleSheet(label_style)
        
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(list(Styles.BOARD_THEMES.keys()))
        current_theme = self.config_manager.get("board_theme", "Green")
        self.theme_combo.setCurrentText(current_theme)
        self.theme_combo.setStyleSheet(combo_style)
        self.theme_combo.currentTextChanged.connect(self.change_board_theme)
        
        appearance_layout.addRow(theme_lbl, self.theme_combo)

        # Piece Style Selector
        from ...board.piece_themes import get_piece_theme_names
        piece_lbl = QLabel("Piece Style:")
        piece_lbl.setStyleSheet(label_style)
        
        self.piece_combo = QComboBox()
        self.piece_combo.addItems(get_piece_theme_names())
        current_piece_theme = self.config_manager.get("piece_theme", "Standard")
        self.piece_combo.setCurrentText(current_piece_theme)
        self.piece_combo.setStyleSheet(combo_style)
        self.piece_combo.currentTextChanged.connect(self.change_piece_theme)
        
        appearance_layout.addRow(piece_lbl, self.piece_combo)

        # Import Theme button (spacer label keeps form alignment)
        import_lbl = QLabel("")
        import_lbl.setStyleSheet(label_style)
        self.import_theme_btn = create_icon_button(
            "Import Theme...", "fa5s.folder-open", self.import_theme, self
        )
        appearance_layout.addRow(import_lbl, self.import_theme_btn)

        # Sound Effects Selector
        self._sound_lbl = QLabel("Sound Effects:")
        self._sound_lbl.setStyleSheet(label_style)
        
        tick_path = get_resource_path("assets/images/tick.svg").replace("\\", "/")
        self.sound_checkbox = QCheckBox("Enable Sound Effects")
        self.sound_checkbox.setStyleSheet(f"""
            QCheckBox {{
                color: {Styles.COLOR_TEXT_PRIMARY};
                font-size: 13px;
                background: transparent;
            }}
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 4px;
                background-color: {Styles.COLOR_SURFACE_LIGHT};
            }}
            QCheckBox::indicator:checked {{
                background-color: {Styles.COLOR_ACCENT};
                border-color: {Styles.COLOR_ACCENT};
                image: url('{tick_path}');
            }}
        """)
        self.sound_checkbox.setChecked(self.config_manager.get("sound_enabled", True))
        self.sound_checkbox.stateChanged.connect(self.change_sound_setting)
        
        appearance_layout.addRow(self._sound_lbl, self.sound_checkbox)

        # Accent Color
        color_lbl = QLabel("Accent Color:")
        color_lbl.setStyleSheet(label_style)
        
        self.color_btn = create_icon_button("Change Color", "fa5s.palette", self.change_accent_color, self)
        appearance_layout.addRow(color_lbl, self.color_btn)

    def change_accent_color(self):
        color = QColorDialog.getColor(initial=QColor(Styles.COLOR_ACCENT), parent=self, title="Select Accent Color")
        if color.isValid():
            Styles.set_accent_color(color.name())
            self.config_manager.config["accent_color"] = color.name()
            self.theme_refreshed.emit()

    def _update_config_and_refresh(self, key, value):
        self.config_manager.config[key] = value
        self.theme_refreshed.emit()

    def change_board_theme(self, theme_name):
        self._update_config_and_refresh("board_theme", theme_name)

    def change_piece_theme(self, theme_name):
        self._update_config_and_refresh("piece_theme", theme_name)

    def change_sound_setting(self, state):
        self.config_manager.config["sound_enabled"] = self.sound_checkbox.isChecked()

    def import_theme(self):
        from PyQt6.QtWidgets import QFileDialog, QMessageBox
        from ...board.piece_themes import (
            get_piece_theme_names,
            import_theme_from_folder,
            validate_theme_folder,
        )

        folder = QFileDialog.getExistingDirectory(
            self, "Select Piece Theme Folder", "",
            QFileDialog.Option.ShowDirsOnly,
        )
        if not folder:
            return

        is_valid, errors = validate_theme_folder(folder)
        if not is_valid:
            QMessageBox.warning(
                self, "Invalid Theme",
                "The selected folder is not a valid piece theme:\n\n"
                + "\n".join(errors),
            )
            return

        theme_name = import_theme_from_folder(folder)
        if theme_name is None:
            QMessageBox.critical(
                self, "Import Failed",
                "Failed to import the theme. Check the logs for details.",
            )
            return

        self.piece_combo.blockSignals(True)
        self.piece_combo.clear()
        self.piece_combo.addItems(get_piece_theme_names())
        self.piece_combo.setCurrentText(theme_name)
        self.piece_combo.blockSignals(False)

        self.change_piece_theme(theme_name)

        QMessageBox.information(
            self, "Theme Imported",
            f"Piece theme '{theme_name}' has been imported and is now active.",
        )

    def set_advanced_visible(self, visible):
        pass

    def refresh_styles(self, combo_style, default_style, sound_cb_style):
        self.setStyleSheet(Styles.get_group_box_style())
        self.theme_combo.setStyleSheet(combo_style)
        self.piece_combo.setStyleSheet(combo_style)
        self.sound_checkbox.setStyleSheet(sound_cb_style)
        self.color_btn.setStyleSheet(default_style)
        self.import_theme_btn.setStyleSheet(default_style)
