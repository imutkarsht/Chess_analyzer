"""Appearance card for ordering the Performance Dashboard cards."""

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QGroupBox, QHBoxLayout, QVBoxLayout

from ...components import SortableItem, SortableItemList
from ...styles import Styles
from ..metrics.card_registry import (
    DEFAULT_CARD_ORDER,
    SORTABLE_BY_KEY,
    normalise_card_order,
)
from .helpers import create_icon_button


class DashboardLayoutSettings(QGroupBox):
    """Reorder the chart cards on the Performance Dashboard."""

    order_changed = pyqtSignal()

    def __init__(self, config_manager, parent=None):
        super().__init__("Dashboard Layout", parent)
        self.config_manager = config_manager
        self.setStyleSheet(Styles.get_group_box_style())
        self._order = normalise_card_order(
            self.config_manager.get("metrics_card_order", [])
        )
        self.setup_ui()

    def setup_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 8, 0, 0)
        outer.setSpacing(10)

        self.sortable_list = SortableItemList()
        self.sortable_list.order_changed.connect(self._on_order_changed)
        outer.addWidget(self.sortable_list)

        self.reset_btn = create_icon_button(
            "Reset order", "fa5s.undo", self.reset_order, self
        )
        row = QHBoxLayout()
        row.addWidget(self.reset_btn)
        row.addStretch(1)
        outer.addLayout(row)

        self._populate()

    # ------------------------------------------------------------------
    # Order API
    # ------------------------------------------------------------------
    def current_order(self) -> list[str]:
        return list(self._order)

    def apply_order(self, keys) -> None:
        """Persist and display a new card order (used by reset and tests)."""
        self._order = normalise_card_order(keys)
        self._populate()
        self._save_order()

    def reset_order(self) -> None:
        self.apply_order(DEFAULT_CARD_ORDER)

    def _save_order(self) -> None:
        self.config_manager.set("metrics_card_order", list(self._order))
        self.order_changed.emit()

    def _on_order_changed(self, keys) -> None:
        order = normalise_card_order(keys)
        if order == self._order:
            return
        self._order = order
        self._save_order()

    def _populate(self) -> None:
        self.sortable_list.set_items(
            [
                SortableItem(
                    key=key,
                    title=SORTABLE_BY_KEY[key].title,
                    description=SORTABLE_BY_KEY[key].description,
                    icon=SORTABLE_BY_KEY[key].icon,
                )
                for key in self._order
                if key in SORTABLE_BY_KEY
            ]
        )
        self.sortable_list.set_visible_rows(5)

    # ------------------------------------------------------------------
    # Lifecycle hooks used by SettingsView
    # ------------------------------------------------------------------
    def reload_from_config(self) -> None:
        self._order = normalise_card_order(
            self.config_manager.get("metrics_card_order", [])
        )
        self._populate()

    def set_advanced_visible(self, visible: bool) -> None:
        # Ordering is useful in both Basic and Advanced modes.
        pass

    def refresh_styles(self, *args, **kwargs) -> None:
        self.setStyleSheet(Styles.get_group_box_style())
        self.reset_btn.setStyleSheet(Styles.get_settings_default_button_style())
        self.sortable_list.viewport().update()
