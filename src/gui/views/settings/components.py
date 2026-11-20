"""Reusable settings rows and fields.

The goal is to make widths, spacing, labels, hints, and advanced visibility
live in one place instead of being reimplemented in every settings card.
"""

from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtCore import QObject, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from src.config.settings_schema import SettingSpec, get_spec
from src.gui.components import (
    Checkbox,
    CheckboxVariant,
    DecimalInput,
    Input,
    Label,
    NumberInput,
    Select,
    SelectOption,
    TextRole,
    TextTone,
)
from src.gui.styles import Styles

# Central size tokens for settings controls.
CONTROL_NARROW = 120
CONTROL_DEFAULT = 300
CONTROL_WIDE = 520
CONTROL_PATH = 600
LABEL_WIDTH = 160
ROW_SPACING = 10

# Distinguishes "derive width from the spec" from "no maximum width".
_UNSET = object()

# Returned by widget readers when a value cannot be parsed.
_INVALID = object()


class SettingsForm(QWidget):
    """A QFormLayout with consistent labels, hints, widths, and advanced rows."""

    def __init__(self, parent=None, label_width: int = LABEL_WIDTH):
        super().__init__(parent)
        self._label_width = label_width
        self._advanced_rows: list[tuple[Label, QWidget]] = []
        self._advanced_visible = True
        self._forced_visible: set[QWidget] = set()

        self.form = QFormLayout(self)
        self.form.setContentsMargins(0, 12, 0, 0)
        self.form.setSpacing(ROW_SPACING)
        self.form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)

    def add_row(
        self,
        label: str,
        control: QWidget,
        *,
        hint: str = "",
        advanced: bool = False,
        width: int | None = CONTROL_DEFAULT,
        inline_hint: bool = False,
    ) -> QWidget:
        """Add a label/control row and return the control wrapper.

        ``inline_hint`` places the description beside the control (as used for
        boolean toggles) instead of stacking it underneath.
        """
        lbl = Label(label, role=TextRole.BODY)
        lbl.setFixedWidth(self._label_width)

        wrapper = QWidget()
        wrapper.setStyleSheet(Styles.get_transparent_style())

        if width is not None:
            control.setMaximumWidth(width)

        hint_lbl = None
        if hint:
            hint_lbl = Label(
                hint,
                role=TextRole.MICRO,
                tone=TextTone.SECONDARY,
                wrap=True,
            )

        if inline_hint:
            box = QHBoxLayout(wrapper)
            box.setContentsMargins(0, 0, 0, 0)
            box.setSpacing(8)
            box.addWidget(control)
            if hint_lbl is not None:
                box.addWidget(hint_lbl, 1)
            else:
                box.addStretch(1)
        else:
            box = QVBoxLayout(wrapper)
            box.setContentsMargins(0, 0, 0, 0)
            box.setSpacing(3)
            box.addWidget(control)
            if hint_lbl is not None:
                box.addWidget(hint_lbl)

        self.form.addRow(lbl, wrapper)
        if advanced:
            self._advanced_rows.append((lbl, wrapper))
        return wrapper

    def set_advanced_visible(self, visible: bool) -> None:
        self._advanced_visible = visible
        self._apply_advanced_visibility()

    def set_row_forced_visible(self, row: QWidget, visible: bool) -> None:
        """Keep an advanced row visible outside Advanced mode.

        Used for controls that stop being merely "advanced" for a specific
        selection (e.g. a custom provider's Base URL). The row still follows
        ``set_advanced_visible`` for every other state.
        """
        if visible:
            self._forced_visible.add(row)
        else:
            self._forced_visible.discard(row)
        self._apply_advanced_visibility()

    def _apply_advanced_visibility(self) -> None:
        for lbl, wrapper in self._advanced_rows:
            shown = self._advanced_visible or wrapper in self._forced_visible
            lbl.setVisible(shown)
            wrapper.setVisible(shown)

    def refresh_styles(self) -> None:
        """Labels follow the global stylesheet; retained for call-site compatibility."""


def make_select(max_width: int = CONTROL_DEFAULT) -> Select:
    """A settings dropdown pinned to a deliberate width.

    A maximum alone lets the control collapse to its shortest entry, which
    clips text like "30 days"; settings controls are deliberately sized, so
    pin both bounds.
    """
    select = Select(min_width=max_width)
    select.setMaximumWidth(max_width)
    return select


def make_line_edit(placeholder: str = "", max_width: int = CONTROL_DEFAULT) -> Input:
    """Settings-row text field: one central Input, no local styling."""
    edit = Input(placeholder=placeholder)
    edit.setMaximumWidth(max_width)
    return edit


def make_spin(maximum: int = 9999, minimum: int = 0, step: int = 1, suffix: str = "") -> NumberInput:
    return NumberInput(minimum, maximum, step, suffix, width=140)


def make_double_spin(
    maximum: float = 100.0, minimum: float = 0.0, step: float = 0.1, suffix: str = ""
) -> DecimalInput:
    return DecimalInput(minimum, maximum, step, suffix, width=140)


class SettingsBinder(QObject):
    """Binds widgets to settings specs and persists changes centrally."""

    changed = pyqtSignal(str, object)

    def __init__(self, config_manager, form: SettingsForm, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.form = form
        self.widgets: dict[str, QWidget] = {}
        self._advanced: list[str] = []
        self._callbacks: dict[str, Callable] = {}

    def add(
        self,
        key: str,
        widget: QWidget | None = None,
        *,
        choices: list[tuple[object, str]] | None = None,
        advanced: bool | None = None,
        hint: str | None = None,
        label: str | None = None,
        width: int | None | object = _UNSET,
        inline_hint: bool | None = None,
        on_change: Callable | None = None,
        container: QWidget | None = None,
    ) -> QWidget:
        spec = get_spec(key)
        if spec is None:
            raise KeyError(f"Unknown setting: {key}")

        if choices is None and spec.choices:
            choices = [(choice.value, choice.label) for choice in spec.choices]

        if widget is None:
            widget = self._make_widget(spec, choices)
        elif choices and isinstance(widget, Select):
            self._populate_select(widget, choices)

        if advanced is None:
            advanced = spec.tier == "advanced"
        if hint is None:
            hint = spec.description
        if width is _UNSET:
            width = self._width_for(spec, widget)
        if inline_hint is None:
            inline_hint = spec.kind == "bool"

        self.form.add_row(
            label or spec.label,
            container or widget,
            hint=hint,
            advanced=advanced,
            width=width,
            inline_hint=inline_hint,
        )
        self.widgets[key] = widget
        if advanced:
            self._advanced.append(key)
        if on_change is not None:
            self._callbacks[key] = on_change
        self._connect(key, widget)
        self._set_widget(key, self.config_manager.get(key, spec.default))
        return widget

    def _make_widget(self, spec: SettingSpec, choices):
        if spec.kind == "bool":
            return Checkbox("", CheckboxVariant.FLAT)
        if spec.kind == "choice":
            select = make_select(CONTROL_DEFAULT)
            self._populate_select(
                select, choices or [(c.value, c.label) for c in spec.choices]
            )
            return select
        if spec.kind == "secret":
            field = Input(password=True)
            field.setMaximumWidth(420)
            return field
        if spec.kind == "path":
            return make_line_edit(spec.description, CONTROL_WIDE)
        if spec.kind == "int":
            return make_spin(
                maximum=int(spec.maximum if spec.maximum is not None else 9999),
                minimum=int(spec.minimum if spec.minimum is not None else 0),
                step=int(spec.step or 1),
            )
        if spec.kind == "float":
            return make_double_spin(
                maximum=float(spec.maximum if spec.maximum is not None else 100.0),
                minimum=float(spec.minimum if spec.minimum is not None else 0.0),
                step=float(spec.step or 0.1),
            )
        return make_line_edit("", CONTROL_DEFAULT)

    @staticmethod
    def _populate_select(select: Select, choices) -> None:
        select.blockSignals(True)
        try:
            select.set_options(
                [SelectOption(str(label), value) for value, label in choices]
            )
        finally:
            select.blockSignals(False)

    @staticmethod
    def _width_for(spec: SettingSpec, widget: QWidget) -> int | None:
        if spec.kind in {"bool", "choice", "secret", "path"}:
            return CONTROL_DEFAULT if spec.kind != "path" else CONTROL_WIDE
        return None

    @staticmethod
    def _has_value_signal(widget: QWidget) -> bool:
        """True for binder-protocol widgets and native numeric editors."""
        return (
            hasattr(widget, "settingValue") and hasattr(widget, "valueChanged")
        ) or isinstance(widget, (QSpinBox, QDoubleSpinBox))

    def _connect(self, key: str, widget: QWidget) -> None:
        spec = get_spec(key)
        if spec is None:
            return

        def commit() -> None:
            self._commit_widget(key)

        if self._has_value_signal(widget):
            widget.valueChanged.connect(lambda _value: commit())
        elif hasattr(widget, "editingFinished") and hasattr(widget, "text"):
            widget.editingFinished.connect(commit)
        elif spec.kind == "bool":
            widget.stateChanged.connect(lambda _state: commit())

    def _read_widget(self, key: str, widget: QWidget):
        """Read a widget's current value, coerced to the spec's Python type."""
        spec = get_spec(key)
        if spec is None:
            return _INVALID

        if hasattr(widget, "settingValue"):
            raw = widget.settingValue()
        elif isinstance(widget, (QSpinBox, QDoubleSpinBox)):
            raw = widget.value()
        elif spec.kind == "bool" and isinstance(widget, Checkbox):
            raw = widget.isChecked()
        else:
            raw = widget.text().strip()

        if raw is None:
            # A null combo entry is only valid for explicitly nullable specs.
            return None if spec.nullable and spec.kind in {"int", "float"} else _INVALID

        try:
            if spec.kind == "int":
                return int(float(raw))
            if spec.kind == "float":
                return float(raw)
            if spec.kind == "bool":
                return bool(raw)
        except (TypeError, ValueError):
            return _INVALID
        return raw

    def _commit_widget(self, key: str) -> None:
        widget = self.widgets.get(key)
        if widget is None:
            return
        value = self._read_widget(key, widget)
        if value is _INVALID:
            return
        spec = get_spec(key)
        current = self.config_manager.get(key, spec.default if spec else None)
        if current == value:
            return
        self.config_manager.set(key, value)
        callback = self._callbacks.get(key)
        if callback is not None:
            callback(value)
        self.changed.emit(key, value)

    def commit_all(self) -> None:
        """Flush every bound widget to config (used by the Save button)."""
        for key in self.widgets:
            self._commit_widget(key)

    def set_choices(self, key: str, choices: list[tuple[object, str]]) -> None:
        """Replace a bound select's options (e.g. after importing a theme)."""
        widget = self.widgets.get(key)
        if isinstance(widget, Select):
            self._populate_select(widget, choices)

    def _set_widget(self, key: str, value) -> None:
        widget = self.widgets[key]
        spec = get_spec(key)
        if spec is None:
            return
        widget.blockSignals(True)
        try:
            if hasattr(widget, "setSettingValue"):
                widget.setSettingValue(value)
            elif isinstance(widget, (QSpinBox, QDoubleSpinBox)):
                widget.setValue(value)
            elif spec.kind == "bool":
                widget.setChecked(bool(value))
            else:
                widget.setText("" if value is None else str(value))
        finally:
            widget.blockSignals(False)

    def load(self) -> None:
        for key in self.widgets:
            spec = get_spec(key)
            default = spec.default if spec is not None else None
            self._set_widget(key, self.config_manager.get(key, default))

    def set_advanced_visible(self, visible: bool) -> None:
        self.form.set_advanced_visible(visible)
