"""Generic drag-and-drop sortable list for rich settings rows."""

from dataclasses import dataclass

from PyQt6.QtCore import (
    QEasingCurve,
    QMimeData,
    QPropertyAnimation,
    QSize,
    Qt,
    QTimer,
    pyqtSignal,
)
from PyQt6.QtGui import QColor, QCursor, QDrag, QFont, QPainter, QPen
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QListWidget,
    QListWidgetItem,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
)

from src.gui.styles import Styles

try:
    import qtawesome as qta

    HAS_QTAWESOME = True
except ImportError:
    HAS_QTAWESOME = False


_KEY_ROLE = Qt.ItemDataRole.UserRole
_TITLE_ROLE = Qt.ItemDataRole.UserRole + 1
_DESCRIPTION_ROLE = Qt.ItemDataRole.UserRole + 2
_ICON_ROLE = Qt.ItemDataRole.UserRole + 3
_ROW_HEIGHT = 64


@dataclass(frozen=True)
class SortableItem:
    """One row in a :class:`SortableItemList`."""

    key: str
    title: str
    description: str = ""
    icon: str = ""


class _SortableItemDelegate(QStyledItemDelegate):
    """Paint a clean row without per-row widget borders."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._icon_cache: dict[tuple[str, str], object] = {}

    def sizeHint(self, option, index):
        return QSize(0, _ROW_HEIGHT)

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index):
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        rect = option.rect.adjusted(0, 2, 0, -2)
        hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)
        background = (
            Styles.COLOR_SURFACE_LIGHT if hovered else Styles.COLOR_SURFACE_CARD
        )
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(background))
        painter.drawRoundedRect(rect, 8, 8)

        if hovered:
            pen = QPen(QColor(Styles.COLOR_ACCENT))
            pen.setWidth(1)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(rect.adjusted(0, 0, -1, -1), 8, 8)

        self._draw_handle(painter, rect, hovered)
        self._draw_icon(painter, rect, index.data(_ICON_ROLE) or "")
        self._draw_text(painter, rect, index)
        painter.restore()

    @staticmethod
    def _draw_handle(painter: QPainter, rect, hovered: bool):
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(
            QColor(Styles.COLOR_ACCENT if hovered else Styles.COLOR_TEXT_MUTED)
        )
        center_y = rect.center().y()
        for column in (0, 1):
            x = rect.left() + 18 + column * 6
            for row in (-1, 0, 1):
                painter.drawEllipse(
                    int(x),
                    int(center_y + row * 5 - 2),
                    3,
                    3,
                )

    def _draw_icon(self, painter: QPainter, rect, icon_name: str):
        if not HAS_QTAWESOME or not icon_name:
            return
        cache_key = (icon_name, Styles.COLOR_TEXT_SECONDARY)
        pixmap = self._icon_cache.get(cache_key)
        if pixmap is None:
            pixmap = qta.icon(
                icon_name, color=Styles.COLOR_TEXT_SECONDARY
            ).pixmap(16, 16)
            self._icon_cache[cache_key] = pixmap
        y = rect.center().y() - pixmap.height() // 2
        painter.drawPixmap(rect.left() + 44, y, pixmap)

    @staticmethod
    def _draw_text(painter: QPainter, rect, index):
        title = index.data(_TITLE_ROLE) or ""
        description = index.data(_DESCRIPTION_ROLE) or ""
        text_left = rect.left() + 74
        text_width = max(0, rect.right() - text_left - 16)

        title_font = QFont(painter.font())
        title_font.setPixelSize(13)
        title_font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(title_font)
        painter.setPen(QPen(QColor(Styles.COLOR_TEXT_PRIMARY)))
        title_rect = rect.adjusted(text_left - rect.left(), 10, -16, -30)
        painter.drawText(
            title_rect,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            painter.fontMetrics().elidedText(
                str(title), Qt.TextElideMode.ElideRight, text_width
            ),
        )

        desc_font = QFont(painter.font())
        desc_font.setPixelSize(11)
        desc_font.setWeight(QFont.Weight.Normal)
        painter.setFont(desc_font)
        painter.setPen(QPen(QColor(Styles.COLOR_TEXT_SECONDARY)))
        desc_rect = rect.adjusted(text_left - rect.left(), 30, -16, -8)
        painter.drawText(
            desc_rect,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            painter.fontMetrics().elidedText(
                str(description), Qt.TextElideMode.ElideRight, text_width
            ),
        )


class SortableItemList(QListWidget):
    """A reusable list whose rows can be reordered by dragging."""

    order_changed = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._drag_source_row: int | None = None
        self._drop_row: int | None = None
        self._autoscroll_delta = 0
        self._autoscroll_timer = QTimer(self)
        self._autoscroll_timer.setInterval(30)
        self._autoscroll_timer.timeout.connect(self._autoscroll_step)
        self._scroll_animation = QPropertyAnimation(
            self.verticalScrollBar(), b"value", self
        )
        self._scroll_animation.setDuration(170)
        self._scroll_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setItemDelegate(_SortableItemDelegate(self))
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(False)
        self.setDragDropOverwriteMode(False)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setUniformItemSizes(True)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setSpacing(0)
        self.setStyleSheet(
            "QListWidget { background: transparent; border: none; }"
            " QListWidget::item { background: transparent; border: none; }"
        )

    def set_items(self, items: list[SortableItem]) -> None:
        self._drag_source_row = None
        self._scroll_animation.stop()
        self.clear()
        for item in items:
            row = QListWidgetItem()
            row.setData(_KEY_ROLE, item.key)
            row.setData(_TITLE_ROLE, item.title)
            row.setData(_DESCRIPTION_ROLE, item.description)
            row.setData(_ICON_ROLE, item.icon)
            row.setFlags(
                Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsSelectable
                | Qt.ItemFlag.ItemIsDragEnabled
                | Qt.ItemFlag.ItemIsDropEnabled
            )
            self.addItem(row)

    def keys(self) -> list[str]:
        return [self.item(i).data(_KEY_ROLE) for i in range(self.count())]

    def set_order(self, keys: list[str]) -> None:
        """Reorder existing rows without recreating them."""
        rows = {}
        while self.count():
            row = self.takeItem(0)
            rows[row.data(_KEY_ROLE)] = row
        for key in keys:
            row = rows.pop(key, None)
            if row is not None:
                self.addItem(row)
        for row in rows.values():
            self.addItem(row)

    def move_item(self, source: int, destination: int) -> None:
        """Move one row, used by keyboard/accessibility actions and tests."""
        if source == destination:
            return
        row = self.takeItem(source)
        if row is None:
            return
        self.insertItem(destination, row)
        self.setCurrentItem(row)
        self.order_changed.emit(self.keys())

    def fit_to_contents(self) -> None:
        height = sum(self.sizeHintForRow(i) for i in range(self.count()))
        self.setFixedHeight(max(0, height + 2 * self.frameWidth()))

    def set_visible_rows(self, rows: int) -> None:
        """Cap the list height, scrolling internally when it grows."""
        if rows <= 0:
            self.fit_to_contents()
            return
        if self.count() > rows:
            self.setFixedHeight(rows * _ROW_HEIGHT)
        else:
            self.fit_to_contents()

    def wheelEvent(self, event) -> None:
        bar = self.verticalScrollBar()
        pixel_delta = event.pixelDelta().y()
        if pixel_delta:
            # Trackpads already provide pixel-precise deltas; don't add lag.
            self._scroll_animation.stop()
            bar.setValue(bar.value() - pixel_delta)
            event.accept()
            return

        delta = event.angleDelta().y()
        if not delta:
            super().wheelEvent(event)
            return
        step = 88 if abs(delta) >= 120 else 44
        target = bar.value() + (-step if delta > 0 else step)
        target = max(bar.minimum(), min(bar.maximum(), target))
        if target == bar.value():
            # Let the page scroll when the list is already at an edge.
            event.ignore()
            return

        self._scroll_animation.stop()
        self._scroll_animation.setStartValue(bar.value())
        self._scroll_animation.setEndValue(target)
        self._scroll_animation.start()
        event.accept()

    # ------------------------------------------------------------------
    # Drag and drop
    # ------------------------------------------------------------------
    def startDrag(self, supported_actions) -> None:
        index = self.currentIndex()
        if not index.isValid():
            return
        self._drag_source_row = index.row()
        self._scroll_animation.stop()

        drag = QDrag(self)
        mime = QMimeData()
        mime.setData("application/x-sortable-item", b"1")
        drag.setMimeData(mime)
        rect = self.visualRect(index)
        if rect.isValid():
            drag.setPixmap(self.viewport().grab(rect))
        drag.exec(Qt.DropAction.MoveAction)
        self._autoscroll_timer.stop()
        self._autoscroll_delta = 0
        self._drop_row = None
        self.viewport().update()

    def _drop_target(self, position) -> int:
        index = self.indexAt(position)
        if index.isValid():
            destination = index.row()
            if position.y() > self.visualRect(index).center().y():
                destination += 1
            return destination
        return self.count()

    def _set_autoscroll(self, y: int) -> None:
        margin = 28
        if y < margin:
            self._autoscroll_delta = -14
        elif y > self.viewport().height() - margin:
            self._autoscroll_delta = 14
        else:
            self._autoscroll_delta = 0

        if self._autoscroll_delta:
            if not self._autoscroll_timer.isActive():
                self._autoscroll_timer.start()
        else:
            self._autoscroll_timer.stop()

    def _autoscroll_step(self) -> None:
        bar = self.verticalScrollBar()
        value = max(bar.minimum(), min(bar.maximum(), bar.value() + self._autoscroll_delta))
        if value == bar.value():
            return
        bar.setValue(value)
        position = self.viewport().mapFromGlobal(QCursor.pos())
        self._drop_row = self._drop_target(position)
        self.viewport().update()

    def dragEnterEvent(self, event) -> None:
        if event.source() is self and self._drag_source_row is not None:
            position = event.position().toPoint()
            self._drop_row = self._drop_target(position)
            self._set_autoscroll(position.y())
            self.viewport().update()
            event.setDropAction(Qt.DropAction.MoveAction)
            event.accept()
            return
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event) -> None:
        if event.source() is self and self._drag_source_row is not None:
            position = event.position().toPoint()
            self._drop_row = self._drop_target(position)
            self._set_autoscroll(position.y())
            self.viewport().update()
            event.setDropAction(Qt.DropAction.MoveAction)
            event.accept()
            return
        super().dragMoveEvent(event)

    def dragLeaveEvent(self, event) -> None:
        self._autoscroll_timer.stop()
        self._autoscroll_delta = 0
        self._drop_row = None
        self.viewport().update()
        super().dragLeaveEvent(event)

    def dropEvent(self, event) -> None:
        source = self._drag_source_row
        if source is None or event.source() is not self:
            event.ignore()
            return

        destination = self._drop_target(event.position().toPoint())
        if destination > source:
            destination -= 1
        self._autoscroll_timer.stop()
        self._autoscroll_delta = 0
        self._drag_source_row = None
        self._drop_row = None
        if destination != source:
            self.move_item(source, destination)
        self.viewport().update()
        event.setDropAction(Qt.DropAction.MoveAction)
        event.accept()

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        if self._drop_row is None or not self.count():
            return

        if self._drop_row < self.count():
            rect = self.visualRect(self.model().index(self._drop_row, 0))
            y = rect.top()
        else:
            rect = self.visualRect(self.model().index(self.count() - 1, 0))
            y = rect.bottom()

        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        pen = QPen(QColor(Styles.COLOR_ACCENT))
        pen.setWidth(2)
        painter.setPen(pen)
        painter.drawLine(8, y, self.viewport().width() - 8, y)
        painter.setBrush(QColor(Styles.COLOR_ACCENT))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(5, y - 3, 6, 6)
        painter.end()
