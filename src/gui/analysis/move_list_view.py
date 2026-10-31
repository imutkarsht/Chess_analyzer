"""Shared move-list table used by the Analysis and Explorer pages.

The two pages render different cell styles, but the table shell, row/column
mapping, selection, click routing and list lifecycle are identical. This
component owns that machinery and switches rendering modes so each page keeps
its existing look.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from PyQt6 import sip
from PyQt6.QtCore import QEvent, QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QIcon, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.gui.analysis.move_cell_widget import MoveCellWidget
from src.gui.styles import Styles
from src.utils.resources import ResourceManager


@dataclass(frozen=True, slots=True)
class MoveListEntry:
    """Display model shared by both move lists."""

    san: str
    classification: str | None = None
    move_number: int | None = None
    time_spent: float | None = None
    variation_count: int = 0


class MoveListView(QWidget):
    """Move table with an ``analysis`` (rich) and ``explorer`` (plain) mode."""

    move_selected = pyqtSignal(int)
    variation_requested = pyqtSignal(int)
    state_changed = pyqtSignal(int, int)  # current index, total moves

    def __init__(
        self,
        variant: str = "analysis",
        parent: QWidget | None = None,
        *,
        forward_navigation_keys: bool | None = None,
    ):
        super().__init__(parent)
        if variant not in {"analysis", "explorer"}:
            raise ValueError(f"Unknown move-list variant: {variant}")

        self.variant = variant
        self._rich = variant == "analysis"
        self._forward_navigation_keys = (
            self._rich if forward_navigation_keys is None else forward_navigation_keys
        )
        self.resource_manager = ResourceManager()
        self.entries: list[MoveListEntry] = []
        self.current_index = -1
        self.move_widgets: dict[int, MoveCellWidget] = {}
        self.think_bars: list[MoveCellWidget] = []
        self._max_seconds = 30.0
        self._variation_counts: dict[int, int] = {}

        layout = QVBoxLayout(self)
        if self._rich:
            layout.setContentsMargins(5, 5, 5, 5)
        else:
            layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.table = self._build_table()
        self.card: QFrame | None = None
        if self._rich:
            self.card = QFrame()
            self.card.setObjectName("MoveListCard")
            self.card.setFrameShape(QFrame.Shape.NoFrame)
            card_layout = QVBoxLayout(self.card)
            card_layout.setContentsMargins(0, 0, 0, 0)
            card_layout.setSpacing(0)
            card_layout.addWidget(self.table)
            layout.addWidget(self.card)
        else:
            layout.addWidget(self.table)

        if self._forward_navigation_keys:
            self.table.installEventFilter(self)

        self.refresh_styles()

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def _build_table(self) -> QTableWidget:
        table = QTableWidget()
        table.setColumnCount(3)
        table.setHorizontalHeaderLabels(["#", "White", "Black"])
        table.horizontalHeader().setHighlightSections(False)
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(False)
        table.setShowGrid(False)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.cellClicked.connect(self._on_table_clicked)

        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)

        if self._rich:
            header.resizeSection(0, 44)
            header.setMinimumHeight(34)
            header.setIconSize(QSize(9, 9))
            header.setDefaultAlignment(
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
            )
            table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            table.setFrameShape(QFrame.Shape.NoFrame)
            table.setWordWrap(False)
            table.setIconSize(QSize(20, 20))
            table.verticalHeader().setDefaultSectionSize(40)
            header.sectionResized.connect(self._on_section_resized)
        else:
            header.resizeSection(0, 46)
            header.setMinimumHeight(30)
            header.setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setIconSize(QSize(16, 16))
            table.verticalHeader().setDefaultSectionSize(36)

        return table

    # ------------------------------------------------------------------
    # Public list API
    # ------------------------------------------------------------------

    def set_entries(
        self, entries: list[MoveListEntry], *, max_seconds: float = 30.0
    ) -> None:
        self.entries = list(entries)
        self._max_seconds = max_seconds
        if self.current_index >= len(self.entries):
            self.current_index = len(self.entries) - 1
        self._render()

    def append_entry(self, entry: MoveListEntry) -> None:
        if self.current_index < len(self.entries) - 1:
            del self.entries[self.current_index + 1 :]
        self.entries.append(entry)
        self.current_index = len(self.entries) - 1
        self._render()

    def update_entry(
        self,
        index: int,
        *,
        classification: str | None = None,
        time_spent: float | None = None,
        variation_count: int | None = None,
    ) -> None:
        if not 0 <= index < len(self.entries):
            return
        changes: dict = {}
        if classification is not None:
            changes["classification"] = classification
        if time_spent is not None:
            changes["time_spent"] = time_spent
        if variation_count is not None:
            changes["variation_count"] = variation_count
        if not changes:
            return
        self.entries[index] = replace(self.entries[index], **changes)
        if self._rich:
            self._update_rich_cell(index)
            self._apply_selection()
        else:
            self._render_plain()
            self._apply_selection()
        self._notify_state()

    def set_classification(self, index: int, classification: str | None) -> None:
        if not 0 <= index < len(self.entries):
            return
        self.entries[index] = replace(
            self.entries[index], classification=classification
        )
        if self._rich:
            self._update_rich_cell(index)
            self._apply_selection()
        else:
            self._render_plain()
            self._apply_selection()
        self._notify_state()

    def set_pending(self, index: int, pending: bool = True) -> None:
        self.set_classification(index, "Pending" if pending else None)

    def set_variation_counts(self, counts: dict[int, int]) -> None:
        self._variation_counts = {
            int(index): int(count) for index, count in counts.items() if count > 0
        }
        for index, entry in enumerate(self.entries):
            desired = self._variation_counts.get(index, 0)
            if entry.variation_count != desired:
                self.entries[index] = replace(entry, variation_count=desired)
        for index, widget in self._live_move_widgets():
            if sip.isdeleted(widget):
                continue
            widget.set_variation_count(self._variation_counts.get(index, 0))
        self._notify_state()

    def set_current_index(self, index: int) -> None:
        if not -1 <= index < len(self.entries):
            return
        self.current_index = index
        self._apply_selection()
        self._notify_state()

    def clear_entries(self) -> None:
        self.entries = []
        self.current_index = -1
        self._variation_counts = {}
        self._reset_table()
        self._notify_state()

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def _render(self) -> None:
        if self._rich:
            self._render_rich()
        else:
            self._render_plain()
        self._apply_selection()
        self._notify_state()

    def _reset_table(self) -> None:
        if self._rich:
            self._clear_cell_widgets()
        self.table.clearContents()
        self.table.setRowCount(0)

    def _render_plain(self) -> None:
        self._reset_table()
        self.table.setRowCount((len(self.entries) + 1) // 2)

        for index, entry in enumerate(self.entries):
            row, column = self._row_column(index)
            if column == 1:
                number = QTableWidgetItem(str(row + 1))
                number.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                number.setFlags(Qt.ItemFlag.ItemIsEnabled)
                number.setForeground(
                    QBrush(QColor(Styles.COLOR_TEXT_SECONDARY))
                )
                self.table.setItem(row, 0, number)

            item = QTableWidgetItem(self._plain_text(entry))
            item.setTextAlignment(
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
            )
            item.setData(Qt.ItemDataRole.UserRole, index)
            self._style_plain_item(item, entry)
            self.table.setItem(row, column, item)

    def _render_rich(self) -> None:
        self._reset_table()
        self.table.setRowCount((len(self.entries) + 1) // 2)

        for index, entry in enumerate(self.entries):
            row, column = self._row_column(index)
            if column == 1:
                number = QTableWidgetItem(
                    str(entry.move_number if entry.move_number else row + 1)
                )
                number.setTextAlignment(
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
                )
                number.setFlags(Qt.ItemFlag.ItemIsEnabled)
                number.setForeground(
                    QBrush(QColor(Styles.COLOR_TEXT_SECONDARY))
                )
                self.table.setItem(row, 0, number)

            cell = self._make_rich_cell(entry, index)
            self.think_bars.append(cell)
            self.move_widgets[index] = cell

            item = QTableWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, index)
            item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            item.setSizeHint(QSize(120, 38))
            self.table.setItem(row, column, item)
            self.table.setCellWidget(row, column, cell)

        QTimer.singleShot(0, self.update_compact_mode)

    def _make_rich_cell(self, entry: MoveListEntry, index: int) -> MoveCellWidget:
        cell = MoveCellWidget(parent=self.table)
        cell.set_entry(
            entry,
            index,
            icon=self._icon_for(entry),
            max_seconds=self._max_seconds,
            variation_count=entry.variation_count,
        )
        cell.clicked.connect(self._on_cell_clicked)
        cell.variation_clicked.connect(self.variation_requested.emit)
        return cell

    def _update_rich_cell(self, index: int) -> None:
        widget = self.move_widgets.get(index)
        if widget is None or sip.isdeleted(widget):
            self.move_widgets.pop(index, None)
            return
        entry = self.entries[index]
        widget.set_entry(
            entry,
            index,
            icon=self._icon_for(entry),
            max_seconds=self._max_seconds,
            variation_count=entry.variation_count,
        )

    @staticmethod
    def _plain_text(entry: MoveListEntry) -> str:
        if entry.classification == "Pending":
            return f"~ {entry.san} ~"
        return entry.san

    def _style_plain_item(self, item: QTableWidgetItem, entry: MoveListEntry) -> None:
        classification = entry.classification
        if classification == "Pending":
            item.setForeground(QBrush(QColor(Styles.COLOR_TEXT_MUTED)))
            return
        if classification:
            icon = self.resource_manager.get_icon(classification)
            if not icon.isNull():
                item.setIcon(icon)
            color_hex = Styles.get_class_color(classification)
            if color_hex:
                item.setForeground(QBrush(QColor(color_hex)))
            if classification in {"Brilliant", "Blunder", "Mistake", "Miss"}:
                font = item.font()
                font.setBold(True)
                item.setFont(font)
            return
        item.setForeground(QBrush(QColor(Styles.COLOR_TEXT_PRIMARY)))

    def _icon_for(self, entry: MoveListEntry) -> QIcon | None:
        if not entry.classification or entry.classification == "Pending":
            return None
        return self.resource_manager.get_icon(entry.classification)

    # ------------------------------------------------------------------
    # Selection / navigation state
    # ------------------------------------------------------------------

    def _apply_selection(self) -> None:
        self.table.clearSelection()
        if self.current_index < 0:
            if self._rich:
                for _index, widget in self._live_move_widgets():
                    widget.set_state(selected=False, row_active=False)
            return

        row, column = self._row_column(self.current_index)
        self.table.setCurrentCell(row, column)
        item = self.table.item(row, column)
        if item is not None:
            self.table.scrollToItem(item)

        if self._rich:
            active_row = self.current_index // 2
            for index, widget in self._live_move_widgets():
                widget.set_state(
                    selected=index == self.current_index,
                    row_active=index // 2 == active_row,
                )

    def _notify_state(self) -> None:
        self.state_changed.emit(self.current_index, len(self.entries))

    @staticmethod
    def _row_column(index: int) -> tuple[int, int]:
        return index // 2, (index % 2) + 1

    # ------------------------------------------------------------------
    # Clicks and keyboard forwarding
    # ------------------------------------------------------------------

    def _on_cell_clicked(self, index: int) -> None:
        if 0 <= index < len(self.entries):
            self.move_selected.emit(index)

    def _on_table_clicked(self, row: int, column: int) -> None:
        if column == 0:
            index = row * 2
        else:
            item = self.table.item(row, column)
            index = item.data(Qt.ItemDataRole.UserRole) if item else None
        if index is None or not 0 <= index < len(self.entries):
            return
        if not self._rich and index == self.current_index:
            return
        self.move_selected.emit(index)

    def eventFilter(self, source, event):
        nav_keys = {
            Qt.Key.Key_Left,
            Qt.Key.Key_Right,
            Qt.Key.Key_Up,
            Qt.Key.Key_Down,
            Qt.Key.Key_Home,
            Qt.Key.Key_End,
        }
        if (
            source is self.table
            and event.type() == QEvent.Type.KeyPress
            and event.key() in nav_keys
        ):
            parent = self.parent()
            while parent is not None:
                from PyQt6.QtWidgets import QMainWindow

                if isinstance(parent, QMainWindow):
                    parent.keyPressEvent(event)
                    return True
                parent = parent.parent()
        return super().eventFilter(source, event)

    # ------------------------------------------------------------------
    # Compact mode / cell-widget lifecycle
    # ------------------------------------------------------------------

    def update_compact_mode(self) -> None:
        if not self._rich:
            return
        widgets = self._live_move_widgets()
        if not widgets:
            return
        compact = self.table.columnWidth(1) < 100
        for _index, widget in widgets:
            widget.set_compact(compact)

    def _on_section_resized(self, *_args) -> None:
        self.update_compact_mode()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_compact_mode()

    def showEvent(self, event):
        super().showEvent(event)
        if self._rich:
            QTimer.singleShot(0, self.update_compact_mode)

    def _clear_cell_widgets(self) -> None:
        for widget in self.think_bars:
            if sip.isdeleted(widget):
                continue
            widget.setParent(None)
            widget.deleteLater()
        self.think_bars.clear()
        self.move_widgets.clear()

    def _live_move_widgets(self) -> list[tuple[int, MoveCellWidget]]:
        live: list[tuple[int, MoveCellWidget]] = []
        for index, widget in list(self.move_widgets.items()):
            if sip.isdeleted(widget):
                self.move_widgets.pop(index, None)
                continue
            live.append((index, widget))
        return live

    # ------------------------------------------------------------------
    # Theme
    # ------------------------------------------------------------------

    def refresh_styles(self) -> None:
        if self._rich:
            self.setStyleSheet(Styles.get_background_style())
            if self.card is not None:
                self.card.setStyleSheet(Styles.get_move_list_card_style())
            self.table.setStyleSheet(Styles.get_move_list_table_style())
            self._setup_header()
            secondary = QColor(Styles.COLOR_TEXT_SECONDARY)
            for row in range(self.table.rowCount()):
                item = self.table.item(row, 0)
                if item:
                    item.setForeground(QBrush(secondary))
            for _index, cell in self._live_move_widgets():
                cell.refresh_styles()
            self._apply_selection()
            return

        self.table.setStyleSheet(Styles.get_explorer_table_style())
        self._render_plain()
        self._apply_selection()

    def _setup_header(self) -> None:
        header = self.table.horizontalHeader()
        header.setIconSize(QSize(9, 9))
        white_item = self.table.horizontalHeaderItem(1)
        black_item = self.table.horizontalHeaderItem(2)
        if white_item is not None:
            white_item.setIcon(self._header_dot(Styles.COLOR_PIECE_WHITE))
        if black_item is not None:
            black_item.setIcon(self._header_dot(Styles.COLOR_PIECE_BLACK))

    @staticmethod
    def _header_dot(color: str) -> QIcon:
        size = 10
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor(Styles.COLOR_BORDER_LIGHT), 1))
        painter.setBrush(QColor(color))
        painter.drawEllipse(1, 1, size - 2, size - 2)
        painter.end()
        return QIcon(pixmap)
