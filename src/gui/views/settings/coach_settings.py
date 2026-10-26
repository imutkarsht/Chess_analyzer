"""AI Coach move-explanation settings."""

from PyQt6.QtWidgets import QGroupBox, QLabel, QVBoxLayout

from src.utils.path_utils import get_resource_path

from ...styles import Styles
from .components import (
    CONTROL_NARROW,
    SettingsBinder,
    SettingsForm,
    make_combo,
)


class CoachSettings(QGroupBox):
    """Explanation policy and generation tuning for the AI Coach.

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
        self.temperature_input = self.binder.add(
            "explain_temperature", width=CONTROL_NARROW
        )
        self.max_tokens_input = self.binder.add(
            "explain_max_tokens", width=CONTROL_NARROW
        )
        self.reasoning_effort_combo = self.binder.add(
            "explain_reasoning_effort",
            make_combo(180),
            width=180,
        )

        cache_note = QLabel(
            "Explanation cache lifetime and clearing live in Data & Storage."
        )
        cache_note.setWordWrap(True)
        cache_note.setStyleSheet(
            Styles.get_secondary_label_style(size=11)
            + " "
            + Styles.get_transparent_label_style()
        )
        outer.addWidget(cache_note)

    def sync_explanation_settings(self) -> None:
        """Re-read the Coach settings from config into the widgets."""
        self.binder.load()

    def reload_from_config(self) -> None:
        self.binder.load()

    def set_advanced_visible(self, visible: bool) -> None:
        # The explanation toggle is Basic; only the tuning rows disappear.
        self.setVisible(True)
        self.binder.set_advanced_visible(visible)

    def refresh_styles(self, *args, **kwargs) -> None:
        self.setStyleSheet(Styles.get_group_box_style())
        self.form.refresh_styles()
        self.temperature_input.setStyleSheet(Styles.get_input_style())
        self.max_tokens_input.setStyleSheet(Styles.get_input_style())
        self.reasoning_effort_combo.setStyleSheet(Styles.get_combobox_style())
        tick_path = get_resource_path("assets/images/tick.svg").replace("\\", "/")
        self.explain_trivial_checkbox.setStyleSheet(
            Styles.get_settings_checkbox_style(tick_path)
        )
