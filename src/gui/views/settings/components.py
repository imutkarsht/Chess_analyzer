"""Reusable settings rows and fields.

The goal is to make widths, spacing, labels, hints, and advanced visibility
live in one place instead of being reimplemented in every settings card.
"""

from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtCore import QObject, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QRadioButton,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from src.config.settings_schema import SettingSpec, get_spec
from src.gui.components.select import Select, SelectOption
from src.gui.styles import Styles
from src.utils.path_utils import get_resource_path

from .helpers import create_icon_button

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


def _tick_path() -> str:
    return get_resource_path("assets/images/tick.svg").replace("\\", "/")


class SettingsForm(QWidget):
    """A QFormLayout with consistent labels, hints, widths, and advanced rows."""

    def __init__(self, parent=None, label_width: int = LABEL_WIDTH):
        super().__init__(parent)
        self._label_width = label_width
        self._advanced_rows: list[tuple[QLabel, QWidget]] = []
        self._label_widgets: list[QLabel] = []
        self._hint_widgets: list[QLabel] = []
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
        lbl = QLabel(label)
        lbl.setFixedWidth(self._label_width)
        lbl.setStyleSheet(
            Styles.get_label_style(size=13) + " " + Styles.get_transparent_label_style()
        )
        self._label_widgets.append(lbl)

        wrapper = QWidget()
        wrapper.setStyleSheet(Styles.get_transparent_label_style())

        if width is not None:
            control.setMaximumWidth(width)

        hint_lbl = None
        if hint:
            hint_lbl = QLabel(hint)
            hint_lbl.setWordWrap(True)
            hint_lbl.setStyleSheet(
                Styles.get_secondary_label_style(size=11)
                + " "
                + Styles.get_transparent_label_style()
            )
            self._hint_widgets.append(hint_lbl)

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
        for lbl in self._label_widgets:
            lbl.setStyleSheet(
                Styles.get_label_style(size=13) + " " + Styles.get_transparent_label_style()
            )
        for hint in self._hint_widgets:
            hint.setStyleSheet(
                Styles.get_secondary_label_style(size=11)
                + " "
                + Styles.get_transparent_label_style()
            )


def make_select(max_width: int = CONTROL_DEFAULT) -> Select:
    """A settings dropdown pinned to a deliberate width.

    A maximum alone lets the control collapse to its shortest entry, which
    clips text like "30 days"; settings controls are deliberately sized, so
    pin both bounds.
    """
    select = Select(min_width=max_width)
    select.setMaximumWidth(max_width)
    return select


def make_checkbox(text: str, max_width: int | None = None) -> QCheckBox:
    box = QCheckBox(text)
    box.setStyleSheet(Styles.get_settings_checkbox_style(_tick_path()))
    box.setCursor(Qt.CursorShape.PointingHandCursor)
    if max_width is not None:
        box.setMaximumWidth(max_width)
    return box


def make_line_edit(placeholder: str = "", max_width: int = CONTROL_DEFAULT) -> QLineEdit:
    edit = QLineEdit()
    edit.setPlaceholderText(placeholder)
    edit.setStyleSheet(Styles.get_input_style())
    edit.setMaximumWidth(max_width)
    return edit


def make_spin(maximum: int = 9999, minimum: int = 0, step: int = 1, suffix: str = "") -> QSpinBox:
    spin = QSpinBox()
    spin.setRange(minimum, maximum)
    spin.setSingleStep(step)
    if suffix:
        spin.setSuffix(f" {suffix}")
    spin.setMaximumWidth(140)
    spin.setStyleSheet(Styles.get_input_style())
    return spin


def make_double_spin(
    maximum: float = 100.0, minimum: float = 0.0, step: float = 0.1, suffix: str = ""
) -> QDoubleSpinBox:
    spin = QDoubleSpinBox()
    spin.setRange(minimum, maximum)
    spin.setSingleStep(step)
    spin.setDecimals(1)
    if suffix:
        spin.setSuffix(f" {suffix}")
    spin.setMaximumWidth(140)
    spin.setStyleSheet(Styles.get_input_style())
    return spin


class RadioChoice(QWidget):
    """Horizontal radio group bound to a single setting value.

    Implements the binder widget protocol (``valueChanged`` +
    ``settingValue``/``setSettingValue``) so radio groups need no special
    casing in :class:`SettingsBinder`. ``valueChanged`` fires only on user
    interaction, never on programmatic ``setValue``.
    """

    valueChanged = pyqtSignal(object)

    def __init__(self, choices, *, trailing: QWidget | None = None, parent=None):
        super().__init__(parent)
        self.setStyleSheet(Styles.get_transparent_label_style())
        self._values: dict[QRadioButton, object] = {}

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        self._group = QButtonGroup(self)
        for value, label in choices:
            radio = QRadioButton(label)
            self._group.addButton(radio)
            self._values[radio] = value
            layout.addWidget(radio)

        if trailing is not None:
            layout.addWidget(trailing)

        layout.addStretch(1)
        self._group.buttonClicked.connect(self._on_button_clicked)
        self.refresh_styles()

    def _on_button_clicked(self, button: QRadioButton) -> None:
        self.valueChanged.emit(self._values[button])

    def radios(self) -> list[QRadioButton]:
        return list(self._values)

    def value(self):
        for radio, value in self._values.items():
            if radio.isChecked():
                return value
        return None

    def setValue(self, value) -> None:
        """Select the radio for ``value`` without emitting ``valueChanged``."""
        for radio, candidate in self._values.items():
            if candidate == value:
                radio.setChecked(True)
                return
        first = next(iter(self._values), None)
        if first is not None:
            first.setChecked(True)

    # -- Binder widget protocol -------------------------------------------
    def settingValue(self):
        return self.value()

    def setSettingValue(self, value) -> None:
        self.setValue(value)

    def refresh_styles(self) -> None:
        style = Styles.get_radio_group_style()
        for radio in self._values:
            radio.setStyleSheet(style)


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
            return make_checkbox("")
        if spec.kind == "choice":
            select = make_select(CONTROL_DEFAULT)
            self._populate_select(
                select, choices or [(c.value, c.label) for c in spec.choices]
            )
            return select
        if spec.kind == "secret":
            from .modern_widgets import PasswordFieldWrapper

            wrapper = PasswordFieldWrapper()
            wrapper.setMaximumWidth(420)
            return wrapper
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
        elif spec.kind == "bool" and isinstance(widget, QCheckBox):
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


class PathField(QWidget):
    """Path input with optional Browse/Clear actions at a fixed compact width."""

    def __init__(
        self,
        placeholder: str = "",
        *,
        browse_callback=None,
        clear_callback=None,
        parent=None,
        input_width: int = CONTROL_WIDE,
    ):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.line_edit = make_line_edit(placeholder, input_width)
        self.line_edit.setMinimumWidth(min(320, input_width))
        layout.addWidget(self.line_edit, 1)

        self.browse_btn = create_icon_button(
            "Browse", "fa5s.folder-open", browse_callback, self
        )
        self.browse_btn.setMaximumWidth(120)
        self.browse_btn.setMinimumWidth(110)
        layout.addWidget(self.browse_btn)

        self.clear_btn = None
        if clear_callback is not None:
            self.clear_btn = create_icon_button(
                "Clear", "fa5s.times", clear_callback, self
            )
            self.clear_btn.setMaximumWidth(100)
            self.clear_btn.setMinimumWidth(90)
            layout.addWidget(self.clear_btn)

        layout.addStretch(1)

    def text(self) -> str:
        return self.line_edit.text()

    def setText(self, text: str) -> None:
        self.line_edit.setText(text)

    def clear(self) -> None:
        self.line_edit.clear()

    @property
    def editingFinished(self):
        return self.line_edit.editingFinished

    def setPlaceholderText(self, text: str) -> None:
        self.line_edit.setPlaceholderText(text)
