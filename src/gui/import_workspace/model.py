"""Table model for the import workspace."""

from __future__ import annotations

from PyQt6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QSortFilterProxyModel,
    Qt,
    pyqtSignal,
)

from src.backend.storage.game_identity import normalize_date
from src.gui.dialogs.load_game.helpers import format_display_date

from .batch import GameCandidate

COL_CHECK = 0
COL_BOARD = 1
COL_DATE = 2
COL_WHITE = 3
COL_BLACK = 4
COL_RESULT = 5
COL_TIME = 6
COL_MOVES = 7
COL_DETAILS = 8
COL_STATUS = 9


class GameImportTableModel(QAbstractTableModel):
    """Virtualized candidate table with checkbox selection."""

    HEADERS = (
        "",
        "Board",
        "Date",
        "White",
        "Black",
        "Result",
        "Time",
        "Moves",
        "Opening / Event",
        "Status",
    )

    selection_changed = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._candidates: list[GameCandidate] = []
        self._checked: set[int] = set()

    # ------------------------------------------------------------------
    # Data API
    # ------------------------------------------------------------------
    def set_candidates(self, candidates: list[GameCandidate]) -> None:
        self.beginResetModel()
        self._candidates = list(candidates)
        self._checked.clear()
        self.endResetModel()
        self.selection_changed.emit(0)

    def candidate_at(self, row: int) -> GameCandidate | None:
        if 0 <= row < len(self._candidates):
            return self._candidates[row]
        return None

    def checked_candidates(self) -> list[GameCandidate]:
        return [c for c in self._candidates if c.candidate_id in self._checked]

    def checked_count(self) -> int:
        return len(self._checked)

    def is_checked(self, candidate_id: int) -> bool:
        return candidate_id in self._checked

    def set_checked(self, candidate_id: int, checked: bool) -> None:
        self.set_many_checked([candidate_id], checked)

    def set_many_checked(self, candidate_ids: list[int], checked: bool) -> None:
        selectable = {
            candidate.candidate_id
            for candidate in self._candidates
            if not candidate.in_history
        }
        candidate_ids = [
            candidate_id
            for candidate_id in candidate_ids
            if candidate_id in selectable
        ]
        if not candidate_ids:
            self.selection_changed.emit(self.checked_count())
            return
        if checked:
            self._checked.update(candidate_ids)
        else:
            self._checked.difference_update(candidate_ids)
        if self._candidates:
            top = self.index(0, COL_CHECK)
            bottom = self.index(len(self._candidates) - 1, COL_CHECK)
            self.dataChanged.emit(
                top, bottom, [Qt.ItemDataRole.CheckStateRole]
            )
        self.selection_changed.emit(self.checked_count())

    def all_candidate_ids(self) -> list[int]:
        return [candidate.candidate_id for candidate in self._candidates]

    def selectable_candidate_ids(self) -> list[int]:
        return [
            candidate.candidate_id
            for candidate in self._candidates
            if not candidate.in_history
        ]

    def mark_in_history(self, candidate_ids: set[int]) -> None:
        ids = set(candidate_ids)
        if not ids:
            return
        for candidate in self._candidates:
            if candidate.candidate_id in ids:
                candidate.in_history = True
        self._checked.difference_update(ids)
        if self._candidates:
            top = self.index(0, COL_STATUS)
            bottom = self.index(len(self._candidates) - 1, COL_STATUS)
            self.dataChanged.emit(top, bottom, [Qt.ItemDataRole.DisplayRole])
            check_top = self.index(0, COL_CHECK)
            check_bottom = self.index(len(self._candidates) - 1, COL_CHECK)
            self.dataChanged.emit(
                check_top, check_bottom, [Qt.ItemDataRole.CheckStateRole]
            )
        self.selection_changed.emit(self.checked_count())

    def toggle_check(self, row: int) -> None:
        candidate = self.candidate_at(row)
        if candidate is not None:
            self.set_checked(
                candidate.candidate_id,
                candidate.candidate_id not in self._checked,
            )

    # ------------------------------------------------------------------
    # Qt model interface
    # ------------------------------------------------------------------
    def rowCount(self, parent=QModelIndex()) -> int:  # noqa: N802 - Qt override
        return 0 if parent.isValid() else len(self._candidates)

    def columnCount(self, parent=QModelIndex()) -> int:  # noqa: N802 - Qt override
        return 0 if parent.isValid() else len(self.HEADERS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):  # noqa: N802
        if (
            role == Qt.ItemDataRole.DisplayRole
            and orientation == Qt.Orientation.Horizontal
            and 0 <= section < len(self.HEADERS)
        ):
            return self.HEADERS[section]
        return None

    def flags(self, index: QModelIndex):
        flags = (
            Qt.ItemFlag.ItemIsEnabled
            | Qt.ItemFlag.ItemIsSelectable
        )
        if index.column() == COL_CHECK:
            candidate = self.candidate_at(index.row())
            if candidate is not None and not candidate.in_history:
                flags |= Qt.ItemFlag.ItemIsUserCheckable
        return flags

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        candidate = self.candidate_at(index.row())
        if candidate is None:
            return None
        column = index.column()

        if role == Qt.ItemDataRole.UserRole:
            return candidate
        if role == Qt.ItemDataRole.UserRole + 1:
            return self._sort_key(candidate, column)
        if role == Qt.ItemDataRole.CheckStateRole and column == COL_CHECK:
            if candidate.in_history:
                return None
            checked = candidate.candidate_id in self._checked
            return (
                Qt.CheckState.Checked
                if checked
                else Qt.CheckState.Unchecked
            )
        if role == Qt.ItemDataRole.TextAlignmentRole:
            if column in (COL_CHECK, COL_BOARD, COL_RESULT, COL_MOVES):
                return Qt.AlignmentFlag.AlignCenter
            return Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        if role == Qt.ItemDataRole.ToolTipRole:
            if column == COL_STATUS:
                return (
                    "This game is already in your history."
                    if candidate.in_history
                    else "Not in your history yet."
                )
            if column == COL_WHITE:
                return candidate.white
            if column == COL_BLACK:
                return candidate.black
            if column == COL_DETAILS:
                return candidate.opening or candidate.event or None
            return None
        if role != Qt.ItemDataRole.DisplayRole:
            return None

        if column in (COL_CHECK, COL_BOARD):
            return ""
        if column == COL_DATE:
            return format_display_date(candidate.date)
        if column == COL_WHITE:
            return candidate.white or "?"
        if column == COL_BLACK:
            return candidate.black or "?"
        if column == COL_RESULT:
            return candidate.result or "*"
        if column == COL_TIME:
            return candidate.time_class or "Unknown"
        if column == COL_MOVES:
            return (
                str(candidate.move_count)
                if candidate.move_count is not None
                else "—"
            )
        if column == COL_DETAILS:
            return candidate.opening or candidate.event or "—"
        if column == COL_STATUS:
            return "Saved" if candidate.in_history else "New"
        return None

    def setData(self, index, value, role=Qt.ItemDataRole.EditRole):  # noqa: N802
        if (
            index.isValid()
            and index.column() == COL_CHECK
            and role == Qt.ItemDataRole.CheckStateRole
        ):
            candidate = self.candidate_at(index.row())
            if candidate is not None:
                checked_value = getattr(value, "value", value)
                self.set_checked(
                    candidate.candidate_id,
                    int(checked_value) == Qt.CheckState.Checked.value,
                )
                return True
        return False

    @staticmethod
    def _sort_key(candidate: GameCandidate, column: int):
        if column == COL_DATE:
            date = (candidate.date or "").strip()
            if date.startswith("?"):
                return "9999.99.99"
            return normalize_date(date)
        if column == COL_WHITE:
            return (candidate.white or "").casefold()
        if column == COL_BLACK:
            return (candidate.black or "").casefold()
        if column == COL_RESULT:
            return candidate.result or ""
        if column == COL_TIME:
            return (candidate.time_class or "").casefold()
        if column == COL_MOVES:
            return candidate.move_count if candidate.move_count is not None else -1
        if column == COL_DETAILS:
            return (candidate.opening or candidate.event or "").casefold()
        if column == COL_STATUS:
            return 0 if candidate.in_history else 1
        return ""


class GameImportFilterProxy(QSortFilterProxyModel):
    """Search and filter the candidate table without touching the source rows."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tokens: list[str] = []
        self._result = "all"
        self._time_class = "all"
        self._history = "all"

    def set_filters(
        self,
        *,
        search: str = "",
        result: str = "all",
        time_class: str = "all",
        history: str = "all",
    ) -> None:
        self._tokens = [token for token in search.casefold().split() if token]
        self._result = result
        self._time_class = time_class
        self._history = history
        self.invalidateFilter()

    def set_search(self, text: str) -> None:
        self.set_filters(search=text, result=self._result,
                         time_class=self._time_class, history=self._history)

    def set_result(self, value: str) -> None:
        self.set_filters(search=" ".join(self._tokens), result=value,
                         time_class=self._time_class, history=self._history)

    def set_time_class(self, value: str) -> None:
        self.set_filters(search=" ".join(self._tokens), result=self._result,
                         time_class=value, history=self._history)

    def set_history(self, value: str) -> None:
        self.set_filters(search=" ".join(self._tokens), result=self._result,
                         time_class=self._time_class, history=value)

    def filterAcceptsRow(self, source_row, source_parent):  # noqa: N802
        model = self.sourceModel()
        candidate = model.candidate_at(source_row)
        if candidate is None:
            return False
        if self._tokens and not all(
            token in candidate.search_blob for token in self._tokens
        ):
            return False
        if self._result != "all" and candidate.result != self._result:
            return False
        if (
            self._time_class != "all"
            and (candidate.time_class or "Unknown") != self._time_class
        ):
            return False
        if self._history == "saved":
            return candidate.in_history
        if self._history == "new":
            return not candidate.in_history
        return True
