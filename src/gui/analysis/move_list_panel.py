"""
Move List Panel - Displays the list of played moves in a paginated/tabular layout.
"""
import chess
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView
from PyQt6.QtCore import pyqtSignal, Qt, QTimer, QSize, QEvent
from PyQt6.QtGui import QColor, QBrush
from ..styles import Styles
from .move_cell_widget import MoveCellWidget
from .think_time_bar import ThinkTimeBar
from ..live_analysis import LiveAnalysisWorker
from ...utils.resources import ResourceManager
from ...utils.logger import logger

class MoveListPanel(QWidget):
    move_selected = pyqtSignal(int)
    lines_updated = pyqtSignal(list, bool) # lines, is_white_turn
    
    def __init__(self, engine_path="stockfish", config_manager=None):
        super().__init__()
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(5)

        self.resource_manager = ResourceManager()
        self.current_game = None

        # Live Analysis — pass the shared ConfigManager so the worker
        # can honour the live_analysis_time / multi_pv settings that
        # the user has chosen in Settings.
        self.engine_path = engine_path
        self.live_worker = LiveAnalysisWorker(self.engine_path, config_manager=config_manager)
        self.live_worker.info_ready.connect(self.on_live_analysis_update)
        self.live_worker.start()
        
        self.live_data = {}
        self.current_turn = chess.WHITE
        self.engine_lines_enabled = False # Off by default!
        # Reusable think-time bar widgets (one per cell). We keep strong
        # references because QTableWidget.setCellWidget() does not take
        # ownership; without this, the bars would be garbage-collected
        # and the table would render empty cells.
        self._think_bars: list[MoveCellWidget] = []
        
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
        
        # Enhanced table styling  
        self.table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {Styles.COLOR_SURFACE};
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 8px;
                gridline-color: transparent;
                font-size: 14px;
            }}
            QTableWidget::item {{
                padding: 6px 8px;
                border-bottom: 1px solid {Styles.COLOR_SURFACE_LIGHT};
            }}
            QTableWidget::item:hover {{
                background-color: {Styles.COLOR_SURFACE_LIGHT};
            }}
            QTableWidget::item:selected {{
                background-color: {Styles.COLOR_HIGHLIGHT};
                color: {Styles.COLOR_TEXT_PRIMARY};
                border-left: 3px solid {Styles.COLOR_ACCENT};
            }}
            QHeaderView::section {{
                background-color: {Styles.COLOR_SURFACE_LIGHT};
                color: {Styles.COLOR_TEXT_SECONDARY};
                padding: 10px 6px;
                border: none;
                border-bottom: 2px solid {Styles.COLOR_ACCENT};
                font-weight: 600;
                font-size: 13px;
            }}
        """)
        
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
        if source is self.table and event.type() == QEvent.Type.KeyPress:
            if event.key() in _NAV_KEYS:
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
                    try:
                        base_time += int(sec_part)
                    except ValueError:
                        pass
            
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

        # We also need a backing QTableWidgetItem so the cell is selectable
        # and shows up in the table's selection model.
        item = QTableWidgetItem()
        item.setData(Qt.ItemDataRole.UserRole, index)
        item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
        item.setSizeHint(QSize(120, 38))
        self.table.setItem(row, col, item)
        self.table.setCellWidget(row, col, cell)

    def _on_cell_widget_clicked(self, index: int):
        """Forward clicks from MoveCellWidget into the existing move_selected signal."""
        self.move_selected.emit(index)
    
    def refresh_styles(self):
        """Refresh styles for dynamic theme updates."""
        self.table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {Styles.COLOR_SURFACE};
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 8px;
                gridline-color: transparent;
                font-size: 14px;
            }}
            QTableWidget::item {{
                padding: 6px 8px;
                border-bottom: 1px solid {Styles.COLOR_SURFACE_LIGHT};
            }}
            QTableWidget::item:hover {{
                background-color: {Styles.COLOR_SURFACE_LIGHT};
            }}
            QTableWidget::item:selected {{
                background-color: {Styles.COLOR_HIGHLIGHT};
                color: {Styles.COLOR_TEXT_PRIMARY};
                border-left: 3px solid {Styles.COLOR_ACCENT};
            }}
            QHeaderView::section {{
                background-color: {Styles.COLOR_SURFACE_LIGHT};
                color: {Styles.COLOR_TEXT_SECONDARY};
                padding: 10px 6px;
                border: none;
                border-bottom: 2px solid {Styles.COLOR_ACCENT};
                font-weight: 600;
                font-size: 13px;
            }}
        """)

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
            return
            
        if index >= len(self.current_game.moves):
            return
            
        row = index // 2
        col = 1 if index % 2 == 0 else 2
        
        self.table.setCurrentCell(row, col)
        self.table.scrollToItem(self.table.item(row, col))
        
        move = self.current_game.moves[index]
        turn = chess.WHITE if index % 2 == 0 else chess.BLACK
        
        # Emit signal instead of updating directly
        self.lines_updated.emit(move.multi_pvs, turn == chess.WHITE)
        
        self.current_turn = turn
        self.live_data = {}
        if self.engine_lines_enabled:
            self.analysis_timer.start()

    def set_engine_lines_enabled(self, enabled):
        self.engine_lines_enabled = enabled
        if enabled:
            self.start_live_analysis()
        else:
            self.live_worker.set_position(None)
            # Restore cached lines (if any) or clear the widget
            if self.current_game:
                index = self.table.currentRow() * 2 + (self.table.currentColumn() - 1)
                if 0 <= index < len(self.current_game.moves):
                    move = self.current_game.moves[index]
                    self.lines_updated.emit(move.multi_pvs, self.current_turn == chess.WHITE)
                    return
            self.lines_updated.emit([], self.current_turn == chess.WHITE)

    def start_live_analysis(self):
        if not self.current_game:
            return
        index = self.table.currentRow() * 2 + (self.table.currentColumn() - 1)
        if index < 0 or index >= len(self.current_game.moves):
            return
        move = self.current_game.moves[index]
        self.live_worker.set_position(move.fen_before)

    def on_live_analysis_update(self, info):
        multipv_id = info.get("multipv", 1)
        self.live_data[multipv_id] = info
        sorted_lines = sorted(self.live_data.values(), key=lambda x: x.get("multipv", 1))
        
        # Emit signal
        self.lines_updated.emit(sorted_lines, self.current_turn == chess.WHITE)

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
