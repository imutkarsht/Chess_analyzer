"""Full-game analysis settings."""

from PyQt6.QtWidgets import QGroupBox, QVBoxLayout

from src.utils.path_utils import get_resource_path

from ...styles import Styles
from .components import SettingsBinder, SettingsForm, make_combo
from .modern_widgets import ModernSliderCounter

# The engine also receives a depth limit, so "No cap" means depth-only.
TIME_CAP_CHOICES = [
    (0.5, "0.5 s"),
    (1.0, "1 s"),
    (2.0, "2 s"),
    (3.0, "3 s"),
    (5.0, "5 s"),
    (10.0, "10 s"),
    (None, "No cap"),
]


class FullAnalysisSettings(QGroupBox):
    """How the engine searches positions during a full-game analysis."""

    def __init__(self, config_manager, parent=None):
        super().__init__("Full Analysis", parent)
        self.config_manager = config_manager
        self.setStyleSheet(Styles.get_group_box_style())
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 0)

        self.form = SettingsForm(self)
        self.binder = SettingsBinder(self.config_manager, self.form, self)
        layout.addWidget(self.form)

        self.depth_combo = self.binder.add(
            "analysis_depth",
            make_combo(100),
            choices=[(depth, str(depth)) for depth in range(10, 26)],
            hint="Higher depth is more accurate but slower.",
            width=100,
        )

        self.time_cap_combo = self.binder.add(
            "time_per_move",
            make_combo(150),
            choices=TIME_CAP_CHOICES,
            width=150,
        )

        self.multi_pv_input = ModernSliderCounter(1, 5, step=1, parent=self)
        self.multi_pv_input.setMaximumWidth(220)
        self.binder.add(
            "multi_pv",
            self.multi_pv_input,
            hint="1–5; raising this multiplies analysis time and heat.",
            width=None,
        )

        self.cache_checkbox = self.binder.add("use_cache")

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
        self.depth_combo.setStyleSheet(Styles.get_combobox_style())
        self.time_cap_combo.setStyleSheet(Styles.get_combobox_style())
        self.multi_pv_input.refresh_styles()
        tick_path = get_resource_path("assets/images/tick.svg").replace("\\", "/")
        self.cache_checkbox.setStyleSheet(
            Styles.get_settings_checkbox_style(tick_path)
        )
