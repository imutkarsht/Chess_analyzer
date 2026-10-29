"""Single source of truth for dropdown / select controls.

``Select`` is a custom-painted dropdown: no ``QComboBox`` styling, popup
delegate, or per-widget stylesheet exists anywhere else in the app. Every
dropdown derives its look, options, geometry, keyboard/mouse behaviour, and
signals from this module.

Theme colours always come from :class:`Styles`, so light/dark and accent
changes are picked up by ``refresh_styles``.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from PyQt6.QtCore import QPoint, QRectF, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QFontMetrics, QGuiApplication, QPainter, QPen
from PyQt6.QtWidgets import (
    QFrame,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.gui.styles import Styles
from src.gui.theme import ThemeManager
from src.gui.utils.smooth_scroll import SmoothScroll

_UNSET = object()


class SelectSize(StrEnum):
    """Trigger/row sizing presets."""

    SM = "sm"
    MD = "md"
    LG = "lg"


# height, font pixel size, row height, horizontal padding, corner radius
_SIZE_SPECS: dict[SelectSize, tuple[int, int, int, int, int]] = {
    SelectSize.SM: (30, 12, 28, 10, 9),
    SelectSize.MD: (36, 13, 34, 12, 11),
    SelectSize.LG: (44, 14, 40, 14, 12),
}


@dataclass(frozen=True)
class SelectOption:
    """One dropdown choice. ``value`` defaults to ``label`` when omitted."""

    label: str
    value: Any = _UNSET

    @property
    def data(self) -> Any:
        return self.label if self.value is _UNSET else self.value


def _values_equal(first: Any, second: Any) -> bool:
    try:
        return bool(first == second)
    except Exception:
        return first is second


class _SelectRow(QWidget):
    """One painted popup row with hover, selection fill, and check mark."""

    activated = pyqtSignal(int)

    def __init__(
        self,
        index: int,
        option: SelectOption,
        *,
        selected: bool,
        row_height: int,
        font_size: int,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._index = index
        self._option = option
        self._selected = selected
        self._highlighted = False
        self._font_size = font_size
        self._hover = False
        self.setFixedHeight(row_height)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        font = QFont(self.font())
        font.setPixelSize(font_size)
        self.setFont(font)
        self.setToolTip(option.label)

    @property
    def index(self) -> int:
        return self._index

    def set_selected(self, selected: bool) -> None:
        if self._selected != selected:
            self._selected = selected
            self.update()
        if self._selected != selected:
            self._selected = selected
            self.update()

    def set_highlighted(self, highlighted: bool) -> None:
        if self._highlighted != highlighted:
            self._highlighted = highlighted
            self.update()

    def enterEvent(self, event) -> None:
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(
            event.position().toPoint()
        ):
            self.activated.emit(self._index)
        super().mouseReleaseEvent(event)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        rect = QRectF(self.rect()).adjusted(2, 1, -2, -1)
        if self._selected:
            painter.setPen(QPen(QColor(Styles.COLOR_BORDER), 1.0))
            painter.setBrush(QColor(Styles.COLOR_SURFACE_LIGHT))
            painter.drawRoundedRect(rect, 8, 8)
        elif self._highlighted or self._hover:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(Styles.COLOR_HIGHLIGHT))
            painter.drawRoundedRect(rect, 8, 8)

        text_color = QColor(Styles.COLOR_TEXT_PRIMARY)
        painter.setPen(text_color)
        metrics = QFontMetrics(self.font())
        right_pad = 34 if self._selected else 12
        text_rect = QRectF(
            rect.left() + 12,
            rect.top(),
            max(0.0, rect.width() - 12 - right_pad),
            rect.height(),
        )
        text = metrics.elidedText(
            self._option.label, Qt.TextElideMode.ElideRight, int(text_rect.width())
        )
        painter.drawText(
            text_rect,
            int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
            text,
        )

        if self._selected:
            cx = rect.right() - 16
            cy = rect.center().y()
            pen = QPen(text_color, 2.0)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawLine(
                QPoint(int(cx - 5), int(cy)), QPoint(int(cx - 1), int(cy + 4))
            )
            painter.drawLine(
                QPoint(int(cx - 1), int(cy + 4)), QPoint(int(cx + 6), int(cy - 4))
            )


class _SelectPopup(QFrame):
    """Floating popup list owned by a :class:`Select`."""

    option_activated = pyqtSignal(int)
    dismissed = pyqtSignal()

    def __init__(self) -> None:
        super().__init__(None, Qt.WindowType.Popup)
        self.setObjectName("SelectPopup")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(0)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.viewport().setAutoFillBackground(False)

        self._content = QWidget()
        self._content.setObjectName("SelectPopupContent")
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(2)
        self._scroll.setWidget(self._content)
        layout.addWidget(self._scroll)

        self._rows: list[_SelectRow] = []
        self._highlight = 0

    @property
    def rows(self) -> list[_SelectRow]:
        return list(self._rows)

    def rebuild(
        self,
        options: Sequence[SelectOption],
        selected_index: int,
        *,
        row_height: int,
        font_size: int,
        placeholder: SelectOption | None = None,
    ) -> None:
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()
        self._rows.clear()

        entries: list[tuple[int, SelectOption]] = []
        if placeholder is not None:
            entries.append((-1, placeholder))
        entries.extend(enumerate(options))

        for index, option in entries:
            row = _SelectRow(
                index,
                option,
                selected=index == selected_index,
                row_height=row_height,
                font_size=font_size,
            )
            row.activated.connect(self._on_row_activated)
            self._content_layout.addWidget(row)
            self._rows.append(row)

    def set_selection(self, selected_index: int) -> None:
        for row in self._rows:
            row.set_selected(row.index == selected_index)

    def highlight_index(self, selected_index: int) -> None:
        """Highlight the row for an option index (-1 = placeholder)."""
        position = next(
            (pos for pos, row in enumerate(self._rows) if row.index == selected_index),
            0,
        )
        self.set_highlight(position)

    def set_highlight(self, index: int) -> bool:
        if not self._rows:
            return False
        index = max(0, min(int(index), len(self._rows) - 1))
        changed = index != self._highlight
        self._highlight = index
        for row_index, row in enumerate(self._rows):
            row.set_highlighted(row_index == index)
        self._scroll.ensureWidgetVisible(self._rows[index], 0, 0)
        return changed

    def highlight(self) -> int:
        return self._highlight

    def _on_row_activated(self, index: int) -> None:
        self.option_activated.emit(index)

    def keyPressEvent(self, event) -> None:
        key = event.key()
        if key == Qt.Key.Key_Down:
            self.set_highlight(self._highlight + 1)
            event.accept()
            return
        if key == Qt.Key.Key_Up:
            self.set_highlight(self._highlight - 1)
            event.accept()
            return
        if key == Qt.Key.Key_Home:
            self.set_highlight(0)
            event.accept()
            return
        if key == Qt.Key.Key_End:
            self.set_highlight(len(self._rows) - 1)
            event.accept()
            return
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.option_activated.emit(self._rows[self._highlight].index)
            event.accept()
            return
        if key in (Qt.Key.Key_Escape, Qt.Key.Key_Tab, Qt.Key.Key_Backtab):
            self.dismissed.emit()
            event.accept()
            return
        super().keyPressEvent(event)

    def refresh_styles(self) -> None:
        self.setStyleSheet(Styles.get_select_popup_style())
        for row in self._rows:
            row.update()

    def paintEvent(self, event) -> None:
        """Draw the floating panel itself (translucent window, rounded edges)."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        painter.setBrush(QColor(Styles.COLOR_SURFACE))
        painter.setPen(QPen(QColor(Styles.COLOR_BORDER), 1.0))
        painter.drawRoundedRect(rect, 12, 12)


class Select(QWidget):
    """The app's only dropdown widget.

    Parameters
    ----------
    options:
        ``SelectOption`` instances, ``(label, value)`` tuples, or plain
        strings (value == label).
    value:
        Initial value. Omit to select the first option, unless a placeholder
        is supplied (then nothing is selected).
    on_change:
        Convenience callback connected to ``valueChanged``.
    """

    currentIndexChanged = pyqtSignal(int)
    currentTextChanged = pyqtSignal(str)
    valueChanged = pyqtSignal(object)
    activated = pyqtSignal(int)
    editingFinished = pyqtSignal()
    popupOpened = pyqtSignal()
    popupClosed = pyqtSignal()

    def __init__(
        self,
        options: Sequence[SelectOption | tuple[str, Any] | str] | None = None,
        *,
        value: Any = _UNSET,
        placeholder: str = "",
        size: SelectSize = SelectSize.MD,
        max_visible_items: int = 8,
        min_width: int = 120,
        popup_min_width: int = 0,
        placeholder_selectable: bool = True,
        allow_custom: bool = False,
        on_change: Callable[[Any], None] | None = None,
        accessible_name: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        # The closed field cycles options on a focused wheel; keep that intent
        # instead of letting the app-wide router scroll the page under it.
        SmoothScroll.disable(self)
        self._size = SelectSize(size)
        self._options: list[SelectOption] = [
            self._coerce_option(option) for option in (options or [])
        ]
        self._placeholder = placeholder
        self._placeholder_selectable = placeholder_selectable
        self._max_visible_items = max(1, int(max_visible_items))
        self._popup_min_width = max(0, int(popup_min_width))
        self._allow_custom = allow_custom
        self._index = -1
        self._popup: _SelectPopup | None = None
        self._popup_open = False

        self.setMinimumWidth(min_width)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.setMouseTracking(True)

        if self._options and not self._placeholder:
            self._index = 0

        if value is not _UNSET:
            self._index = self.find_value(value)
            if self._index < 0 and self._options:
                self._index = 0

        if accessible_name:
            self.setAccessibleName(accessible_name)

        if on_change is not None:
            self.valueChanged.connect(on_change)

        manager = ThemeManager.instance()
        manager.theme_changed.connect(self._on_theme_changed)
        manager.accent_changed.connect(self._on_theme_changed)

    # ------------------------------------------------------------------
    # Option construction / convenience
    # ------------------------------------------------------------------
    @staticmethod
    def _coerce_option(option: SelectOption | tuple[str, Any] | str) -> SelectOption:
        if isinstance(option, SelectOption):
            return option
        if isinstance(option, tuple):
            label, value = option
            return SelectOption(str(label), value)
        return SelectOption(str(option))

    def set_options(
        self,
        options: Sequence[SelectOption | tuple[str, Any] | str],
        *,
        preserve_value: bool = True,
        emit: bool = False,
    ) -> None:
        previous = self._snapshot()
        old_value = self._value_at(self._index) if preserve_value else _UNSET
        self._options = [self._coerce_option(option) for option in options]
        if preserve_value:
            index = self.find_value(old_value) if old_value is not _UNSET else -1
        else:
            index = -1
        if index < 0:
            index = 0 if self._options else -1
        self._index = index
        self._refresh_popup()
        if emit:
            self._notify(previous)

    def add_option(
        self, option: SelectOption | tuple[str, Any] | str, *, index: int | None = None
    ) -> None:
        coerced = self._coerce_option(option)
        if index is None:
            self._options.append(coerced)
        else:
            self._options.insert(max(0, min(int(index), len(self._options))), coerced)
        if self._index < 0:
            self._index = 0
        self._refresh_popup()

    def remove_option(self, index: int) -> None:
        if not 0 <= index < len(self._options):
            return
        previous = self._snapshot()
        del self._options[index]
        if index < self._index:
            self._index -= 1
        elif index == self._index:
            self._index = min(self._index, len(self._options) - 1)
        self._refresh_popup()
        self._notify(previous)

    # ------------------------------------------------------------------
    # Selection
    # ------------------------------------------------------------------
    def count(self) -> int:
        return len(self._options)

    def options(self) -> list[SelectOption]:
        return list(self._options)

    def current_index(self) -> int:
        return self._index

    def current_text(self) -> str:
        option = self._option_at(self._index)
        return option.label if option is not None else ""

    def current_value(self) -> Any:
        return self._value_at(self._index)

    def currentIndex(self) -> int:  # noqa: N802 - QComboBox compatibility
        return self._index

    def currentText(self) -> str:  # noqa: N802 - QComboBox compatibility
        return self.current_text()

    def currentData(self) -> Any:  # noqa: N802 - QComboBox compatibility
        return self.current_value()

    def set_current_index(self, index: int, *, emit: bool = True) -> None:
        target = max(-1, min(int(index), len(self._options) - 1))
        if target == self._index:
            return
        previous = self._snapshot()
        self._index = target
        self._refresh_popup()
        self.update()
        if emit:
            self._notify(previous)

    def setCurrentIndex(self, index: int) -> None:  # noqa: N802
        self.set_current_index(index)

    def set_current_text(self, text: str, *, add_missing: bool | None = None) -> bool:
        index = self.find_text(text)
        if index < 0:
            allowed = self._allow_custom if add_missing is None else add_missing
            if not allowed or not text:
                return False
            self.add_option(SelectOption(text))
            index = self.find_text(text)
        self.set_current_index(index)
        return True

    def setCurrentText(self, text: str) -> None:  # noqa: N802
        self.set_current_text(text)

    def set_current_value(self, value: Any, *, add_missing: bool | None = None) -> bool:
        index = self.find_value(value)
        if index < 0:
            allowed = self._allow_custom if add_missing is None else add_missing
            if not allowed or value is None:
                return False
            self.add_option(SelectOption(str(value), value))
            index = self.find_value(value)
        self.set_current_index(index)
        return True

    def find_text(self, text: str) -> int:
        for index, option in enumerate(self._options):
            if option.label == text:
                return index
        return -1

    def findText(self, text: str) -> int:  # noqa: N802
        return self.find_text(text)

    def find_value(self, value: Any) -> int:
        for index, option in enumerate(self._options):
            if _values_equal(option.data, value):
                return index
        return -1

    def findData(self, value: Any) -> int:  # noqa: N802
        return self.find_value(value)

    def findValue(self, value: Any) -> int:  # noqa: N802
        return self.find_value(value)

    def item_text(self, index: int) -> str:
        option = self._option_at(index)
        return option.label if option is not None else ""

    def itemText(self, index: int) -> str:  # noqa: N802
        return self.item_text(index)

    def item_data(self, index: int) -> Any:
        option = self._option_at(index)
        return option.data if option is not None else None

    def itemData(self, index: int) -> Any:  # noqa: N802
        return self.item_data(index)

    def settingValue(self) -> Any:  # noqa: N802 - binder protocol
        return self.current_value()

    def setting_value(self) -> Any:
        return self.current_value()

    def setSettingValue(self, value: Any) -> None:  # noqa: N802 - binder protocol
        index = self.find_value(value)
        if index < 0:
            if self._allow_custom and value is not None:
                self.add_option(SelectOption(str(value), value))
                index = self.find_value(value)
            else:
                index = 0 if self._options else -1
        self.set_current_index(index, emit=False)

    def set_setting_value(self, value: Any) -> None:
        self.setSettingValue(value)

    # ------------------------------------------------------------------
    # QComboBox-compatible mutation helpers
    # ------------------------------------------------------------------
    def addItem(self, label: str, userData: Any = _UNSET) -> None:  # noqa: N802
        value = label if userData is _UNSET else userData
        self.add_option(SelectOption(str(label), value))

    def addItems(self, labels: Sequence[str]) -> None:  # noqa: N802
        for label in labels:
            self._options.append(SelectOption(str(label)))
        if self._index < 0 and self._options:
            self._index = 0
        self._refresh_popup()

    def insertItem(  # noqa: N802
        self, index: int, label: str, userData: Any = _UNSET
    ) -> None:
        value = label if userData is _UNSET else userData
        self.add_option(SelectOption(str(label), value), index=index)

    def removeItem(self, index: int) -> None:  # noqa: N802
        self.remove_option(index)

    def set_item_text(self, index: int, text: str) -> None:
        option = self._option_at(index)
        if option is None:
            return
        previous = self._snapshot()
        self._options[index] = SelectOption(str(text), option.data)
        self._refresh_popup()
        self.update()
        self._notify(previous)

    def setItemText(self, index: int, text: str) -> None:  # noqa: N802
        self.set_item_text(index, text)

    def set_item_data(self, index: int, value: Any) -> None:
        option = self._option_at(index)
        if option is None:
            return
        previous = self._snapshot()
        self._options[index] = SelectOption(option.label, value)
        self._refresh_popup()
        self.update()
        self._notify(previous)

    def setItemData(self, index: int, value: Any) -> None:  # noqa: N802
        self.set_item_data(index, value)

    def clear(self) -> None:
        previous = self._snapshot()
        self._options.clear()
        self._index = -1
        self._refresh_popup()
        self.update()
        self._notify(previous)

    def text(self) -> str:
        return self.current_text()

    def setText(self, value: str) -> None:  # noqa: N802
        self.set_current_text(value, add_missing=self._allow_custom)

    # ------------------------------------------------------------------
    # Popup lifecycle
    # ------------------------------------------------------------------
    def is_open(self) -> bool:
        return self._popup_open

    def showPopup(self) -> None:  # noqa: N802 - QComboBox compatibility
        if self._popup_open or not self._options or not self.isEnabled():
            return

        popup = self._ensure_popup()
        popup.rebuild(
            self._options,
            self._index,
            row_height=_SIZE_SPECS[self._size][2],
            font_size=_SIZE_SPECS[self._size][1],
            placeholder=self._placeholder_option(),
        )
        popup.highlight_index(self._index)

        width, height = self._popup_geometry()
        popup.resize(width, height)
        popup.move(self._popup_position(width, height))
        popup.show()
        popup.raise_()
        popup.setFocus(Qt.FocusReason.PopupFocusReason)
        self._popup_open = True
        self.update()
        self.popupOpened.emit()

    def hidePopup(self) -> None:  # noqa: N802 - QComboBox compatibility
        if not self._popup_open:
            return
        self._popup_open = False
        if self._popup is not None:
            self._popup.hide()
        self.update()
        self.popupClosed.emit()
        if self.isVisible():
            self.setFocus(Qt.FocusReason.OtherFocusReason)

    def toggle_popup(self) -> None:
        self.hidePopup() if self._popup_open else self.showPopup()

    def _ensure_popup(self) -> _SelectPopup:
        if self._popup is None:
            self._popup = _SelectPopup()
            self._popup.setStyleSheet(Styles.get_select_popup_style())
            self._popup.option_activated.connect(self._on_popup_selected)
            self._popup.dismissed.connect(self.hidePopup)
        return self._popup

    def _on_popup_selected(self, index: int) -> None:
        self.hidePopup()
        self.set_current_index(index)
        self.activated.emit(index)

    def _popup_geometry(self) -> tuple[int, int]:
        row_height = _SIZE_SPECS[self._size][2]
        placeholder = self._placeholder_option()
        entry_count = len(self._options) + (1 if placeholder is not None else 0)
        visible = min(entry_count, self._max_visible_items)
        height = visible * row_height + (visible - 1) * 2 + 14
        metrics = QFontMetrics(self._trigger_font())
        labels = [option.label for option in self._options]
        if placeholder is not None:
            labels.append(placeholder.label)
        content_width = max(
            (metrics.horizontalAdvance(label) for label in labels),
            default=0,
        )
        width = max(self.width(), self._popup_min_width, content_width + 52)
        screen = self._screen()
        if screen is not None:
            width = min(width, max(160, screen.availableGeometry().width() - 16))
        return width, height

    def _popup_position(self, width: int, height: int) -> QPoint:
        anchor = self.mapToGlobal(QPoint(0, self.height() + 6))
        above = self.mapToGlobal(QPoint(0, -height - 6))
        screen = self._screen()
        if screen is not None:
            available = screen.availableGeometry()
            if anchor.y() + height > available.bottom():
                anchor = above
            anchor.setX(max(available.left() + 8, min(anchor.x(), available.right() - width - 8)))
            anchor.setY(max(available.top() + 8, anchor.y()))
        return anchor

    def _screen(self):
        center = self.mapToGlobal(self.rect().center())
        return QGuiApplication.screenAt(center) or self.window().screen()

    def _refresh_popup(self) -> None:
        if self._popup is None:
            return
        if self._popup_open:
            self.hidePopup()
            self.showPopup()
        else:
            self._popup.rebuild(
                self._options,
                self._index,
                row_height=_SIZE_SPECS[self._size][2],
                font_size=_SIZE_SPECS[self._size][1],
                placeholder=self._placeholder_option(),
            )

    def _placeholder_option(self) -> SelectOption | None:
        if self._placeholder and self._placeholder_selectable:
            return SelectOption(self._placeholder, None)
        return None

    # ------------------------------------------------------------------
    # Painting / geometry
    # ------------------------------------------------------------------
    def set_size(self, size: SelectSize) -> None:
        self._size = SelectSize(size)
        self.updateGeometry()
        self.update()

    def set_size_value(self, size: SelectSize) -> None:
        self.set_size(size)

    def set_max_visible_items(self, count: int) -> None:
        self._max_visible_items = max(1, int(count))

    def set_placeholder(self, text: str, *, selectable: bool | None = None) -> None:
        self._placeholder = text
        if selectable is not None:
            self._placeholder_selectable = selectable
        if not text and self._index < 0 and self._options:
            self._index = 0
        self.update()

    def _trigger_font(self) -> QFont:
        font = QFont(self.font())
        font.setPixelSize(_SIZE_SPECS[self._size][1])
        return font

    def sizeHint(self) -> QSize:  # noqa: N802
        height, font_size, _row, padding, _radius = _SIZE_SPECS[self._size]
        metrics = QFontMetrics(self._trigger_font())
        text = self.current_text() or self._placeholder
        return QSize(max(self.minimumWidth(), metrics.horizontalAdvance(text) + 64), height)

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return QSize(80, _SIZE_SPECS[self._size][0])

    def paintEvent(self, event) -> None:
        _height, _font_size, _row, padding, radius = _SIZE_SPECS[self._size]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        focused = self.hasFocus() or self._popup_open
        hovered = self.underMouse()

        painter.setBrush(QColor(Styles.COLOR_BACKGROUND))
        if focused or hovered:
            painter.setPen(QPen(QColor(Styles.COLOR_ACCENT), 1.4))
        else:
            painter.setPen(QPen(QColor(Styles.COLOR_BORDER), 1.0))
        painter.drawRoundedRect(rect, radius, radius)

        option = self._option_at(self._index)
        if option is not None:
            text = option.label
            color = QColor(Styles.COLOR_TEXT_PRIMARY)
        else:
            text = self._placeholder
            color = QColor(Styles.COLOR_TEXT_SECONDARY)
        if not self.isEnabled():
            color = QColor(Styles.COLOR_TEXT_MUTED)

        font = self._trigger_font()
        painter.setFont(font)
        painter.setPen(color)
        metrics = QFontMetrics(font)
        text_rect = QRectF(
            rect.left() + padding,
            rect.top(),
            max(0.0, rect.width() - 2 * padding - 24),
            rect.height(),
        )
        painter.drawText(
            text_rect,
            int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
            metrics.elidedText(text, Qt.TextElideMode.ElideRight, int(text_rect.width())),
        )

        cx = rect.right() - padding - 4
        cy = rect.center().y()
        pen = QPen(QColor(Styles.COLOR_TEXT_SECONDARY), 1.8)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawLine(QPoint(int(cx - 4), int(cy - 2)), QPoint(int(cx), int(cy + 2)))
        painter.drawLine(QPoint(int(cx), int(cy + 2)), QPoint(int(cx + 4), int(cy - 2)))

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.isEnabled():
            if self._popup_open:
                self.hidePopup()
            else:
                self.setFocus(Qt.FocusReason.MouseFocusReason)
                self.showPopup()
            event.accept()
            return
        super().mousePressEvent(event)

    def wheelEvent(self, event) -> None:
        if not self.isEnabled() or not self.hasFocus() or not self._options:
            event.ignore()
            return
        step = -1 if event.angleDelta().y() > 0 else 1
        self.set_current_index(max(0, min(self._index + step, len(self._options) - 1)))
        event.accept()

    def keyPressEvent(self, event) -> None:
        key = event.key()
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space, Qt.Key.Key_Down):
            self.showPopup()
            event.accept()
            return
        if key == Qt.Key.Key_Up:
            self.showPopup()
            if self._popup is not None:
                self._popup.set_highlight((self._index if self._index >= 0 else 0) - 1)
            event.accept()
            return
        if key == Qt.Key.Key_Escape:
            self.hidePopup()
            event.accept()
            return
        text = event.text()
        if text and text.isprintable():
            self._select_prefix(text)
            event.accept()
            return
        super().keyPressEvent(event)

    def _select_prefix(self, prefix: str) -> None:
        prefix = prefix.lower()
        if not self._options:
            return
        start = self._index + 1 if self._index >= 0 else 0
        order = list(range(start, len(self._options))) + list(range(0, start))
        for index in order:
            if self._options[index].label.lower().startswith(prefix):
                self.set_current_index(index)
                return

    def focusInEvent(self, event) -> None:
        self.update()
        super().focusInEvent(event)

    def focusOutEvent(self, event) -> None:
        self.update()
        super().focusOutEvent(event)

    def hideEvent(self, event) -> None:
        self.hidePopup()
        super().hideEvent(event)

    def moveEvent(self, event) -> None:
        self.hidePopup()
        super().moveEvent(event)

    def resizeEvent(self, event) -> None:
        self.hidePopup()
        super().resizeEvent(event)

    # ------------------------------------------------------------------
    # Theme
    # ------------------------------------------------------------------
    def _on_theme_changed(self, *_args) -> None:
        self.refresh_styles()

    def refresh_styles(self) -> None:
        if self._popup is not None:
            self._popup.refresh_styles()
        self.update()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _option_at(self, index: int) -> SelectOption | None:
        if 0 <= index < len(self._options):
            return self._options[index]
        return None

    def _value_at(self, index: int) -> Any:
        option = self._option_at(index)
        return option.data if option is not None else None

    def _snapshot(self) -> tuple[int, str, Any]:
        return self._index, self.current_text(), self.current_value()

    def _notify(self, previous: tuple[int, str, Any]) -> None:
        old_index, old_text, old_value = previous
        index, text, value = self._snapshot()
        if index != old_index:
            self.currentIndexChanged.emit(index)
        if text != old_text:
            self.currentTextChanged.emit(text)
        if not _values_equal(value, old_value):
            self.valueChanged.emit(value)
        if index != old_index or not _values_equal(value, old_value):
            self.editingFinished.emit()
