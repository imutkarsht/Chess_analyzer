"""Toolbar for the import workspace."""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QWidget

from src.gui.components import (
    Button,
    ButtonSize,
    ButtonVariant,
    Input,
    InputSize,
    InputVariant,
    Label,
    SegmentedControl,
    Select,
    SelectSize,
    TextRole,
    TextTone,
)
from src.gui.utils.debounce import Debouncer


class ImportToolbar(QWidget):
    """Search, perspective-aware filters, counts, and display toggles."""

    filters_changed = pyqtSignal()
    boards_toggled = pyqtSignal(bool)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(24, 12, 24, 12)
        layout.setSpacing(8)

        self.search_input = Input(
            placeholder="Filter games…",
            variant=InputVariant.SEARCH,
            size=InputSize.SM,
            clearable=True,
        )
        self.search_input.setMinimumWidth(220)
        self.search_input.setMaximumWidth(380)
        self._search_debounce = Debouncer(self, interval=150)
        self.search_input.textChanged.connect(
            lambda *_: self._search_debounce.call(
                self.filters_changed.emit
            )
        )
        layout.addWidget(self.search_input, 1)

        self.result_filter = Select(
            self._color_result_options(),
            size=SelectSize.SM,
            min_width=110,
            on_change=lambda _value: self.filters_changed.emit(),
        )
        self.color_filter = Select(
            [
                ("All colors", "all"),
                ("White", "white"),
                ("Black", "black"),
            ],
            size=SelectSize.SM,
            min_width=100,
            on_change=lambda _value: self.filters_changed.emit(),
        )
        self.color_filter.setVisible(False)
        self.time_filter = Select(
            [
                ("All speeds", "all"),
                ("Bullet", "Bullet"),
                ("Blitz", "Blitz"),
                ("Rapid", "Rapid"),
                ("Classical", "Classical"),
                ("Daily", "Daily"),
                ("Unknown", "Unknown"),
            ],
            size=SelectSize.SM,
            min_width=110,
            on_change=lambda _value: self.filters_changed.emit(),
        )
        self.history_filter = SegmentedControl(
            [("All", "all"), ("New", "new"), ("Saved", "saved")],
            value="all",
        )
        self.history_filter.valueChanged.connect(
            lambda _value: self.filters_changed.emit()
        )
        layout.addWidget(self.result_filter)
        layout.addWidget(self.color_filter)
        layout.addWidget(self.time_filter)
        layout.addWidget(self.history_filter)

        self.lbl_filtered = Label(
            "",
            role=TextRole.CAPTION,
            tone=TextTone.MUTED,
        )
        layout.addWidget(self.lbl_filtered)

        self.btn_clear_filters = Button(
            "Clear filters",
            ButtonVariant.GHOST,
            ButtonSize.SM,
            on_click=self.reset_filters,
        )
        self.btn_clear_filters.setVisible(False)
        self.btn_boards = Button(
            "Boards",
            ButtonVariant.GHOST,
            ButtonSize.SM,
            icon="fa5s.chess-board",
            checkable=True,
            tooltip="Show board thumbnails",
            on_click=lambda: self.boards_toggled.emit(
                self.btn_boards.isChecked()
            ),
        )
        layout.addWidget(self.btn_clear_filters)
        layout.addWidget(self.btn_boards)

    @staticmethod
    def _color_result_options() -> list[tuple[str, str]]:
        return [
            ("All results", "all"),
            ("White win", "1-0"),
            ("Black win", "0-1"),
            ("Draw", "1/2-1/2"),
        ]

    @staticmethod
    def _perspective_result_options() -> list[tuple[str, str]]:
        return [
            ("All results", "all"),
            ("My wins", "my_win"),
            ("My losses", "my_loss"),
            ("My draws", "my_draw"),
            ("My games", "my_game"),
            ("Not my games", "other"),
        ]

    def set_perspective(self, perspective: bool) -> None:
        self.color_filter.set_current_index(0, emit=False)
        self.color_filter.setVisible(perspective)
        self.result_filter.set_options(
            (
                self._perspective_result_options()
                if perspective
                else self._color_result_options()
            ),
            preserve_value=False,
            emit=False,
        )

    def reset_filters(self, *, emit: bool = True) -> None:
        self._search_debounce.cancel()
        self.search_input.blockSignals(True)
        self.search_input.clear()
        self.search_input.blockSignals(False)
        self.result_filter.set_current_index(0, emit=False)
        self.color_filter.set_current_index(0, emit=False)
        self.time_filter.set_current_index(0, emit=False)
        self.history_filter.set_value("all", emit=False)
        if emit:
            self.filters_changed.emit()

    def filters_active(self) -> bool:
        return (
            bool(self.search_input.text().strip())
            or self.result_filter.current_value() != "all"
            or (
                not self.color_filter.isHidden()
                and self.color_filter.current_value() != "all"
            )
            or self.time_filter.current_value() != "all"
            or self.history_filter.value() != "all"
        )

    def update_counts(self, shown: int, total: int) -> None:
        self.lbl_filtered.setText(
            f"{shown} shown" if shown != total else ""
        )
        self.btn_clear_filters.setVisible(self.filters_active())

    def set_boards_checked(self, enabled: bool) -> None:
        self.btn_boards.setChecked(enabled)
        self.btn_boards.set_variant(
            ButtonVariant.FILLED if enabled else ButtonVariant.GHOST
        )

    def refresh_styles(self) -> None:
        self.btn_clear_filters.refresh_styles()
        self.btn_boards.refresh_styles()
        self.search_input.refresh_styles()
        self.result_filter.refresh_styles()
        self.color_filter.refresh_styles()
        self.time_filter.refresh_styles()
        self.history_filter.refresh_styles()
