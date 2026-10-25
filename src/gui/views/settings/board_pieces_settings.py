"""Board rendering and piece set settings."""

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
)

from ....utils.path_utils import get_resource_path
from ...styles import Styles
from ...theme.palette import BOARD_THEMES
from .components import CONTROL_DEFAULT, SettingsBinder, SettingsForm, make_combo
from .helpers import create_icon_button


class BoardPiecesSettings(QGroupBox):
    """Board colours, pieces, and annotation overlays."""

    theme_refreshed = pyqtSignal()

    def __init__(self, config_manager, parent=None):
        super().__init__("Board && Pieces", parent)
        self.config_manager = config_manager
        self.setStyleSheet(Styles.get_group_box_style())
        self.setup_ui()

    def setup_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 8, 0, 0)

        self.form = SettingsForm(self)
        self.binder = SettingsBinder(self.config_manager, self.form, self)
        outer.addWidget(self.form)

        self._add_board_theme_row()
        self._add_piece_style_row()
        self._add_board_display_rows()

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
            on_change=lambda _value: self.theme_refreshed.emit(),
        )
        self.classification_checkbox = self.binder.add(
            "board_show_classification",
            on_change=lambda _value: self.theme_refreshed.emit(),
        )
        self.best_move_arrow_checkbox = self.binder.add(
            "board_show_best_move_arrow",
            on_change=lambda _value: self.theme_refreshed.emit(),
        )
        self.last_move_checkbox = self.binder.add(
            "board_show_last_move",
            on_change=lambda _value: self.theme_refreshed.emit(),
        )
        self.eval_bar_checkbox = self.binder.add(
            "board_show_eval_bar",
            on_change=lambda _value: self.theme_refreshed.emit(),
        )

    def import_theme(self):
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
        self.binder.set_choices("piece_theme", choices)
        self.piece_combo.setCurrentIndex(max(self.piece_combo.findData(theme_name), 0))
        MainWindow.toast_from_widget(
            self, f"Piece theme '{theme_name}' imported and active.", "success"
        )

    # ------------------------------------------------------------------
    # Lifecycle hooks used by SettingsView
    # ------------------------------------------------------------------
    def reload_from_config(self):
        self.binder.load()

    def set_advanced_visible(self, visible):
        self.binder.set_advanced_visible(visible)

    def refresh_styles(self, *args, **kwargs):
        self.setStyleSheet(Styles.get_group_box_style())
        self.form.refresh_styles()
        self.theme_combo.setStyleSheet(Styles.get_combobox_style())
        self.piece_combo.setStyleSheet(Styles.get_combobox_style())
        self.import_theme_btn.setStyleSheet(Styles.get_settings_default_button_style())
        tick_path = get_resource_path("assets/images/tick.svg").replace("\\", "/")
        for checkbox in (
            self.coordinates_checkbox,
            self.classification_checkbox,
            self.best_move_arrow_checkbox,
            self.last_move_checkbox,
            self.eval_bar_checkbox,
        ):
            checkbox.setStyleSheet(Styles.get_settings_checkbox_style(tick_path))
