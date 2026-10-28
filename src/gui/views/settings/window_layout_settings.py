"""Window and sidebar layout settings."""

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QGroupBox, QVBoxLayout

from ....utils.path_utils import get_resource_path
from ...styles import Styles
from .components import RadioChoice, SettingsBinder, SettingsForm, make_select


class WindowLayoutSettings(QGroupBox):
    """Sidebar behaviour and window geometry persistence."""

    sidebar_prefs_changed = pyqtSignal()
    history_view_changed = pyqtSignal()

    def __init__(self, config_manager, parent=None):
        super().__init__("Window && Layout", parent)
        self.config_manager = config_manager
        self.setStyleSheet(Styles.get_group_box_style())
        self.setup_ui()

    def setup_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 8, 0, 0)

        self.form = SettingsForm(self)
        self.binder = SettingsBinder(self.config_manager, self.form, self)
        outer.addWidget(self.form)

        self._add_sidebar_row()
        self.history_view_combo = self.binder.add(
            "history_view_mode",
            make_select(180),
            width=180,
            on_change=lambda _value: self.history_view_changed.emit(),
        )
        self.remember_window_checkbox = self.binder.add("remember_window_geometry")

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
        self.sidebar_choice.refresh_styles()
        tick_path = get_resource_path("assets/images/tick.svg").replace("\\", "/")
        self.remember_window_checkbox.setStyleSheet(
            Styles.get_settings_checkbox_style(tick_path)
        )
