"""Single reusable input components for the whole app.

One module owns every text entry surface: :class:`Input` (single line),
:class:`TextArea` (multi line), and the numeric :class:`NumberInput` /
:class:`DecimalInput`. Call sites never ship their own field QSS; the look comes
from :meth:`Styles.get_input_qss` / :meth:`Styles.get_textarea_qss`, so theme and
accent changes repaint every field in the app automatically.

The visual language follows the app's shadcn-inspired forms: a filled resting
surface, one hairline border, an accent border on focus, a muted placeholder,
and a destructive border for invalid values. Search fields add a leading glyph
and an optional clear affordance; passwords get a trailing reveal toggle.
"""

from __future__ import annotations

from enum import StrEnum

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QColor, QIcon, QPalette
from PyQt6.QtWidgets import (
    QAbstractSpinBox,
    QDoubleSpinBox,
    QFrame,
    QLineEdit,
    QPlainTextEdit,
    QSizePolicy,
    QSpinBox,
    QTextEdit,
    QWidget,
)

from src.gui.styles import Styles
from src.gui.theme import ThemeManager

try:
    import qtawesome as qta
    HAS_QTAWESOME = True
except ImportError:
    HAS_QTAWESOME = False


# Widget classes that accept typed text; used by shortcut/navigation guards so
# they do not each re-declare the tuple.
TEXT_INPUT_TYPES = (QLineEdit, QTextEdit, QPlainTextEdit)


class InputVariant(StrEnum):
    """Resting appearance of a single-line field."""

    DEFAULT = "default"  # standard form field
    SEARCH = "search"  # filled filter bar with a leading glyph
    INLINE = "inline"  # dense field that sits beside a label


class InputSize(StrEnum):
    """Field heights mirror the Button scale so rows stay aligned."""

    SM = "sm"
    MD = "md"
    LG = "lg"


class TextAreaVariant(StrEnum):
    DEFAULT = "default"  # bordered writing surface
    CODE = "code"  # monospace (PGN, logs)
    FLAT = "flat"  # borderless read-only prose inside a card


_INPUT_SIZE_SPECS: dict[InputSize, dict[str, int]] = {
    InputSize.SM: {"height": 28, "font": 12, "padding": 8},
    InputSize.MD: {"height": 34, "font": 13, "padding": 10},
    InputSize.LG: {"height": 42, "font": 13, "padding": 12},
}

_INLINE_RADIUS = 6


class Input(QLineEdit):
    """The app's only single-line text field.

    ``icon`` accepts a qtawesome name or a ready ``QIcon`` and renders inside
    the field. ``clearable`` adds a trailing clear affordance that appears only
    while there is text; ``password`` adds a reveal toggle. ``invalid`` mirrors
    shadcn's ``aria-invalid``: use :meth:`set_invalid` instead of swapping QSS.
    """

    def __init__(
        self,
        text: str = "",
        placeholder: str = "",
        variant: InputVariant | str = InputVariant.DEFAULT,
        size: InputSize | str = InputSize.MD,
        *,
        icon: QIcon | str | None = None,
        clearable: bool = False,
        password: bool = False,
        invalid: bool = False,
        monospace: bool = False,
        full_width: bool = True,
        on_change=None,
        on_submit=None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(text, parent)
        self._variant = InputVariant(variant)
        self._size = InputSize(size)
        self._monospace = monospace
        self._clearable = clearable
        self._password = password
        self._password_visible = False
        self._invalid = invalid
        self._actions: list[QAction] = []
        self._clear_action: QAction | None = None
        self._password_action: QAction | None = None
        self._icon_spec = icon
        if icon is None and self._variant is InputVariant.SEARCH:
            self._icon_spec = "fa5s.search"

        self.setPlaceholderText(placeholder)
        if full_width:
            self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        if password:
            self.setEchoMode(QLineEdit.EchoMode.Password)
            self.setAccessibleName("Password")
        if clearable:
            self.textChanged.connect(self._sync_clear_action)

        manager = ThemeManager.instance()
        manager.theme_changed.connect(self._on_theme_changed)
        manager.accent_changed.connect(self._on_theme_changed)

        self._apply_invalid_property()
        self.refresh_styles()
        if on_change is not None:
            self.textChanged.connect(on_change)
        if on_submit is not None:
            self.returnPressed.connect(on_submit)

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------
    @property
    def variant(self) -> InputVariant:
        return self._variant

    @property
    def size(self) -> InputSize:
        return self._size

    def is_invalid(self) -> bool:
        return self._invalid

    def set_invalid(self, invalid: bool = True) -> None:
        """Flag the value as rejected; the palette supplies the destructive border."""
        if invalid == self._invalid:
            return
        self._invalid = invalid
        self._apply_invalid_property()

    def clear_invalid(self) -> None:
        self.set_invalid(False)

    def set_icon_spec(self, icon: QIcon | str | None) -> None:
        self._icon_spec = icon
        self._rebuild_actions()

    def set_size(self, size: InputSize | str) -> None:
        self._size = InputSize(size)
        self.refresh_styles()

    # ------------------------------------------------------------------
    # Styling
    # ------------------------------------------------------------------
    def refresh_styles(self) -> None:
        spec = _INPUT_SIZE_SPECS[self._size]
        self.setStyleSheet(
            Styles.get_input_qss(
                variant=self._variant.value,
                height=spec["height"],
                font_size=spec["font"],
                padding_h=spec["padding"],
                radius=_INLINE_RADIUS
                if self._variant is InputVariant.INLINE
                else 8,
                monospace=self._monospace,
            )
        )
        self._apply_placeholder_color()
        self._rebuild_actions()

    def _on_theme_changed(self, *_args) -> None:
        self.refresh_styles()

    def _apply_invalid_property(self) -> None:
        self.setProperty("invalid", "true" if self._invalid else "false")
        self.style().unpolish(self)
        self.style().polish(self)

    def _apply_placeholder_color(self) -> None:
        palette = self.palette()
        palette.setColor(
            QPalette.ColorRole.PlaceholderText, QColor(Styles.COLOR_TEXT_MUTED)
        )
        self.setPalette(palette)

    # ------------------------------------------------------------------
    # In-field affordances
    # ------------------------------------------------------------------
    def _rebuild_actions(self) -> None:
        for action in self._actions:
            self.removeAction(action)
        self._actions.clear()
        self._clear_action = None
        self._password_action = None

        if self._icon_spec is not None:
            self._make_action(
                self._icon_spec, QLineEdit.ActionPosition.LeadingPosition
            )
        if self._clearable:
            self._clear_action = self._make_action(
                "fa5s.times",
                QLineEdit.ActionPosition.TrailingPosition,
                tooltip="Clear",
                on_trigger=self.clear,
            )
            if self._clear_action is not None:
                self._clear_action.setVisible(bool(self.text()))
        if self._password:
            self._password_action = self._make_action(
                self._reveal_icon(),
                QLineEdit.ActionPosition.TrailingPosition,
                tooltip=self._reveal_tooltip(),
                on_trigger=self.toggle_password_visibility,
            )

    def _make_action(
        self,
        spec: QIcon | str,
        position: QLineEdit.ActionPosition,
        *,
        tooltip: str = "",
        on_trigger=None,
    ) -> QAction | None:
        if not HAS_QTAWESOME:
            return None
        icon = spec if isinstance(spec, QIcon) else qta.icon(
            spec, color=Styles.COLOR_TEXT_MUTED
        )
        action = QAction(icon, "", self)
        if tooltip:
            action.setToolTip(tooltip)
        if on_trigger is not None:
            action.triggered.connect(on_trigger)
        self.addAction(action, position)
        self._actions.append(action)
        return action

    def _sync_clear_action(self, text: str) -> None:
        if self._clear_action is not None:
            self._clear_action.setVisible(bool(text))

    def toggle_password_visibility(self, *_args) -> None:
        """Reveal or mask the value; the field keeps the same cursor position."""
        self._password_visible = not self._password_visible
        self.setEchoMode(
            QLineEdit.EchoMode.Normal
            if self._password_visible
            else QLineEdit.EchoMode.Password
        )
        if self._password_action is not None and HAS_QTAWESOME:
            self._password_action.setIcon(
                qta.icon(self._reveal_icon(), color=Styles.COLOR_TEXT_MUTED)
            )
            self._password_action.setToolTip(self._reveal_tooltip())

    def _reveal_icon(self) -> str:
        # "eye-slash" means "hide what is visible", matching the drawn glyph.
        return "fa5s.eye-slash" if self._password_visible else "fa5s.eye"

    def _reveal_tooltip(self) -> str:
        return "Hide password" if self._password_visible else "Show password"


class TextArea(QTextEdit):
    """The app's only multi-line text field."""

    def __init__(
        self,
        text: str = "",
        placeholder: str = "",
        variant: TextAreaVariant | str = TextAreaVariant.DEFAULT,
        *,
        min_height: int = 0,
        font_size: int | None = None,
        readonly: bool = False,
        invalid: bool = False,
        on_change=None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._variant = TextAreaVariant(variant)
        self._font_size = font_size or (
            12 if self._variant is TextAreaVariant.CODE else 13
        )
        self._invalid = invalid

        self.setAcceptRichText(False)
        # QSS draws the border; a native frame would double it.
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.setPlaceholderText(placeholder)
        self.setReadOnly(readonly)
        if readonly:
            self.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
                | Qt.TextInteractionFlag.TextSelectableByKeyboard
            )
        if min_height:
            self.setMinimumHeight(min_height)
        if text:
            self.setPlainText(text)

        manager = ThemeManager.instance()
        manager.theme_changed.connect(self._on_theme_changed)
        manager.accent_changed.connect(self._on_theme_changed)

        self.refresh_styles()
        if on_change is not None:
            self.textChanged.connect(on_change)

    @property
    def variant(self) -> TextAreaVariant:
        return self._variant

    def is_invalid(self) -> bool:
        return self._invalid

    def set_invalid(self, invalid: bool = True) -> None:
        if invalid == self._invalid:
            return
        self._invalid = invalid
        self.setProperty("invalid", "true" if invalid else "false")
        self.style().unpolish(self)
        self.style().polish(self)

    def clear_invalid(self) -> None:
        self.set_invalid(False)

    def refresh_styles(self) -> None:
        self.setStyleSheet(
            Styles.get_textarea_qss(
                variant=self._variant.value,
                font_size=self._font_size,
            )
        )
        self._apply_placeholder_color()

    def _on_theme_changed(self, *_args) -> None:
        self.refresh_styles()

    def _apply_placeholder_color(self) -> None:
        palette = self.palette()
        palette.setColor(
            QPalette.ColorRole.PlaceholderText, QColor(Styles.COLOR_TEXT_MUTED)
        )
        self.setPalette(palette)


class _NumericInputMixin:
    """Shared chrome for the spin-box editors (no duplicated styling)."""

    def _init_chrome(self, size: InputSize | str) -> None:
        self._size = InputSize(size)
        self.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        manager = ThemeManager.instance()
        manager.theme_changed.connect(self._on_theme_changed)
        manager.accent_changed.connect(self._on_theme_changed)
        self.refresh_styles()

    def _on_theme_changed(self, *_args) -> None:
        self.refresh_styles()

    def refresh_styles(self) -> None:
        spec = _INPUT_SIZE_SPECS[self._size]
        selector = "QDoubleSpinBox" if isinstance(self, QDoubleSpinBox) else "QSpinBox"
        self.setStyleSheet(
            Styles.get_input_qss(
                selector=selector,
                height=spec["height"],
                font_size=spec["font"],
                padding_h=spec["padding"],
            )
        )


class NumberInput(_NumericInputMixin, QSpinBox):
    """Integer setting field; typing, arrow keys and the wheel all still work."""

    def __init__(
        self,
        minimum: int = 0,
        maximum: int = 9999,
        step: int = 1,
        suffix: str = "",
        *,
        size: InputSize | str = InputSize.MD,
        width: int | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setRange(minimum, maximum)
        self.setSingleStep(step)
        if suffix:
            self.setSuffix(f" {suffix}")
        if width is not None:
            self.setMaximumWidth(width)
        self._init_chrome(size)


class DecimalInput(_NumericInputMixin, QDoubleSpinBox):
    """Fractional setting field (temperature, thresholds)."""

    def __init__(
        self,
        minimum: float = 0.0,
        maximum: float = 100.0,
        step: float = 0.1,
        suffix: str = "",
        decimals: int = 1,
        *,
        size: InputSize | str = InputSize.MD,
        width: int | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setRange(minimum, maximum)
        self.setSingleStep(step)
        self.setDecimals(decimals)
        if suffix:
            self.setSuffix(f" {suffix}")
        if width is not None:
            self.setMaximumWidth(width)
        self._init_chrome(size)
