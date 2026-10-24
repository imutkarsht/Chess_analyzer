"""Reusable settings rows and fields.

The goal is to make widths, spacing, labels, hints, and advanced visibility
live in one place instead of being reimplemented in every settings card.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

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
    ) -> QWidget:
        """Add a label/control row and return the control wrapper."""
        lbl = QLabel(label)
        lbl.setFixedWidth(self._label_width)
        lbl.setStyleSheet(
            Styles.get_label_style(size=13) + " " + Styles.get_transparent_label_style()
        )
        self._label_widgets.append(lbl)

        wrapper = QWidget()
        wrapper.setStyleSheet(Styles.get_transparent_label_style())
        box = QVBoxLayout(wrapper)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(3)

        if width is not None:
            control.setMaximumWidth(width)
        box.addWidget(control)

        if hint:
            hint_lbl = QLabel(hint)
            hint_lbl.setWordWrap(True)
            hint_lbl.setStyleSheet(
                Styles.get_secondary_label_style(size=11)
                + " "
                + Styles.get_transparent_label_style()
            )
            self._hint_widgets.append(hint_lbl)
            box.addWidget(hint_lbl)

        self.form.addRow(lbl, wrapper)
        if advanced:
            self._advanced_rows.append((lbl, wrapper))
        return wrapper

    def set_advanced_visible(self, visible: bool) -> None:
        for lbl, wrapper in self._advanced_rows:
            lbl.setVisible(visible)
            wrapper.setVisible(visible)

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


def make_combo(max_width: int = CONTROL_DEFAULT) -> QComboBox:
    combo = QComboBox()
    combo.setStyleSheet(Styles.get_combobox_style())
    combo.setMaximumWidth(max_width)
    return combo


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


def make_hint(text: str) -> QLabel:
    label = QLabel(text)
    label.setWordWrap(True)
    label.setStyleSheet(
        Styles.get_secondary_label_style(size=11)
        + " "
        + Styles.get_transparent_label_style()
    )
    return label


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

    def setPlaceholderText(self, text: str) -> None:
        self.line_edit.setPlaceholderText(text)
