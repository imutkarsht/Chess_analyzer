"""
Move List Panel - Displays the list of played moves in a paginated/tabular layout.
"""
import contextlib

import chess
from PyQt6.QtCore import QEvent, QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QBrush, QColor
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.gui.analysis.line_utils import lines_for_display
from src.gui.analysis.live_analysis import LiveAnalysisWorker
from src.gui.analysis.move_cell_widget import MoveCellWidget
from src.gui.styles import Styles
from src.utils.logger import logger
from src.utils.resources import ResourceManager


class MoveListPanel(QWidget):
    move_selected = pyqtSignal(int)
    lines_updated = pyqtSignal(list, bool, str)  # lines, is_white_turn, analysed FEN

    def __init__(self, engine_path="stockfish", config_manager=None):
        super().__init__()
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(5)

        self.resource_manager = ResourceManager()
        self.current_game = None

        # Live Analysis — pass the shared ConfigManager so the worker
        # can honour the live_analysis_time / multi_pv settings that
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        # the user has chosen in Settings.
        self.engine_path = engine_path
        self.live_worker = LiveAnalysisWorker(self.engine_path, config_manager=config_manager)
        self.live_worker.info_ready.connect(self.on_live_analysis_update)
        self.live_worker.start()

        self.live_data = {}
        self.current_turn = chess.WHITE
        self.engine_lines_enabled = False # Off by default!
        # The move list's live engine is shared with variation exploration.
        # Every request carries a monotonic seq so stale positions are dropped.
        self._analysis_seq = 0
        self._analysed_fen: str | None = None
        self._variation_active = False
        # Reusable think-time bar widgets (one per cell). We keep strong
        # references because QTableWidget.setCellWidget() does not take
        # ownership; without this, the bars would be garbage-collected
        # and the table would render empty cells.
        self._think_bars: list[MoveCellWidget] = []
        self._move_widgets: dict[int, MoveCellWidget] = {}

        self.analysis_timer = QTimer()
        self.analysis_timer.setSingleShot(True)
        self.analysis_timer.setInterval(1000) # 1 second delay (more responsive)
        self.analysis_timer.timeout.connect(self.start_live_analysis)

        # Move List Table — 3 columns: #, White, Black
        # Think-time is rendered as a thin coloured bar at the bottom of the
        # move cell itself (no separate column) so the table stays readable
        # in a narrow left-pane.
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(
            ["#", "White", "Black"]
        )
        self.table.horizontalHeader().setHighlightSections(False)
        self.table.horizontalHeader().setMinimumHeight(32)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(0, 46)   # #  — wide enough for two-digit move numbers
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)

        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(False)  # Using custom hover instead
        self.table.setShowGrid(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.cellClicked.connect(self.on_cell_clicked)
        self.table.setIconSize(QSize(20, 20))

        # Redirect arrow / Home / End keys from the table back to the main
        # window so keyboard navigation always works regardless of focus.
        self.table.installEventFilter(self)

        # Set default row height for better click targets
        self.table.verticalHeader().setDefaultSectionSize(40)

        self.layout.addWidget(self.table)

        # Stretch factors
        self.layout.setStretch(0, 1)  # Table

    def eventFilter(self, source, event):
        """Redirect navigation keys from the table to the main window."""
        _NAV_KEYS = {
            Qt.Key.Key_Left, Qt.Key.Key_Right,
            Qt.Key.Key_Up,   Qt.Key.Key_Down,
            Qt.Key.Key_Home, Qt.Key.Key_End,
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
        self.live_worker.set_chess960(game_analysis.metadata.chess960)
        self.refresh()

    def refresh(self):
        if not self.current_game:
            self.table.clearContents()
            self.table.setRowCount(0)
            self._think_bars.clear()
            return

        try:
            # Clear previously-embedded bar widgets before re-inserting
            for bar in self._think_bars:
                bar.setParent(None)
                bar.deleteLater()
            self._think_bars.clear()
            self._move_widgets.clear()

            # Clear table contents and reset row count to prevent leftover widgets/text
            self.table.clearContents()
            self.table.setRowCount(0)

            # Set row count
            num_rows = (len(self.current_game.moves) + 1) // 2
            self.table.setRowCount(num_rows)

            # Update vertical header labels (Move numbers)
            labels = [str(i+1) for i in range(num_rows)]
            self.table.setVerticalHeaderLabels(labels)

            # Calculate max_seconds based on TimeControl
            tc = ""
            if hasattr(self.current_game, 'metadata') and self.current_game.metadata:
                tc = getattr(self.current_game.metadata, 'time_control', None) or self.current_game.metadata.headers.get("TimeControl", "")

            base_time = 0
            if tc and tc not in ("-", "?", ""):
                for period in tc.split(":"):
                    base_part = period.split("+")[0]      # remove increment
                    sec_part = base_part.split("/")[-1]   # remove move count
                    with contextlib.suppress(ValueError):
                        base_time += int(sec_part)

            # Default max seconds if no time control is 30.
            # Otherwise use 10% of base time, capped between 10s and 600s
            max_seconds = 30.0
            if base_time > 0:
                max_seconds = max(10.0, min(600.0, base_time * 0.1))

            for i, move in enumerate(self.current_game.moves):
                row = i // 2
                col = (i % 2) + 1  # 0->1 (White), 1->2 (Black)

                # Set Move Number for White moves (left of the row)
                if col == 1:
                    num_item = QTableWidgetItem(str(move.move_number))
                    num_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    num_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
                    num_item.setForeground(QBrush(QColor(Styles.COLOR_TEXT_SECONDARY)))
                    self.table.setItem(row, 0, num_item)

                self._set_move_item(row, col, move, i, max_seconds)

            self.table.viewport().update()

        except Exception as e:
            logger.error(f"Error refreshing move list: {e}", exc_info=True)

    def _set_move_item(self, row, col, move, index, max_seconds=30.0):
        """Render a move cell with icon, SAN, and a think-time bar inline."""
        # Get classification icon (if any)
        icon = None
        if move.classification:
            icon = self.resource_manager.get_icon(move.classification)

        # Resolve the SAN colour from the project's styles module
        san_color = Styles.get_class_color(move.classification) or Styles.COLOR_TEXT_PRIMARY

        cell = MoveCellWidget(parent=self.table)
        cell.set_move(move, index, icon=icon, san_color=san_color, max_seconds=max_seconds)
        cell.clicked.connect(self._on_cell_widget_clicked)

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

    def update_move_cell(self, move_index: int, classification: str = None,
                         eval_after_cp=None, eval_after_mate=None):
        """Update a single move cell's classification and eval display during analysis."""
        widget = self._move_widgets.get(move_index)
        if widget is None:
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
        san_color = Styles.get_class_color(move.classification) or Styles.COLOR_TEXT_PRIMARY
        widget.set_move(move, move_index, icon=icon, san_color=san_color)

    def _on_cell_widget_clicked(self, index: int):
        """Forward clicks from MoveCellWidget into the existing move_selected signal."""
        self.move_selected.emit(index)

    def refresh_styles(self):
        """Refresh styles for dynamic theme updates."""
        self.setStyleSheet(Styles.get_background_style())
        self.table.setStyleSheet(Styles.get_move_list_table_style())

        # Re-apply color for move numbers in column 0
        from PyQt6.QtGui import QBrush, QColor
        secondary_color = QColor(Styles.COLOR_TEXT_SECONDARY)
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item:
                item.setForeground(QBrush(secondary_color))

        for cell in self._think_bars:
            cell.refresh_styles()

    def on_cell_clicked(self, row, col):
        item = self.table.item(row, col)
        if item:
            index = item.data(Qt.ItemDataRole.UserRole)
            if index is not None:
                self.move_selected.emit(index)

    def select_move(self, index):
        if not self.current_game:
            return

        if index < 0:
            self.table.clearSelection()
            self.current_turn = chess.WHITE
            self.live_data = {}
            self._stop_live_analysis()
            self._analysed_fen = None
            self.lines_updated.emit([], True, "")
            return

        if index >= len(self.current_game.moves):
            return

        row = index // 2
        col = 1 if index % 2 == 0 else 2

        self.table.setCurrentCell(row, col)
        self.table.scrollToItem(self.table.item(row, col))

        move = self.current_game.moves[index]

        lines, is_white, lines_fen = self._lines_for_index(index)
        self.current_turn = chess.WHITE if is_white else chess.BLACK
        self.live_data = {}
        self._analysed_fen = lines_fen

        # Checkmate ends the game: the other MultiPV entries are alternatives
        # to the mating move, not continuations after it. Show only the mating
        # line and do not spend engine time on a finished position.
        if move.is_checkmate:
            self._stop_live_analysis()
            self.lines_updated.emit(lines, is_white, lines_fen)
            return

        # Emit signal instead of updating directly
        self.lines_updated.emit(lines, is_white, lines_fen)

        if self.engine_lines_enabled:
            self.analysis_timer.start()

    def _lines_for_index(self, index: int) -> tuple[list[dict], bool, str]:
        """Lines for the position shown on the board after move ``index``.

        The evaluation panel describes the board, which holds the position
        *after* the selected move. The next move's analysis is exactly that
        position (its ``fen_before``), so reuse it instead of the pre-move
        MultiPVs, which would repeat the move already on the board. The final
        move has no successor, so fall back to its own lines.
        """
        moves = self.current_game.moves
        if index + 1 < len(moves):
            nxt = moves[index + 1]
            return lines_for_display(nxt), (index + 1) % 2 == 0, nxt.fen_before
        move = moves[index]
        return lines_for_display(move), index % 2 == 0, move.fen_before

    def _stop_live_analysis(self) -> None:
        """Cancel the pending timer and invalidate any in-flight results."""
        self.analysis_timer.stop()
        self._analysis_seq += 1
        self.live_worker.set_position(None, self._analysis_seq)

    def begin_variation(self, fen: str, is_white: bool) -> None:
        """Analyse an arbitrary position while the board is in variation mode."""
        self._variation_active = True
        self.analysis_timer.stop()
        self.current_turn = chess.WHITE if is_white else chess.BLACK
        self.live_data = {}
        self._analysis_seq += 1
        self._analysed_fen = fen
        self.lines_updated.emit([], is_white, fen)
        self.live_worker.set_position(fen, self._analysis_seq)

    def end_variation(self) -> None:
        """Stop the variation analysis; the caller restores the game position."""
        self._variation_active = False
        self.analysis_timer.stop()
        self._analysis_seq += 1
        self._analysed_fen = None
        self.live_data = {}
        self.live_worker.set_position(None, self._analysis_seq)

    def set_engine_lines_enabled(self, enabled):
        if self._variation_active:
            return
        self.engine_lines_enabled = enabled
        if enabled:
            self.start_live_analysis()
        else:
            self._stop_live_analysis()
            # Restore cached lines (if any) or clear the widget
            if self.current_game:
                index = self.table.currentRow() * 2 + (self.table.currentColumn() - 1)
                if 0 <= index < len(self.current_game.moves):
                    lines, is_white, lines_fen = self._lines_for_index(index)
                    self.lines_updated.emit(lines, is_white, lines_fen)
                    return
            self.lines_updated.emit([], self.current_turn == chess.WHITE, "")

    def start_live_analysis(self):
        if not self.current_game or self._variation_active or not self.engine_lines_enabled:
            return
        index = self.table.currentRow() * 2 + (self.table.currentColumn() - 1)
        if index < 0 or index >= len(self.current_game.moves):
            return
        move = self.current_game.moves[index]
        lines, is_white, lines_fen = self._lines_for_index(index)
        self.current_turn = chess.WHITE if is_white else chess.BLACK
        self._analysed_fen = lines_fen
        if move.is_checkmate:
            self._stop_live_analysis()
            self.lines_updated.emit(lines, is_white, lines_fen)
            return
        self._analysis_seq += 1
        self.live_worker.set_position(lines_fen, self._analysis_seq)

    def on_live_analysis_update(self, info):
        # Drop results that belong to a position we have already left.
        if info.get("seq") != self._analysis_seq:
            return
        multipv_id = info.get("multipv", 1)
        self.live_data[multipv_id] = info
        sorted_lines = sorted(self.live_data.values(), key=lambda x: x.get("multipv", 1))

        # Emit signal
        self.lines_updated.emit(
            sorted_lines, self.current_turn == chess.WHITE, self._analysed_fen or ""
        )

    def closeEvent(self, event):
        self.live_worker.stop()
        super().closeEvent(event)

    def update_engine_path(self, path):
        self.engine_path = path
        self.live_worker.stop()
        # Re-create the worker preserving the same config_manager so
        # the live-panel settings (time, multi_pv) survive a path swap.
        self.live_worker = LiveAnalysisWorker(self.engine_path, config_manager=self.live_worker.config_manager)
        self.live_worker.info_ready.connect(self.on_live_analysis_update)
        self.live_worker.start()
