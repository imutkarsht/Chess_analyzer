"""
Move List Panel - Displays the list of played moves in a paginated/tabular layout.
"""

import contextlib

import chess
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

from src.gui.analysis.line_utils import lines_for_index
from src.gui.analysis.move_cell_widget import MoveCellWidget
from src.gui.engine_lines import LiveEngineSession
from src.gui.styles import Styles
from src.utils.logger import logger
from src.utils.resources import ResourceManager


class MoveListPanel(QWidget):
    move_selected = pyqtSignal(int)
    lines_updated = pyqtSignal(list, str)  # White-POV EngineLines, analysed FEN
    variation_requested = pyqtSignal(int)

    def __init__(self, engine_path="stockfish", config_manager=None):
        super().__init__()
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(5, 5, 5, 5)
        self.layout.setSpacing(0)

        self.resource_manager = ResourceManager()
        self.current_game = None

        # Live Analysis — one shared session owns the worker, the sequence
        # counter and the coalesced line updates.  The worker is started
        # lazily on the first request, not at app launch.
        self.engine_path = engine_path
        self.session = LiveEngineSession(
            self.engine_path,
            config_manager=config_manager,
            parent=self,
            debounce_ms=1000,  # 1 second delay (more responsive than a full search)
        )
        self.session.lines_changed.connect(self._on_session_lines)

        self.engine_lines_enabled = (
            bool(config_manager.get("engine_lines_enabled", False))
            if config_manager is not None
            else False
        )
        # The move list's live engine is shared with variation exploration.
        self._analysed_fen: str | None = None
        self._variation_active = False
        self.is_chess960 = False
        self.starting_fen = chess.STARTING_FEN
        # Reusable think-time bar widgets (one per cell). We keep strong
        # references because QTableWidget.setCellWidget() does not take
        # ownership; without this, the bars would be garbage-collected
        # and the table would render empty cells.
        self._think_bars: list[MoveCellWidget] = []
        self._move_widgets: dict[int, MoveCellWidget] = {}
        self._variation_counts: dict[int, int] = {}

        # Move List Table — 3 columns: #, White, Black
        # Think-time is rendered as a thin coloured bar at the bottom of the
        # move cell itself (no separate column) so the table stays readable
        # in a narrow left-pane.
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["#", "White", "Black"])
        self.table.horizontalHeader().setHighlightSections(False)
        self.table.horizontalHeader().setMinimumHeight(34)
        self.table.horizontalHeader().setIconSize(QSize(9, 9))
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.table.setFrameShape(QFrame.Shape.NoFrame)
        self.table.setWordWrap(False)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(0, 44)  # #  — wide enough for two-digit move numbers
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(False)
        self.table.setShowGrid(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.cellClicked.connect(self.on_cell_clicked)
        self.table.horizontalHeader().sectionResized.connect(self._on_section_resized)
        self.table.setIconSize(QSize(20, 20))

        # Redirect arrow / Home / End keys from the table back to the main
        # window so keyboard navigation always works regardless of focus.
        self.table.installEventFilter(self)

        # Set default row height for better click targets
        self.table.verticalHeader().setDefaultSectionSize(40)

        # Rounded card so the list reads as a panel like the rest of the app.
        # The table itself stays transparent: the card owns the surface + radius.
        self.card = QFrame()
        self.card.setObjectName("MoveListCard")
        self.card.setFrameShape(QFrame.Shape.NoFrame)
        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)
        card_layout.addWidget(self.table)

        self.layout.addWidget(self.card)

        # Stretch factors
        self.layout.setStretch(0, 1)  # Card

        self._max_seconds = 30.0
        self._selected_index: int | None = None
        self.refresh_styles()

    def eventFilter(self, source, event):
        """Redirect navigation keys from the table to the main window."""
        _NAV_KEYS = {
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
            and event.key() in _NAV_KEYS
        ):
            # Walk up to the QMainWindow and let it handle the key
            parent = self.parent()
            while parent is not None:
                from PyQt6.QtWidgets import QMainWindow

                if isinstance(parent, QMainWindow):
                    parent.keyPressEvent(event)
                    return True
                parent = parent.parent()
        return super().eventFilter(source, event)

    def set_game(self, game_analysis):
        self.current_game = game_analysis
        self._variation_counts = {}
        self._selected_index = None
        self.is_chess960 = bool(getattr(game_analysis.metadata, "chess960", False))
        moves = game_analysis.moves or []
        self.starting_fen = (
            getattr(game_analysis.metadata, "starting_fen", None)
            or (moves[0].fen_before if moves else chess.STARTING_FEN)
        )
        self.session.clear(emit=False)
        self.refresh()

    def clear(self) -> None:
        """Drop the loaded game and its live-engine session."""
        self.current_game = None
        self._variation_counts = {}
        self._selected_index = None
        self.session.clear(emit=False)
        self.refresh()

    def _clear_move_widgets(self) -> None:
        """Drop embedded cell widgets before the table destroys their C++ objects.

        ``QTableWidget`` owns widgets installed with ``setCellWidget()``, so
        clearing the table deletes them. Keeping the Python wrappers in
        ``_move_widgets`` lets later signals call into deleted widgets.
        """
        for widget in self._think_bars:
            if sip.isdeleted(widget):
                continue
            widget.setParent(None)
            widget.deleteLater()
        self._think_bars.clear()
        self._move_widgets.clear()

    def _live_move_widgets(self) -> list[tuple[int, MoveCellWidget]]:
        """Return live cells, pruning wrappers whose C++ object was deleted."""
        live: list[tuple[int, MoveCellWidget]] = []
        for index, widget in list(self._move_widgets.items()):
            if sip.isdeleted(widget):
                self._move_widgets.pop(index, None)
                continue
            live.append((index, widget))
        return live

    def refresh(self):
        if not self.current_game:
            self._clear_move_widgets()
            self.table.clearContents()
            self.table.setRowCount(0)
            self._variation_counts = {}
            return

        try:
            # Clear previously-embedded bar widgets before re-inserting
            self._clear_move_widgets()

            # Clear table contents and reset row count to prevent leftover widgets/text
            self.table.clearContents()
            self.table.setRowCount(0)

            # Set row count
            num_rows = (len(self.current_game.moves) + 1) // 2
            self.table.setRowCount(num_rows)

            # Update vertical header labels (Move numbers)
            labels = [str(i + 1) for i in range(num_rows)]
            self.table.setVerticalHeaderLabels(labels)

            # Calculate max_seconds based on TimeControl
            tc = ""
            if hasattr(self.current_game, "metadata") and self.current_game.metadata:
                tc = getattr(
                    self.current_game.metadata, "time_control", None
                ) or self.current_game.metadata.headers.get("TimeControl", "")

            base_time = 0
            if tc and tc not in ("-", "?", ""):
                for period in tc.split(":"):
                    base_part = period.split("+")[0]  # remove increment
                    sec_part = base_part.split("/")[-1]  # remove move count
                    with contextlib.suppress(ValueError):
                        base_time += int(sec_part)

            # Default max seconds if no time control is 30.
            # Otherwise use 10% of base time, capped between 10s and 600s
            max_seconds = 30.0
            if base_time > 0:
                max_seconds = max(10.0, min(600.0, base_time * 0.1))
            self._max_seconds = max_seconds

            for i, move in enumerate(self.current_game.moves):
                row = i // 2
                col = (i % 2) + 1  # 0->1 (White), 1->2 (Black)

                # Set Move Number for White moves (left of the row)
                if col == 1:
                    num_item = QTableWidgetItem(str(move.move_number))
                    num_item.setTextAlignment(
                        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
                    )
                    num_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
                    num_item.setForeground(QBrush(QColor(Styles.COLOR_TEXT_SECONDARY)))
                    self.table.setItem(row, 0, num_item)

                self._set_move_item(row, col, move, i, max_seconds)

            if self._selected_index is not None:
                self._apply_selection(self._selected_index)
            self.table.viewport().update()
            QTimer.singleShot(0, self._update_compact_mode)

        except Exception as e:
            logger.error(f"Error refreshing move list: {e}", exc_info=True)

    def _set_move_item(self, row, col, move, index, max_seconds=30.0):
        """Render a move cell with icon, SAN, and a think-time bar inline."""
        # Every classified move keeps its badge; routine classes stay neutral text.
        icon = None
        if move.classification:
            icon = self.resource_manager.get_icon(move.classification)

        cell = MoveCellWidget(parent=self.table)
        cell.set_move(
            move,
            index,
            icon=icon,
            max_seconds=max_seconds,
            variation_count=self._variation_counts.get(index, 0),
        )
        cell.clicked.connect(self._on_cell_widget_clicked)
        cell.variation_clicked.connect(self._on_variation_clicked)

        # Keep a strong reference so the widget isn't GC'd
        self._think_bars.append(cell)
        self._move_widgets[index] = cell

        # We also need a backing QTableWidgetItem so the cell is selectable
        # and shows up in the table's selection model.
        item = QTableWidgetItem()
        item.setData(Qt.ItemDataRole.UserRole, index)
        item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
        item.setSizeHint(QSize(120, 38))
        self.table.setItem(row, col, item)
        self.table.setCellWidget(row, col, cell)

    def update_move_cell(
        self, move_index: int, classification: str = None, eval_after_cp=None, eval_after_mate=None
    ):
        """Update a single move cell's classification and eval display during analysis."""
        widget = self._move_widgets.get(move_index)
        if widget is None or sip.isdeleted(widget):
            self._move_widgets.pop(move_index, None)
            return
        if move_index < 0 or move_index >= len(self.current_game.moves):
            return
        move = self.current_game.moves[move_index]
        if classification is not None:
            move.classification = classification
        if eval_after_cp is not None:
            move.eval_after_cp = eval_after_cp
        if eval_after_mate is not None:
            move.eval_after_mate = eval_after_mate
        icon = None
        if move.classification:
            icon = self.resource_manager.get_icon(move.classification)
        widget.set_move(
            move,
            move_index,
            icon=icon,
            max_seconds=self._max_seconds,
            variation_count=self._variation_counts.get(move_index, 0),
        )

    def _on_cell_widget_clicked(self, index: int):
        """Forward clicks from MoveCellWidget into the existing move_selected signal."""
        self.move_selected.emit(index)

    def _on_variation_clicked(self, index: int):
        self.variation_requested.emit(index)

    def _apply_selection(self, index: int | None) -> None:
        """Paint the active half-move and a faint tint over its move pair."""
        self._selected_index = index
        active_row = None if index is None else index // 2
        for move_index, widget in self._live_move_widgets():
            widget.set_state(
                selected=move_index == index,
                row_active=active_row is not None and move_index // 2 == active_row,
            )

    def _update_compact_mode(self) -> None:
        """SAN wins when space is tight: drop the numeric think time, keep the bar."""
        widgets = self._live_move_widgets()
        if not widgets:
            return
        compact = self.table.columnWidth(1) < 100
        for _, widget in widgets:
            widget.set_compact(compact)

    def _on_section_resized(self, *_args) -> None:
        # Column widths settle after the table is laid out, which can happen
        # without a panel resize (e.g. loading a game into a visible window).
        self._update_compact_mode()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_compact_mode()

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(0, self._update_compact_mode)

    def _setup_header(self) -> None:
        """Label the two move columns with a side dot instead of a bare word."""
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

    def set_variation_counts(self, counts: dict[int, int]) -> None:
        """Attach branch badges to game positions that own saved variation trees."""
        self._variation_counts = {int(k): int(v) for k, v in counts.items() if v > 0}
        for index, widget in self._live_move_widgets():
            widget.set_variation_count(self._variation_counts.get(index, 0))

    def refresh_styles(self):
        """Refresh styles for dynamic theme updates."""
        self.setStyleSheet(Styles.get_background_style())
        self.card.setStyleSheet(Styles.get_move_list_card_style())
        self.table.setStyleSheet(Styles.get_move_list_table_style())
        self._setup_header()

        # Re-apply color for move numbers in column 0
        secondary_color = QColor(Styles.COLOR_TEXT_SECONDARY)
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item:
                item.setForeground(QBrush(secondary_color))

        for _, cell in self._live_move_widgets():
            cell.refresh_styles()

        self._apply_selection(self._selected_index)

    def on_cell_clicked(self, row, col):
        if col == 0:
            # Clicking a move number jumps to that row's White move instead of
            # being a dead target.
            index = row * 2
        else:
            item = self.table.item(row, col)
            index = item.data(Qt.ItemDataRole.UserRole) if item else None
        if index is None or not self.current_game:
            return
        if 0 <= index < len(self.current_game.moves):
            self.move_selected.emit(index)

    def select_move(self, index):
        if not self.current_game:
            return

        if index < 0:
            self.table.clearSelection()
            self._apply_selection(None)
            lines, lines_fen = self._lines_for_index(-1)
            self._analysed_fen = lines_fen
            self.lines_updated.emit(lines, lines_fen)
            self._request_live(lines_fen, terminal=False)
            return

        if index >= len(self.current_game.moves):
            return

        row = index // 2
        col = 1 if index % 2 == 0 else 2

        self.table.setCurrentCell(row, col)
        self.table.scrollToItem(self.table.item(row, col))
        self._apply_selection(index)

        move = self.current_game.moves[index]

        lines, lines_fen = self._lines_for_index(index)
        self._analysed_fen = lines_fen

        # Checkmate ends the game: the other MultiPV entries are alternatives
        # to the mating move, not continuations after it. Show only the mating
        # line and do not spend engine time on a finished position.
        self.lines_updated.emit(lines, lines_fen)
        self._request_live(lines_fen, terminal=move.is_checkmate)

    def _request_live(self, fen: str, terminal: bool = False) -> None:
        """Ask the shared session for live lines, or cancel when disabled."""
        if self._variation_active or not self.engine_lines_enabled or terminal or not fen:
            self.session.clear(emit=False)
            return
        self.session.request(fen, chess960=self.is_chess960, emit_empty=False)

    def _lines_for_index(self, index: int) -> tuple[list, str]:
        """White-POV lines matching the position the board shows after ``index``."""
        return lines_for_index(
            self.current_game.moves, index, self.is_chess960
        )

    def _stop_live_analysis(self) -> None:
        """Cancel pending work and invalidate any in-flight results."""
        self.session.clear(emit=False)

    def begin_variation(self, fen: str, is_white: bool) -> None:
        """Analyse an arbitrary position while the board is in variation mode."""
        self._variation_active = True
        self._analysed_fen = fen
        self.lines_updated.emit([], fen)
        if self.engine_lines_enabled:
            self.session.request(fen, chess960=self.is_chess960, emit_empty=False)
        else:
            self.session.clear(emit=False)

    def end_variation(self) -> None:
        """Stop the variation analysis; the caller restores the game position."""
        self._variation_active = False
        self._analysed_fen = None
        self.session.clear(emit=False)

    def set_engine_lines_enabled(self, enabled):
        self.engine_lines_enabled = enabled
        # The toggle stays live inside variation mode too; the variation's
        # current FEN is the position to analyse or clear.
        if self._variation_active:
            self._apply_variation_lines()
            return
        if enabled:
            self.start_live_analysis()
            return

        self.session.clear(emit=False)
        # Restore cached lines (if any) or clear the widget.
        if self.current_game and self.current_game.moves:
            index = self._selected_index if self._selected_index is not None else -1
            lines, lines_fen = self._lines_for_index(index)
            self._analysed_fen = lines_fen
            self.lines_updated.emit(lines, lines_fen)
            return
        self._analysed_fen = None
        self.lines_updated.emit([], "")

    def _apply_variation_lines(self) -> None:
        """Start or clear engine lines for the active variation position."""
        fen = self._analysed_fen
        self.session.clear(emit=False)
        if not fen:
            self.lines_updated.emit([], "")
            return
        if self.engine_lines_enabled:
            self.session.request(fen, chess960=self.is_chess960, emit_empty=False)
        else:
            self.lines_updated.emit([], fen)

    def start_live_analysis(self):
        if not self.current_game or self._variation_active or not self.engine_lines_enabled:
            return
        index = self._selected_index if self._selected_index is not None else -1
        if index >= len(self.current_game.moves):
            return
        if index >= 0 and self.current_game.moves[index].is_checkmate:
            self.session.clear(emit=False)
            return
        lines, lines_fen = self._lines_for_index(index)
        self._analysed_fen = lines_fen
        if lines_fen:
            self.session.request(lines_fen, chess960=self.is_chess960, emit_empty=False)

    def _on_session_lines(self, lines):
        """Publish lines for whichever position the session is analysing.

        Both the game position and a variation position go through the same
        session, so the variation must be forwarded too — dropping it here
        was why jumping into a variation left the panel empty.
        """
        if not self.engine_lines_enabled:
            return
        self.lines_updated.emit(lines, self._analysed_fen or "")

    def closeEvent(self, event):
        self.session.shutdown()
        super().closeEvent(event)

    def update_engine_path(self, path):
        self.engine_path = path
        self.session.set_engine_path(path)
