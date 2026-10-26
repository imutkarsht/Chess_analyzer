"""AI Coach move-explanation settings."""

from PyQt6.QtWidgets import QGroupBox, QVBoxLayout

from src.utils.path_utils import get_resource_path

from ...styles import Styles
from .components import SettingsBinder, SettingsForm


class CoachSettings(QGroupBox):
    """Explanation policy for the AI Coach.

    Cache lifetime and clearing live on the Data & Storage page, next to the
    other retention controls.
    """

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
