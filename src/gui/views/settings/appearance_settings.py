"""Appearance settings: theme, accent, board pieces, and display toggles."""

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QColorDialog,
    QGroupBox,
    QHBoxLayout,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ....config.settings_schema import get_spec
from ....utils.path_utils import get_resource_path
from ...styles import Styles
from ...theme import ThemeManager
from ...theme.palette import BOARD_THEMES
from .components import (
    CONTROL_DEFAULT,
    RadioChoice,
    SettingsBinder,
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
        self.binder = SettingsBinder(self.config_manager, self.form, self)
        outer.addWidget(self.form)

        self._add_theme_mode_row()
        self._add_sidebar_row()
        self._add_board_theme_row()
        self._add_piece_style_row()
        self._add_board_display_rows()
        self._add_sound_row()
        self._add_accent_row()

    # ------------------------------------------------------------------
    # Rows
    # ------------------------------------------------------------------
    def _add_theme_mode_row(self):
        spec = get_spec("theme_mode")
        self.theme_mode_choice = RadioChoice(
            [(choice.value, choice.label) for choice in spec.choices]
        )
        self.binder.add(
            "theme_mode",
            self.theme_mode_choice,
            hint="",
            width=None,
            on_change=self._on_theme_mode_changed,
        )

    def _on_theme_mode_changed(self, mode):
        ThemeManager.set_theme_mode(mode)

    def _add_sidebar_row(self):
        self.sidebar_choice = RadioChoice([(False, "Expanded"), (True, "Collapsed")])
        self.sidebar_expanded_radio, self.sidebar_collapsed_radio = (
            self.sidebar_choice.radios()
        )
        self.binder.add(
            "sidebar_start_collapsed",
            self.sidebar_choice,
            label="Sidebar",
            hint="",
            width=None,
            on_change=lambda _value: self.sidebar_prefs_changed.emit(),
        )

    def sync_sidebar_pref(self):
        """Re-read the saved sidebar preference into the radio group."""
        self.sidebar_choice.setValue(
            bool(self.config_manager.get("sidebar_start_collapsed", False))
        )

    def _add_board_theme_row(self):
        self.theme_combo = self.binder.add(
            "board_theme",
            make_combo(CONTROL_DEFAULT),
            choices=[(name, name) for name in BOARD_THEMES],
            on_change=lambda _value: self.theme_refreshed.emit(),
        )

    def _add_piece_style_row(self):
        from ...board.piece_themes import get_piece_theme_names

        self.piece_combo = make_combo(CONTROL_DEFAULT)
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

        self.binder.add(
            "piece_theme",
            self.piece_combo,
            choices=[(name, name) for name in get_piece_theme_names()],
            hint="",
            width=None,
            container=row,
            on_change=lambda _value: self.theme_refreshed.emit(),
        )

    def _add_board_display_rows(self):
        self.coordinates_checkbox = self.binder.add(
            "board_show_coordinates",
            make_checkbox("Show coordinates"),
            hint="",
            width=None,
            on_change=lambda _value: self.theme_refreshed.emit(),
        )

        self.classification_checkbox = self.binder.add(
            "board_show_classification",
            make_checkbox("Show move quality badges"),
            hint="",
            width=None,
            on_change=lambda _value: self.theme_refreshed.emit(),
        )

    def _add_sound_row(self):
        self.sound_checkbox = self.binder.add(
            "sound_enabled",
            make_checkbox("Enable Sound Effects"),
            hint="",
            width=None,
        )

    def _add_accent_row(self):
        self.color_btn = QPushButton("Choose Color")
        self.color_btn.setStyleSheet(self._accent_btn_style())
        self.color_btn.setMaximumWidth(150)
        self.color_btn.clicked.connect(self.change_accent_color)

        self.accent_choice = RadioChoice(
            [(choice.value, choice.label) for choice in get_spec("accent_mode").choices],
            trailing=self.color_btn,
        )
        self.accent_mode_system, self.accent_mode_custom = self.accent_choice.radios()
        self._update_accent_btn_visibility()
        self.binder.add(
            "accent_mode",
            self.accent_choice,
            hint="",
            width=None,
            on_change=self._on_accent_mode_changed,
        )

    def _on_accent_mode_changed(self, mode):
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
            self.accent_choice.setValue("custom")
            self._update_accent_btn_visibility()
            ThemeManager.set_accent(color.name())
            self.theme_refreshed.emit()

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

        choices = [(name, name) for name in get_piece_theme_names()]
        SettingsBinder._populate_combo(self.piece_combo, choices)
        self.piece_combo.setCurrentIndex(max(self.piece_combo.findData(theme_name), 0))
        MainWindow.toast_from_widget(
            self, f"Piece theme '{theme_name}' imported and active.", "success"
        )

    # ------------------------------------------------------------------
    # Lifecycle hooks used by SettingsView
    # ------------------------------------------------------------------
    def reload_from_config(self):
        self.binder.load()
        self._update_accent_btn_visibility()

    def set_advanced_visible(self, visible):
        self.binder.set_advanced_visible(visible)

    def refresh_styles(self, *args, **kwargs):
        self.setStyleSheet(Styles.get_group_box_style())
        if hasattr(self, "form"):
            self.form.refresh_styles()
        for combo in (getattr(self, "theme_combo", None), getattr(self, "piece_combo", None)):
            if combo:
                combo.setStyleSheet(Styles.get_combobox_style())
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
        for choice in (
            getattr(self, "theme_mode_choice", None),
            getattr(self, "sidebar_choice", None),
            getattr(self, "accent_choice", None),
        ):
            if choice:
                choice.refresh_styles()
