"""AI Coach move-explanation settings."""

from PyQt6.QtWidgets import QGroupBox, QVBoxLayout

from src.utils.path_utils import get_resource_path

from ...styles import Styles
from .components import SettingsBinder, SettingsForm, make_combo
from .helpers import create_icon_button

TTL_CHOICES = [
    (7, "7 days"),
    (30, "30 days"),
    (90, "90 days"),
    (365, "1 year"),
    (None, "Never expire"),
]


class CoachSettings(QGroupBox):
    """Explanation policy for the AI Coach and its response cache."""

    def __init__(self, config_manager, parent=None):
        super().__init__("Move Explanations", parent)
        self.config_manager = config_manager
        self.setStyleSheet(Styles.get_group_box_style())
        self.setup_ui()

    def setup_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 8, 0, 0)
        outer.setSpacing(10)

        self.form = SettingsForm(self)
        self.binder = SettingsBinder(self.config_manager, self.form, self)
        outer.addWidget(self.form)

        self.explain_trivial_checkbox = self.binder.add(
            "explain_llm_for_trivial_moves"
        )
        self.explain_ttl_combo = self.binder.add(
            "explain_cache_ttl_days",
            make_combo(180),
            choices=TTL_CHOICES,
            width=180,
        )

        self.clear_explanations_btn = create_icon_button(
            "Clear Explanation Cache", "fa5s.broom", self.clear_explanations, self
        )
        self.clear_explanations_btn.setMaximumWidth(260)
        outer.addWidget(self.clear_explanations_btn)

    def clear_explanations(self) -> None:
        """Drop every cached explanation (shared confirmation with Data settings)."""
        from .data_settings import clear_analysis_cache

        clear_analysis_cache(self)

    def sync_explanation_settings(self) -> None:
        """Re-read the Coach settings from config into the widgets."""
        self.binder.load()

    def reload_from_config(self) -> None:
        self.binder.load()

    def set_advanced_visible(self, visible: bool) -> None:
        # Every row here is Advanced, so the whole card goes away in Basic mode.
        self.setVisible(visible)
        self.binder.set_advanced_visible(visible)

    def refresh_styles(self, *args, **kwargs) -> None:
        self.setStyleSheet(Styles.get_group_box_style())
        self.form.refresh_styles()
        tick_path = get_resource_path("assets/images/tick.svg").replace("\\", "/")
        self.explain_trivial_checkbox.setStyleSheet(
            Styles.get_settings_checkbox_style(tick_path)
        )
        self.explain_ttl_combo.setStyleSheet(Styles.get_combobox_style())
        self.clear_explanations_btn.setStyleSheet(
            Styles.get_settings_default_button_style()
        )
