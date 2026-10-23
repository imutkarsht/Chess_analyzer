"""
Move List Panel - Displays the list of played moves in a paginated/tabular layout.
"""

import contextlib

import chess
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

from src.gui.analysis.line_utils import lines_for_display
from src.gui.analysis.live_analysis import LiveAnalysisWorker
from src.gui.analysis.move_cell_widget import MoveCellWidget
from src.gui.styles import Styles
from src.utils.logger import logger
from src.utils.resources import ResourceManager


class MoveListPanel(QWidget):
    move_selected = pyqtSignal(int)
    lines_updated = pyqtSignal(list, bool, str)  # lines, is_white_turn, analysed FEN
    variation_requested = pyqtSignal(int)

    def __init__(self, engine_path="stockfish", config_manager=None):
        super().__init__()
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(5, 5, 5, 5)
        self.layout.setSpacing(0)

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
        self.engine_lines_enabled = False  # Off by default!
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
        self._variation_counts: dict[int, int] = {}

        self.analysis_timer = QTimer()
        self.analysis_timer.setSingleShot(True)
        self.analysis_timer.setInterval(1000)  # 1 second delay (more responsive)
        self.analysis_timer.timeout.connect(self.start_live_analysis)

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
        for move_index, widget in self._move_widgets.items():
            widget.set_state(
                selected=move_index == index,
                row_active=active_row is not None and move_index // 2 == active_row,
            )

    def _update_compact_mode(self) -> None:
        """SAN wins when space is tight: drop the numeric think time, keep the bar."""
        if not self._move_widgets:
            return
        compact = self.table.columnWidth(1) < 130
        for widget in self._move_widgets.values():
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
        for index, widget in self._move_widgets.items():
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

        for cell in self._think_bars:
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
        self._apply_selection(index)

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
        self.live_worker = LiveAnalysisWorker(
            self.engine_path, config_manager=self.live_worker.config_manager
        )
        self.live_worker.info_ready.connect(self.on_live_analysis_update)
        self.live_worker.start()
