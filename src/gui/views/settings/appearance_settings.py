from PyQt6.QtWidgets import QGroupBox, QFormLayout, QLabel, QComboBox, QCheckBox, QColorDialog, QRadioButton, QHBoxLayout, QWidget, QPushButton, QButtonGroup, QFrame
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from ...styles import Styles
from ...theme import ThemeManager
from ...theme.palette import BOARD_THEMES
from ....utils.path_utils import get_resource_path
from .helpers import create_icon_button

RADIO_GROUP_TPL = """
    QRadioButton {{
        color: {text};
        font-size: 13px;
        spacing: 8px;
        padding: 4px 0;
    }}
    QRadioButton::indicator {{
        width: 18px;
        height: 18px;
        border: 1px solid {border};
        border-radius: 10px;
        background: {bg};
    }}
    QRadioButton::indicator:checked {{
        background: {accent};
        border-color: {accent};
    }}
    QRadioButton::indicator:hover {{
        border-color: {accent};
    }}
"""


class AppearanceSettings(QGroupBox):
    theme_refreshed = pyqtSignal()

    def __init__(self, config_manager, parent=None):
        super().__init__("Appearance", parent)
        self.config_manager = config_manager
        self.setStyleSheet(Styles.get_group_box_style())
        self.setup_ui()

    def _radio_style(self):
        p = ThemeManager.palette()
        return RADIO_GROUP_TPL.format(
            text=p.text_primary,
            border=p.border,
            bg=p.surface_light,
            accent=p.accent,
        )

    def _label_style(self):
        return f"color: {Styles.COLOR_TEXT_PRIMARY}; font-size: 14px; background: transparent;"

    def _combo_style(self):
        return f"""
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

    def setup_ui(self):
        layout = QFormLayout(self)
        layout.setContentsMargins(20, 30, 20, 20)
        layout.setSpacing(16)
        layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        label_style = self._label_style()
        combo_style = self._combo_style()
        radio_style = self._radio_style()

        self._add_theme_mode_row(layout, label_style, radio_style)
        self._add_board_theme_row(layout, label_style, combo_style)
        self._add_piece_style_row(layout, label_style, combo_style)
        self._add_import_row(layout, label_style)
        self._add_sound_row(layout, label_style)
        self._add_accent_row(layout, label_style, radio_style)

    def _make_radio_group(self, labels, parent, radio_style):
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        hbox = QHBoxLayout(container)
        hbox.setContentsMargins(0, 0, 0, 0)
        hbox.setSpacing(4)
        group = QButtonGroup(container)
        buttons = []
        for label in labels:
            rb = QRadioButton(label)
            rb.setStyleSheet(radio_style)
            group.addButton(rb)
            hbox.addWidget(rb)
            buttons.append(rb)
        hbox.addStretch()
        return group, buttons, container

    def _add_theme_mode_row(self, layout, label_style, radio_style):
        lbl = QLabel("Theme Mode:")
        lbl.setStyleSheet(label_style)
        group, buttons, container = self._make_radio_group(
            ["System", "Light", "Dark"], self, radio_style
        )
        self._theme_mode_group = group
        self._theme_mode_system, self._theme_mode_light, self._theme_mode_dark = buttons

        saved = self.config_manager.get("theme_mode", "system")
        idx = {"system": 0, "light": 1, "dark": 2}.get(saved, 0)
        buttons[idx].setChecked(True)

        group.buttonClicked.connect(self._on_theme_mode_clicked)
        layout.addRow(lbl, container)

    def _on_theme_mode_clicked(self, btn):
        mapping = {self._theme_mode_system: "system", self._theme_mode_light: "light", self._theme_mode_dark: "dark"}
        mode = mapping.get(btn, "system")
        self.config_manager.config["theme_mode"] = mode
        ThemeManager.set_theme_mode(mode)
        self.theme_refreshed.emit()

    def _add_board_theme_row(self, layout, label_style, combo_style):
        lbl = QLabel("Board Theme:")
        lbl.setStyleSheet(label_style)
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(list(BOARD_THEMES.keys()))
        self.theme_combo.setCurrentText(self.config_manager.get("board_theme", "Green"))
        self.theme_combo.setStyleSheet(combo_style)
        self.theme_combo.currentTextChanged.connect(self.change_board_theme)
        layout.addRow(lbl, self.theme_combo)

    def _add_piece_style_row(self, layout, label_style, combo_style):
        from ...board.piece_themes import get_piece_theme_names
        lbl = QLabel("Piece Style:")
        lbl.setStyleSheet(label_style)
        self.piece_combo = QComboBox()
        self.piece_combo.addItems(get_piece_theme_names())
        self.piece_combo.setCurrentText(self.config_manager.get("piece_theme", "Standard"))
        self.piece_combo.setStyleSheet(combo_style)
        self.piece_combo.currentTextChanged.connect(self.change_piece_theme)
        layout.addRow(lbl, self.piece_combo)

    def _add_import_row(self, layout, label_style):
        import_lbl = QLabel("")
        import_lbl.setStyleSheet(label_style)
        self.import_theme_btn = create_icon_button(
            "Import Theme...", "fa5s.folder-open", self.import_theme, self
        )
        layout.addRow(import_lbl, self.import_theme_btn)

    def _add_sound_row(self, layout, label_style):
        self._sound_lbl = QLabel("Sound Effects:")
        self._sound_lbl.setStyleSheet(label_style)
        tick_path = get_resource_path("assets/images/tick.svg").replace("\\", "/")
        self.sound_checkbox = QCheckBox("Enable Sound Effects")
        self.sound_checkbox.setStyleSheet(f"""
            QCheckBox {{
                color: {Styles.COLOR_TEXT_PRIMARY};
                font-size: 13px;
                background: transparent;
                spacing: 8px;
            }}
            QCheckBox::indicator {{
                width: 20px;
                height: 20px;
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
        layout.addRow(self._sound_lbl, self.sound_checkbox)

    def _add_accent_row(self, layout, label_style, radio_style):
        accent_lbl = QLabel("Accent Color:")
        accent_lbl.setStyleSheet(label_style)
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        hbox = QHBoxLayout(container)
        hbox.setContentsMargins(0, 0, 0, 0)
        hbox.setSpacing(4)
        self._accent_group = QButtonGroup(container)
        self.accent_mode_system = QRadioButton("System")
        self.accent_mode_custom = QRadioButton("Custom")
        for rb in (self.accent_mode_system, self.accent_mode_custom):
            rb.setStyleSheet(radio_style)
            self._accent_group.addButton(rb)
            hbox.addWidget(rb)
        self.color_btn = QPushButton("Choose Color")
        self.color_btn.setStyleSheet(f"""
            QPushButton {{
                padding: 6px 14px;
                background-color: {Styles.COLOR_SURFACE_LIGHT};
                color: {Styles.COLOR_TEXT_PRIMARY};
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 6px;
                font-size: 13px;
            }}
            QPushButton:hover {{
                border-color: {Styles.COLOR_ACCENT};
            }}
        """)
        self.color_btn.clicked.connect(self.change_accent_color)
        hbox.addWidget(self.color_btn)
        hbox.addStretch()
        saved = self.config_manager.get("accent_mode", "system")
        if saved == "custom":
            self.accent_mode_custom.setChecked(True)
        else:
            self.accent_mode_system.setChecked(True)
        self._update_accent_btn_visibility()
        self._accent_group.buttonClicked.connect(self._on_accent_mode_clicked)
        layout.addRow(accent_lbl, container)

    def _on_accent_mode_clicked(self, btn):
        mode = "custom" if btn == self.accent_mode_custom else "system"
        self.config_manager.config["accent_mode"] = mode
        ThemeManager.set_accent_mode(mode)
        self._update_accent_btn_visibility()
        self.theme_refreshed.emit()

    def _update_accent_btn_visibility(self):
        self.color_btn.setVisible(self.accent_mode_custom.isChecked())

    def change_accent_color(self):
        color = QColorDialog.getColor(initial=QColor(ThemeManager.accent()), parent=self, title="Select Accent Color")
        if color.isValid():
            ThemeManager.set_accent(color.name())
            self.config_manager.config["accent_color"] = color.name()
            self.config_manager.config["accent_mode"] = "custom"
            self.accent_mode_custom.setChecked(True)
            self._update_accent_btn_visibility()
            self.theme_refreshed.emit()

    def change_board_theme(self, theme_name):
        self.config_manager.config["board_theme"] = theme_name
        self.theme_refreshed.emit()

    def change_piece_theme(self, theme_name):
        self.config_manager.config["piece_theme"] = theme_name
        self.theme_refreshed.emit()

    def change_sound_setting(self, state):
        self.config_manager.config["sound_enabled"] = self.sound_checkbox.isChecked()

    def import_theme(self):
        from PyQt6.QtWidgets import QFileDialog, QMessageBox
        from src.gui.main_window import MainWindow
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
            QMessageBox.warning(self, "Invalid Theme", "The selected folder is not a valid piece theme:\n\n" + "\n".join(errors))
            return
        theme_name = import_theme_from_folder(folder)
        if theme_name is None:
            QMessageBox.critical(self, "Import Failed", "Failed to import the theme. Check the logs for details.")
            return
        self.piece_combo.blockSignals(True)
        self.piece_combo.clear()
        self.piece_combo.addItems(get_piece_theme_names())
        self.piece_combo.setCurrentText(theme_name)
        self.piece_combo.blockSignals(False)
        self.change_piece_theme(theme_name)
        MainWindow.toast_from_widget(self, f"Piece theme '{theme_name}' imported and active.", "success")

    def set_advanced_visible(self, visible):
        pass

    def refresh_styles(self, combo_style, default_style, sound_cb_style):
        self.setStyleSheet(Styles.get_group_box_style())
        self.theme_combo.setStyleSheet(combo_style)
        self.piece_combo.setStyleSheet(combo_style)
        self.sound_checkbox.setStyleSheet(sound_cb_style)
        self.color_btn.setStyleSheet(default_style)
        self.import_theme_btn.setStyleSheet(default_style)
        rs = self._radio_style()
        for btn in (self._theme_mode_system, self._theme_mode_light, self._theme_mode_dark,
                    self.accent_mode_system, self.accent_mode_custom):
            if btn:
                btn.setStyleSheet(rs)
