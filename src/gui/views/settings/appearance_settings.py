from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QWidget,
)

from ....utils.path_utils import get_resource_path
from ...styles import Styles
from ...theme import ThemeManager
from ...theme.palette import BOARD_THEMES
from .helpers import create_icon_button


class AppearanceSettings(QGroupBox):
    theme_refreshed = pyqtSignal()
    sidebar_prefs_changed = pyqtSignal()

    def __init__(self, config_manager, parent=None):
        super().__init__("Appearance", parent)
        self.config_manager = config_manager
        self.setStyleSheet(Styles.get_group_box_style())
        self.setup_ui()

    def _combo_style(self):
        return Styles.get_combobox_style()

    def _accent_btn_style(self):
        return f"""
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
        """

    def _radio_style(self):
        return Styles.get_radio_group_style()

    def _label_style(self):
        return f"font-size: 14px; {Styles.get_transparent_label_style()}"

    def setup_ui(self):
        layout = QFormLayout(self)
        layout.setContentsMargins(20, 30, 20, 20)
        layout.setSpacing(16)
        layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        label_style = self._label_style()
        combo_style = self._combo_style()
        radio_style = self._radio_style()

        self._add_theme_mode_row(layout, label_style, radio_style)
        self._add_sidebar_row(layout, label_style, radio_style)
        self._add_board_theme_row(layout, label_style, combo_style)
        self._add_piece_style_row(layout, label_style, combo_style)
        self._add_board_display_rows(layout, label_style)
        self._add_import_row(layout, label_style)
        self._add_sound_row(layout, label_style)
        self._add_accent_row(layout, label_style, radio_style)

    def _make_radio_group(self, labels, parent, radio_style):
        container = QWidget()
        container.setStyleSheet(Styles.get_transparent_label_style())
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
        self.config_manager.set("theme_mode", mode)
        ThemeManager.set_theme_mode(mode)

    def _add_sidebar_row(self, layout, label_style, radio_style):
        self._sidebar_lbl = QLabel("Sidebar:")
        self._sidebar_lbl.setStyleSheet(label_style)
        self._sidebar_group, buttons, container = self._make_radio_group(
            ["Expanded", "Collapsed"], self, radio_style
        )
        self.sidebar_expanded_radio, self.sidebar_collapsed_radio = buttons
        self.sync_sidebar_pref()
        self._sidebar_group.buttonClicked.connect(self._on_sidebar_mode_clicked)
        layout.addRow(self._sidebar_lbl, container)

    def _on_sidebar_mode_clicked(self, btn):
        self.config_manager.set(
            "sidebar_start_collapsed", btn is self.sidebar_collapsed_radio
        )
        self.sidebar_prefs_changed.emit()

    def sync_sidebar_pref(self):
        """Reflect the persisted default in the radio buttons without emitting."""
        collapsed = bool(self.config_manager.get("sidebar_start_collapsed", False))
        radio = self.sidebar_collapsed_radio if collapsed else self.sidebar_expanded_radio
        radio.setChecked(True)

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

    def _add_board_display_rows(self, layout, label_style):
        tick_path = get_resource_path("assets/images/tick.svg").replace("\\", "/")
        checkbox_style = Styles.get_checkbox_style(tick_path)

        self._coords_lbl = QLabel("Board Details:")
        self._coords_lbl.setStyleSheet(label_style)
        self.coordinates_checkbox = QCheckBox("Show coordinates")
        self.coordinates_checkbox.setStyleSheet(checkbox_style)
        self.coordinates_checkbox.setChecked(
            self.config_manager.get("board_show_coordinates", True)
        )
        self.coordinates_checkbox.stateChanged.connect(self.change_board_coordinates)
        layout.addRow(self._coords_lbl, self.coordinates_checkbox)

        self._badges_lbl = QLabel("Move Labels:")
        self._badges_lbl.setStyleSheet(label_style)
        self.classification_checkbox = QCheckBox("Show move quality badges")
        self.classification_checkbox.setStyleSheet(checkbox_style)
        self.classification_checkbox.setChecked(
            self.config_manager.get("board_show_classification", True)
        )
        self.classification_checkbox.stateChanged.connect(self.change_board_classification)
        layout.addRow(self._badges_lbl, self.classification_checkbox)

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
        self.sound_checkbox.setStyleSheet(Styles.get_checkbox_style(tick_path))
        self.sound_checkbox.setChecked(self.config_manager.get("sound_enabled", True))
        self.sound_checkbox.stateChanged.connect(self.change_sound_setting)
        layout.addRow(self._sound_lbl, self.sound_checkbox)

    def _add_accent_row(self, layout, label_style, radio_style):
        accent_lbl = QLabel("Accent Color:")
        accent_lbl.setStyleSheet(label_style)
        container = QWidget()
        container.setStyleSheet(Styles.get_transparent_label_style())
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
        self.color_btn.setStyleSheet(self._accent_btn_style())
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
        self.config_manager.set("accent_mode", mode)
        self._update_accent_btn_visibility()
        ThemeManager.set_accent_mode(mode)
        self.theme_refreshed.emit()

    def _update_accent_btn_visibility(self):
        self.color_btn.setVisible(self.accent_mode_custom.isChecked())

    def change_accent_color(self):
        color = QColorDialog.getColor(initial=QColor(ThemeManager.accent()), parent=self, title="Select Accent Color")
        if color.isValid():
            self.config_manager.set("accent_color", color.name())
            self.config_manager.set("accent_mode", "custom")
            self.accent_mode_custom.setChecked(True)
            self._update_accent_btn_visibility()
            ThemeManager.set_accent(color.name())
            self.theme_refreshed.emit()

    def change_board_theme(self, theme_name):
        self.config_manager.config["board_theme"] = theme_name
        self.theme_refreshed.emit()

    def change_piece_theme(self, theme_name):
        self.config_manager.config["piece_theme"] = theme_name
        self.theme_refreshed.emit()

    def change_board_coordinates(self, state):
        self.config_manager.config["board_show_coordinates"] = (
            self.coordinates_checkbox.isChecked()
        )
        self.theme_refreshed.emit()

    def change_board_classification(self, state):
        self.config_manager.config["board_show_classification"] = (
            self.classification_checkbox.isChecked()
        )
        self.theme_refreshed.emit()

    def change_sound_setting(self, state):
        self.config_manager.config["sound_enabled"] = self.sound_checkbox.isChecked()

    def import_theme(self):
        from PyQt6.QtWidgets import QFileDialog

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
            MainWindow.toast_from_widget(self,
                "Invalid theme: " + "; ".join(errors),
                "error")
            return
        theme_name = import_theme_from_folder(folder)
        if theme_name is None:
            MainWindow.toast_from_widget(self, "Theme import failed. Check the logs.", "error")
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

    def refresh_styles(self, *args, **kwargs):
        self.setStyleSheet(Styles.get_group_box_style())
        combo_style = self._combo_style()
        radio_style = self._radio_style()

        if hasattr(self, 'theme_combo'):
            self.theme_combo.setStyleSheet(combo_style)
        if hasattr(self, 'piece_combo'):
            self.piece_combo.setStyleSheet(combo_style)
        if hasattr(self, 'color_btn'):
            self.color_btn.setStyleSheet(self._accent_btn_style())
        tick_path = get_resource_path("assets/images/tick.svg").replace("\\", "/")
        for checkbox in (
            getattr(self, "sound_checkbox", None),
            getattr(self, "coordinates_checkbox", None),
            getattr(self, "classification_checkbox", None),
        ):
            if checkbox:
                checkbox.setStyleSheet(Styles.get_checkbox_style(tick_path))
        for lbl in (
            getattr(self, "_sound_lbl", None),
            getattr(self, "_coords_lbl", None),
            getattr(self, "_badges_lbl", None),
            getattr(self, "_sidebar_lbl", None),
        ):
            if lbl:
                lbl.setStyleSheet(self._label_style())
        if hasattr(self, 'import_theme_btn'):
            self.import_theme_btn.setStyleSheet(Styles.get_settings_default_button_style())
        for rb in (
            getattr(self, '_theme_mode_system', None),
            getattr(self, '_theme_mode_light', None),
            getattr(self, '_theme_mode_dark', None),
            getattr(self, 'sidebar_expanded_radio', None),
            getattr(self, 'sidebar_collapsed_radio', None),
            getattr(self, 'accent_mode_system', None),
            getattr(self, 'accent_mode_custom', None),
        ):
            if rb:
                rb.setStyleSheet(radio_style)
