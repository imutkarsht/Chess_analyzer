"""Live engine panel settings."""

from PyQt6.QtWidgets import QGroupBox, QVBoxLayout

from src.utils.path_utils import get_resource_path

from ...styles import Styles
from .components import SettingsBinder, SettingsForm
from .modern_widgets import ModernSliderCounter


class LiveAnalysisSettings(QGroupBox):
    """Budget and line display for the live engine panel."""

    def __init__(self, config_manager, parent=None):
        super().__init__("Live Analysis", parent)
        self.config_manager = config_manager
        self.setStyleSheet(Styles.get_group_box_style())
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 0)

        self.form = SettingsForm(self)
        self.binder = SettingsBinder(self.config_manager, self.form, self)
        layout.addWidget(self.form)

        self.engine_lines_checkbox = self.binder.add("engine_lines_enabled")

        self.live_time_input = ModernSliderCounter(
            0.5, 10.0, step=0.1, is_float=True, parent=self
        )
        self.live_time_input.setMaximumWidth(220)
        self.binder.add(
            "live_analysis_time",
            self.live_time_input,
            hint="0.5–10.0; per-position CPU budget for the live panel.",
            width=None,
        )

        self.live_multi_pv_input = ModernSliderCounter(1, 5, step=1, parent=self)
        self.live_multi_pv_input.setMaximumWidth(220)
        self.binder.add(
            "live_multi_pv",
            self.live_multi_pv_input,
            hint="1–5 lines. Independent of the full-analysis Multi-PV cost.",
            width=None,
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
        self.live_time_input.refresh_styles()
        self.live_multi_pv_input.refresh_styles()
        tick_path = get_resource_path("assets/images/tick.svg").replace("\\", "/")
        self.engine_lines_checkbox.setStyleSheet(
            Styles.get_settings_checkbox_style(tick_path)
        )
