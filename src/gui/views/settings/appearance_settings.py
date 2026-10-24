from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QButtonGroup,
    QColorDialog,
    QGroupBox,
    QHBoxLayout,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from ....utils.path_utils import get_resource_path
from ...styles import Styles
from ...theme import ThemeManager
from ...theme.palette import BOARD_THEMES
from .components import (
    CONTROL_DEFAULT,
    SettingsForm,
    make_checkbox,
    make_combo,
)
from .helpers import create_icon_button


class AppearanceSettings(QGroupBox):
    theme_refreshed = pyqtSignal()
    sidebar_prefs_changed = pyqtSignal()

    def __init__(self, config_manager, parent=None):
        super().__init__("Appearance", parent)
        self.config_manager = config_manager
        self.setStyleSheet(Styles.get_group_box_style())
        self.setup_ui()

    def _radio_style(self):
        return Styles.get_radio_group_style()

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

    def setup_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 8, 0, 0)

        self.form = SettingsForm(self)
        outer.addWidget(self.form)

        self._add_theme_mode_row()
        self._add_sidebar_row()
        self._add_board_theme_row()
        self._add_piece_style_row()
        self._add_board_display_rows()
        self._add_sound_row()
        self._add_accent_row()

    def _make_radio_group(self, labels):
        container = QWidget()
        container.setStyleSheet(Styles.get_transparent_label_style())
        hbox = QHBoxLayout(container)
        hbox.setContentsMargins(0, 0, 0, 0)
        hbox.setSpacing(12)
        group = QButtonGroup(container)
        buttons = []
        for label in labels:
            radio = QRadioButton(label)
            radio.setStyleSheet(self._radio_style())
            group.addButton(radio)
            hbox.addWidget(radio)
            buttons.append(radio)
        hbox.addStretch()
        return group, buttons, container

    def _add_theme_mode_row(self):
        group, buttons, container = self._make_radio_group(["System", "Light", "Dark"])
        self._theme_mode_group = group
        self._theme_mode_system, self._theme_mode_light, self._theme_mode_dark = buttons

        saved = self.config_manager.get("theme_mode", "system")
        index = {"system": 0, "light": 1, "dark": 2}.get(saved, 0)
        buttons[index].setChecked(True)
        group.buttonClicked.connect(self._on_theme_mode_clicked)
        self.form.add_row("Theme Mode", container, width=None)

    def _on_theme_mode_clicked(self, button):
        mapping = {
            self._theme_mode_system: "system",
            self._theme_mode_light: "light",
            self._theme_mode_dark: "dark",
        }
        mode = mapping.get(button, "system")
        self.config_manager.set("theme_mode", mode)
        ThemeManager.set_theme_mode(mode)

    def _add_sidebar_row(self):
        group, buttons, container = self._make_radio_group(["Expanded", "Collapsed"])
        self._sidebar_group = group
        self.sidebar_expanded_radio, self.sidebar_collapsed_radio = buttons
        self.sync_sidebar_pref()
        group.buttonClicked.connect(self._on_sidebar_mode_clicked)
        self.form.add_row("Sidebar", container, width=None)

    def _on_sidebar_mode_clicked(self, button):
        self.config_manager.set(
            "sidebar_start_collapsed", button is self.sidebar_collapsed_radio
        )
        self.sidebar_prefs_changed.emit()

    def sync_sidebar_pref(self):
        collapsed = bool(self.config_manager.get("sidebar_start_collapsed", False))
        radio = self.sidebar_collapsed_radio if collapsed else self.sidebar_expanded_radio
        radio.setChecked(True)

    def _add_board_theme_row(self):
        self.theme_combo = make_combo(CONTROL_DEFAULT)
        self.theme_combo.addItems(list(BOARD_THEMES.keys()))
        self.theme_combo.setCurrentText(self.config_manager.get("board_theme", "Green"))
        self.theme_combo.currentTextChanged.connect(self.change_board_theme)
        self.form.add_row("Board Theme", self.theme_combo)

    def _add_piece_style_row(self):
        from ...board.piece_themes import get_piece_theme_names

        self.piece_combo = make_combo(CONTROL_DEFAULT)
        self.piece_combo.addItems(get_piece_theme_names())
        self.piece_combo.setCurrentText(self.config_manager.get("piece_theme", "Standard"))
        self.piece_combo.currentTextChanged.connect(self.change_piece_theme)

        self.import_theme_btn = create_icon_button(
            "Import Theme...", "fa5s.folder-open", self.import_theme, self
        )
        self.import_theme_btn.setMaximumWidth(170)

        row = QWidget()
        row.setStyleSheet(Styles.get_transparent_label_style())
        hbox = QHBoxLayout(row)
        hbox.setContentsMargins(0, 0, 0, 0)
        hbox.setSpacing(8)
        hbox.addWidget(self.piece_combo)
        hbox.addWidget(self.import_theme_btn)
        hbox.addStretch(1)
        self.form.add_row("Piece Style", row, width=None)

    def _add_board_display_rows(self):
        self.coordinates_checkbox = make_checkbox("Show coordinates")
        self.coordinates_checkbox.setChecked(
            self.config_manager.get("board_show_coordinates", True)
        )
        self.coordinates_checkbox.stateChanged.connect(self.change_board_coordinates)
        self.form.add_row("Board Details", self.coordinates_checkbox, width=None)

        self.classification_checkbox = make_checkbox("Show move quality badges")
        self.classification_checkbox.setChecked(
            self.config_manager.get("board_show_classification", True)
        )
        self.classification_checkbox.stateChanged.connect(self.change_board_classification)
        self.form.add_row("Move Labels", self.classification_checkbox, width=None)

    def _add_sound_row(self):
        self.sound_checkbox = make_checkbox("Enable Sound Effects")
        self.sound_checkbox.setChecked(self.config_manager.get("sound_enabled", True))
        self.sound_checkbox.stateChanged.connect(self.change_sound_setting)
        self.form.add_row("Sound Effects", self.sound_checkbox, width=None)

    def _add_accent_row(self):
        container = QWidget()
        container.setStyleSheet(Styles.get_transparent_label_style())
        hbox = QHBoxLayout(container)
        hbox.setContentsMargins(0, 0, 0, 0)
        hbox.setSpacing(12)

        self._accent_group = QButtonGroup(container)
        self.accent_mode_system = QRadioButton("System")
        self.accent_mode_custom = QRadioButton("Custom")
        for radio in (self.accent_mode_system, self.accent_mode_custom):
            radio.setStyleSheet(self._radio_style())
            self._accent_group.addButton(radio)
            hbox.addWidget(radio)

        self.color_btn = QPushButton("Choose Color")
        self.color_btn.setStyleSheet(self._accent_btn_style())
        self.color_btn.setMaximumWidth(150)
        self.color_btn.clicked.connect(self.change_accent_color)
        hbox.addWidget(self.color_btn)
        hbox.addStretch(1)

        saved = self.config_manager.get("accent_mode", "system")
        if saved == "custom":
            self.accent_mode_custom.setChecked(True)
        else:
            self.accent_mode_system.setChecked(True)
        self._update_accent_btn_visibility()
        self._accent_group.buttonClicked.connect(self._on_accent_mode_clicked)
        self.form.add_row("Accent Color", container, width=None)

    def _on_accent_mode_clicked(self, button):
        mode = "custom" if button == self.accent_mode_custom else "system"
        self.config_manager.set("accent_mode", mode)
        self._update_accent_btn_visibility()
        ThemeManager.set_accent_mode(mode)
        self.theme_refreshed.emit()

    def _update_accent_btn_visibility(self):
        self.color_btn.setVisible(self.accent_mode_custom.isChecked())

    def change_accent_color(self):
        color = QColorDialog.getColor(
            initial=QColor(ThemeManager.accent()),
            parent=self,
            title="Select Accent Color",
        )
        if color.isValid():
            self.config_manager.set("accent_color", color.name())
            self.config_manager.set("accent_mode", "custom")
            self.accent_mode_custom.setChecked(True)
            self._update_accent_btn_visibility()
            ThemeManager.set_accent(color.name())
            self.theme_refreshed.emit()

    def change_board_theme(self, theme_name):
        self.config_manager.set("board_theme", theme_name)
        self.theme_refreshed.emit()

    def change_piece_theme(self, theme_name):
        self.config_manager.set("piece_theme", theme_name)
        self.theme_refreshed.emit()

    def change_board_coordinates(self, state):
        self.config_manager.set("board_show_coordinates", self.coordinates_checkbox.isChecked())
        self.theme_refreshed.emit()

    def change_board_classification(self, state):
        self.config_manager.set(
            "board_show_classification", self.classification_checkbox.isChecked()
        )
        self.theme_refreshed.emit()

    def change_sound_setting(self, state):
        self.config_manager.set("sound_enabled", self.sound_checkbox.isChecked())

    def import_theme(self):
        from PyQt6.QtWidgets import QFileDialog

        from src.gui.main_window import MainWindow

        from ...board.piece_themes import (
            get_piece_theme_names,
            import_theme_from_folder,
            validate_theme_folder,
        )

        folder = QFileDialog.getExistingDirectory(
            self, "Select Piece Theme Folder", "", QFileDialog.Option.ShowDirsOnly
        )
        if not folder:
            return
        is_valid, errors = validate_theme_folder(folder)
        if not is_valid:
            MainWindow.toast_from_widget(
                self, "Invalid theme: " + "; ".join(errors), "error"
            )
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
        MainWindow.toast_from_widget(
            self, f"Piece theme '{theme_name}' imported and active.", "success"
        )

    def set_advanced_visible(self, visible):
        # Appearance is intentionally available in basic mode.
        pass

    def refresh_styles(self, *args, **kwargs):
        self.setStyleSheet(Styles.get_group_box_style())
        if hasattr(self, "form"):
            self.form.refresh_styles()
        if hasattr(self, "theme_combo"):
            self.theme_combo.setStyleSheet(Styles.get_combobox_style())
        if hasattr(self, "piece_combo"):
            self.piece_combo.setStyleSheet(Styles.get_combobox_style())
        tick_path = get_resource_path("assets/images/tick.svg").replace("\\", "/")
        for checkbox in (
            getattr(self, "sound_checkbox", None),
            getattr(self, "coordinates_checkbox", None),
            getattr(self, "classification_checkbox", None),
        ):
            if checkbox:
                checkbox.setStyleSheet(Styles.get_settings_checkbox_style(tick_path))
        if hasattr(self, "import_theme_btn"):
            self.import_theme_btn.setStyleSheet(Styles.get_settings_default_button_style())
        if hasattr(self, "color_btn"):
            self.color_btn.setStyleSheet(self._accent_btn_style())
        for radio in (
            getattr(self, "_theme_mode_system", None),
            getattr(self, "_theme_mode_light", None),
            getattr(self, "_theme_mode_dark", None),
            getattr(self, "sidebar_expanded_radio", None),
            getattr(self, "sidebar_collapsed_radio", None),
            getattr(self, "accent_mode_system", None),
            getattr(self, "accent_mode_custom", None),
        ):
            if radio:
                radio.setStyleSheet(self._radio_style())
