"""Cache retention policy: TTLs and the analysis-cache capacity."""

from PyQt6.QtWidgets import QVBoxLayout

from ....backend.storage.cache import AnalysisCache
from ...styles import Styles
from .components import SettingsBinder, SettingsForm, make_select
from .modern_widgets import ModernSliderCounter
from .storage_card import StorageCard

EXPLORER_TTL_CHOICES = [
    (1, "1 hour"),
    (6, "6 hours"),
    (24, "24 hours"),
    (48, "48 hours"),
    (168, "7 days"),
    (720, "30 days"),
    (None, "Never expire"),
]

EXPLANATION_TTL_CHOICES = [
    (7, "7 days"),
    (30, "30 days"),
    (90, "90 days"),
    (365, "1 year"),
    (None, "Never expire"),
]


class RetentionSettings(StorageCard):
    """How long caches are kept and how many evaluations are stored."""

    def __init__(self, config_manager, parent=None):
        super().__init__("Cache Retention", parent)
        self.config_manager = config_manager
        self.setup_ui()

    def setup_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 8, 0, 0)

        self.form = SettingsForm(self)
        self.binder = SettingsBinder(self.config_manager, self.form, self)
        outer.addWidget(self.form)

        self.explorer_ttl_combo = self.binder.add(
            "explorer_cache_ttl_hours",
            make_select(180),
            choices=EXPLORER_TTL_CHOICES,
            width=180,
        )

        self.analysis_cap_input = ModernSliderCounter(
            10_000,
            1_000_000,
            step=10_000,
            format_value=lambda val: f"{int(val):,}",
            parent=self,
        )
        # The grouped value ("250,000") needs more room than the default label.
        self.analysis_cap_input.value_label.setFixedWidth(64)
        self.analysis_cap_input.setMaximumWidth(280)
        self.binder.add(
            "analysis_cache_max_entries",
            self.analysis_cap_input,
            hint="Oldest entries are evicted first.",
            width=None,
            on_change=self._apply_capacity,
        )

        self.explain_ttl_combo = self.binder.add(
            "explain_cache_ttl_days",
            make_select(180),
            choices=EXPLANATION_TTL_CHOICES,
            width=180,
        )

        self.register_busy_widgets(self.analysis_cap_input)

    def _apply_capacity(self, value) -> None:
        """Apply a lower cap immediately instead of waiting for the next run."""
        try:
            cap = int(value)
        except (TypeError, ValueError):
            return
        self.run_task(
            lambda: AnalysisCache().prune_cache(cap),
            self._on_pruned,
            loading_message="Pruning old evaluations…",
        )

    def _on_pruned(self, removed) -> None:
        if removed:
            self._toast(f"Pruned {int(removed):,} cached evaluations.")
        self.data_changed.emit()

    # ------------------------------------------------------------------
    # Lifecycle hooks used by SettingsView
    # ------------------------------------------------------------------
    def reload_from_config(self) -> None:
        self.binder.load()

    def set_advanced_visible(self, visible: bool) -> None:
        # Every row is advanced, so the whole card disappears in Basic mode.
        self.setVisible(visible)
        self.binder.set_advanced_visible(visible)

    def refresh_styles(self, *args, **kwargs) -> None:
        self.setStyleSheet(Styles.get_group_box_style())
        self.form.refresh_styles()
        self.analysis_cap_input.refresh_styles()
