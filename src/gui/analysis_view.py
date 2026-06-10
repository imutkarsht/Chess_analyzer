from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, 
                             QHeaderView, QLabel, QGridLayout, QFrame, QHBoxLayout, 
                             QPushButton, QAbstractItemView, QCheckBox, QTabWidget, QSizePolicy)
from .graph_widget import GraphWidget
from PyQt6.QtCore import pyqtSignal, Qt, QTimer, QThread, QSize, QEvent
from PyQt6.QtGui import QColor, QBrush, QFont, QIcon
from .styles import Styles
from .gui_utils import (clear_layout, create_button, show_error_dialog,
                      is_error_message, format_clock_duration,
                      format_time_stats_for_llm, ThinkTimeBar,
                      MoveCellWidget)
from .components import SimpleStatCard as StatCard
from .analysis import CapturedPiecesWidget, GameControlsWidget  # From analysis package
from ..utils.resources import ResourceManager
from ..utils.logger import logger
import chess
from .live_analysis import LiveAnalysisWorker
from ..backend.groq_service import GroqService
from PyQt6.QtWidgets import QTextEdit, QMessageBox
from ..utils.config import ConfigManager
from .loading_widget import LoadingOverlay


# CapturedPiecesWidget and GameControlsWidget imported from .analysis package

class AnalysisLinesWidget(QFrame):
    def __init__(self):
        super().__init__()
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {Styles.COLOR_SURFACE};
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 12px;
                padding: 10px;
            }}
            QWidget#AnalysisRow {{
                background-color: transparent;
                border-radius: 8px;
                border-bottom: 1px solid {Styles.COLOR_SURFACE_LIGHT};
            }}
            QWidget#AnalysisRow:hover {{
                background-color: {Styles.COLOR_SURFACE_LIGHT};
            }}
            QLabel {{
                border: none;
                background: transparent;
            }}
        """)
        
        self.layout = QVBoxLayout(self)
        self.layout.setSpacing(6)
        self.layout.setContentsMargins(8, 8, 8, 8)
        
        # Header Layout for the toggles (Engine Lines and Use Cache)
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(4, 2, 4, 2)
        header_layout.setSpacing(16)
        
        self.toggle_checkbox = QCheckBox("Engine Lines")
        self.toggle_checkbox.setChecked(False) # Off by default!
        self.toggle_checkbox.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_checkbox.setStyleSheet(f"""
            QCheckBox {{
                color: {Styles.COLOR_TEXT_PRIMARY};
                font-weight: bold;
                font-size: 13px;
                background: transparent;
                border: none;
            }}
            QCheckBox::indicator {{
                width: 16px;
                height: 16px;
            }}
        """)
        header_layout.addWidget(self.toggle_checkbox)

        self.cache_checkbox = QCheckBox("Use Cache")
        self.cache_checkbox.setChecked(True)
        self.cache_checkbox.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cache_checkbox.setStyleSheet(f"""
            QCheckBox {{
                color: {Styles.COLOR_TEXT_PRIMARY};
                font-weight: bold;
                font-size: 13px;
                background: transparent;
                border: none;
            }}
            QCheckBox::indicator {{
                width: 16px;
                height: 16px;
            }}
        """)
        header_layout.addWidget(self.cache_checkbox)
        
        header_layout.addStretch()
        self.layout.addLayout(header_layout)
        
        self.rows = [] # List of (widget, lbl_depth, lbl_eval, lbl_pv) tuples
        self.lines_layout = QVBoxLayout()
        self.lines_layout.setSpacing(6)
        self.layout.addLayout(self.lines_layout)
        self.layout.addStretch() # Push lines to top

    def clear(self):
        """Clears all analysis lines."""
        for row_data in self.rows:
            row_data[0].hide()

    def _format_pv_to_html(self, pv_text: str) -> str:
        if not pv_text:
            return ""
        words = pv_text.split()
        html_words = []
        first_move = True
        for word in words:
            # Check if it's a move number (e.g. "14.", "13...")
            if word[0].isdigit() or word.endswith("..."):
                html_words.append(f"<span style='color: {Styles.COLOR_TEXT_MUTED}; font-weight: 500;'>{word}</span>")
            else:
                # It's a move
                if first_move:
                    html_words.append(f"<span style='color: {Styles.COLOR_ACCENT}; font-weight: 700;'>{word}</span>")
                    first_move = False
                else:
                    html_words.append(f"<span style='color: {Styles.COLOR_TEXT_PRIMARY}; font-weight: 600;'>{word}</span>")
        return " ".join(html_words)

    def update_lines(self, multi_pvs, turn_color):
        if not multi_pvs:
            self.clear()
            return

        # Ensure we have enough rows
        while len(self.rows) < len(multi_pvs):
            self._create_row()
            
        # Update rows
        for i, pv_data in enumerate(multi_pvs):
            row_widget, lbl_depth, lbl_eval, lbl_pv = self.rows[i]
            row_widget.show()
            
            # Depth
            depth = pv_data.get("depth", "?")
            lbl_depth.setText(f"d{depth}")
            lbl_depth.setStyleSheet(f"""
                QLabel {{
                    color: {Styles.COLOR_TEXT_SECONDARY};
                    font-size: 11px;
                    font-family: monospace;
                    background-color: {Styles.COLOR_SURFACE_LIGHT};
                    border-radius: 4px;
                    padding: 2px 4px;
                }}
            """)
            
            # Eval
            score_val = pv_data.get("score_value", "?")
            display_score = score_val
            bg_color = Styles.COLOR_SURFACE_LIGHT
            text_color = Styles.COLOR_TEXT_PRIMARY

            try:
                if score_val.startswith("M"):
                    # Mate score: M+ → White mates, M- → Black mates
                    if "-" in score_val:
                        bg_color = "#1a1a1a"   # Very dark — Black is mating
                        text_color = "#E4E4E7"
                    else:
                        bg_color = "#E8E8E8"   # Near-white — White is mating
                        text_color = "#111111"
                else:
                    val = float(score_val)
                    if turn_color == chess.BLACK:
                        val = -val
                    display_score = f"{val:+.2f}"

                    # + → White better (light badge), - → Black better (dark badge)
                    if val > 0:
                        # Blend from neutral to full white as advantage grows
                        intensity = min(1.0, abs(val) / 3.0)
                        r = int(Styles.COLOR_SURFACE_LIGHT.lstrip("#")[0:2], 16)
                        r = int(r + (232 - r) * intensity)
                        g = int(Styles.COLOR_SURFACE_LIGHT.lstrip("#")[2:4], 16)
                        g = int(g + (232 - g) * intensity)
                        b = int(Styles.COLOR_SURFACE_LIGHT.lstrip("#")[4:6], 16)
                        b = int(b + (232 - b) * intensity)
                        bg_color = f"#{r:02X}{g:02X}{b:02X}"
                        text_color = "#111111" if intensity > 0.4 else Styles.COLOR_TEXT_PRIMARY
                    elif val < 0:
                        # Blend from neutral to near-black as Black's advantage grows
                        intensity = min(1.0, abs(val) / 3.0)
                        r = int(Styles.COLOR_SURFACE_LIGHT.lstrip("#")[0:2], 16)
                        r = int(r * (1 - intensity * 0.85))
                        g = int(Styles.COLOR_SURFACE_LIGHT.lstrip("#")[2:4], 16)
                        g = int(g * (1 - intensity * 0.85))
                        b = int(Styles.COLOR_SURFACE_LIGHT.lstrip("#")[4:6], 16)
                        b = int(b * (1 - intensity * 0.85))
                        bg_color = f"#{r:02X}{g:02X}{b:02X}"
                        text_color = "#E4E4E7"
            except:
                pass

            lbl_eval.setText(display_score)
            lbl_eval.setStyleSheet(f"""
                QLabel {{
                    background-color: {bg_color};
                    color: {text_color};
                    border-radius: 4px;
                    padding: 2px 6px;
                    font-weight: bold;
                    font-family: monospace;
                    font-size: 12px;
                }}
            """)
            
            # PV
            pv_text = pv_data.get("pv_san", "")
            if not pv_text:
                pv_moves = pv_data.get("pv", [])
                pv_text = " ".join(pv_moves[:5]) 
            
            formatted_pv = self._format_pv_to_html(pv_text)
            lbl_pv.setText(formatted_pv)

        # Hide unused rows
        for i in range(len(multi_pvs), len(self.rows)):
            self.rows[i][0].hide()

    def _create_row(self):
        row_widget = QWidget()
        row_widget.setObjectName("AnalysisRow")
        row_layout = QVBoxLayout(row_widget)
        row_layout.setContentsMargins(8, 8, 8, 8)
        row_layout.setSpacing(6)
        
        # Top row layout for evaluation and depth badges
        top_layout = QHBoxLayout()
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(8)
        
        # Eval Badge
        lbl_eval = QLabel("+0.00")
        lbl_eval.setFixedWidth(65)
        lbl_eval.setAlignment(Qt.AlignmentFlag.AlignCenter)
        top_layout.addWidget(lbl_eval, alignment=Qt.AlignmentFlag.AlignVCenter)

        # Depth Badge
        lbl_depth = QLabel("d0")
        lbl_depth.setFixedWidth(40)
        lbl_depth.setAlignment(Qt.AlignmentFlag.AlignCenter)
        top_layout.addWidget(lbl_depth, alignment=Qt.AlignmentFlag.AlignVCenter)
        
        top_layout.addStretch()
        row_layout.addLayout(top_layout)
        
        # PV Move sequence line (rendered below the badges)
        lbl_pv = QLabel("")
        lbl_pv.setWordWrap(True) # Wrap text
        lbl_pv.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        lbl_pv.setStyleSheet(f"font-size: 12px; color: {Styles.COLOR_TEXT_PRIMARY};")
        row_layout.addWidget(lbl_pv)
        
        self.lines_layout.addWidget(row_widget)
        self.rows.append((row_widget, lbl_depth, lbl_eval, lbl_pv))

    def _clear_layout(self, layout):
        # Deprecated, not used in optimized version
        pass


# GameControlsWidget class removed - imported from .analysis package

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
        # the user has chosen in Settings.  See issue #5.
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
        self._think_bars: list[ThinkTimeBar] = []
        
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
        header.resizeSection(0, 38)   # #  — move number
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
        self.refresh()
        
    def refresh(self):
        if not self.current_game:
            self.table.setRowCount(0)
            self._think_bars.clear()
            return

        try:
            # Clear previously-embedded bar widgets before re-inserting
            for bar in self._think_bars:
                bar.setParent(None)
                bar.deleteLater()
            self._think_bars.clear()

            # Set row count
            num_rows = (len(self.current_game.moves) + 1) // 2
            self.table.setRowCount(num_rows)

            # Update vertical header labels (Move numbers)
            labels = [str(i+1) for i in range(num_rows)]
            self.table.setVerticalHeaderLabels(labels)

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

                self._set_move_item(row, col, move, i)

            self.table.viewport().update()

        except Exception as e:
            logger.error(f"Error refreshing move list: {e}", exc_info=True)

    def _set_move_item(self, row, col, move, index):
        """Render a move cell with icon, SAN, and a think-time bar inline."""
        # Get classification icon (if any)
        icon = None
        if move.classification:
            icon = self.resource_manager.get_icon(move.classification)

        # Resolve the SAN colour from the project's styles module
        san_color = Styles.get_class_color(move.classification) or Styles.COLOR_TEXT_PRIMARY

        cell = MoveCellWidget(parent=self.table)
        cell.set_move(move, index, icon=icon, san_color=san_color)
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
            # self.lines_widget.update_lines([], chess.WHITE) # Moved
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

class AnalysisPanel(QWidget):
    cache_toggled = pyqtSignal(bool)

    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout(self)
        self.layout.setSpacing(10)
        self.layout.setContentsMargins(5, 5, 5, 5)
        
        self.resource_manager = ResourceManager()
        self.config_manager = ConfigManager()
        self.groq_service = GroqService()
        self.current_game = None
        
        # Tabs
        self.tabs = QTabWidget()
        self.layout.addWidget(self.tabs)
        
        # --- Tab 1: Evaluation ---
        self.eval_tab = QWidget()
        self.eval_layout = QVBoxLayout(self.eval_tab)
        self.eval_layout.setContentsMargins(5, 5, 5, 5)
        
        # Graph
        self.graph_widget = GraphWidget()
        self.graph_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.eval_layout.addWidget(self.graph_widget, stretch=2)
        
        # Analysis Lines (Moved here)
        self.lines_widget = AnalysisLinesWidget()
        self.eval_layout.addWidget(self.lines_widget, stretch=1)
        
        self.tabs.addTab(self.eval_tab, "Evaluation")
        
        # --- Tab 2: Report ---
        self.report_tab = QWidget()
        self.report_layout = QVBoxLayout(self.report_tab)
        self.report_layout.setContentsMargins(5, 5, 5, 5)
        self.report_layout.setSpacing(10)
        
        # Opening
        self.opening_label = QLabel("Opening: -")
        self.opening_label.setStyleSheet(f"color: {Styles.COLOR_TEXT_SECONDARY}; font-size: 14px; font-weight: bold;")
        self.opening_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.report_layout.addWidget(self.opening_label)
        
        # Accuracy
        self.accuracy_frame = QFrame()
        self.accuracy_layout = QHBoxLayout(self.accuracy_frame)
        self.accuracy_layout.setContentsMargins(0, 0, 0, 0)
        self.report_layout.addWidget(self.accuracy_frame)
        
        # Stats Grid
        self.stats_frame = QFrame()
        self.stats_layout = QGridLayout(self.stats_frame)
        self.stats_layout.setSpacing(5)
        self.stats_layout.setContentsMargins(0, 0, 0, 0)
        self.report_layout.addWidget(self.stats_frame)
        
        # AI Summary
        self.ai_summary_frame = QFrame()
        self.ai_summary_layout = QVBoxLayout(self.ai_summary_frame)
        self.ai_summary_layout.setContentsMargins(0, 5, 0, 0)
        
        self.btn_generate_summary = QPushButton("Generate AI Summary")
        self.btn_generate_summary.setStyleSheet(Styles.get_button_style())
        self.btn_generate_summary.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_generate_summary.clicked.connect(self.generate_ai_summary)
        self.ai_summary_layout.addWidget(self.btn_generate_summary)
        
        self.txt_ai_summary = QTextEdit()
        self.txt_ai_summary.setReadOnly(True)
        self.txt_ai_summary.setPlaceholderText("AI Summary will appear here...")
        self.txt_ai_summary.setStyleSheet(f"""
            QTextEdit {{
                background-color: {Styles.COLOR_SURFACE_LIGHT};
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 8px;
                padding: 10px;
                color: {Styles.COLOR_TEXT_PRIMARY};
            }}
        """)
        self.txt_ai_summary.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.ai_summary_layout.addWidget(self.txt_ai_summary)
        
        self.report_layout.addWidget(self.ai_summary_frame)
        self.report_layout.setStretchFactor(self.ai_summary_frame, 1)
        
        self.tabs.addTab(self.report_tab, "Report")
        
        # Cache Checkbox connected from the header layout
        self.cache_checkbox = self.lines_widget.cache_checkbox
        self.cache_checkbox.toggled.connect(self.cache_toggled.emit)
        
        # Loading Overlay
        self.loading_overlay = LoadingOverlay(self)

    def set_game(self, game_analysis):
        self.current_game = game_analysis
        self.refresh()
        
    def refresh(self):
        if not self.current_game:
            self.lines_widget.clear()
            return
            
        try:
            self.lines_widget.clear()
            self.graph_widget.plot_game(self.current_game)
            self._update_summary(self.current_game.summary)
            
            opening = self.current_game.metadata.opening
            self.opening_label.setText(f"Opening: {opening}" if opening else "Opening: Unknown")
            
            if self.current_game.ai_summary:
                self.txt_ai_summary.setText(self.current_game.ai_summary)
                self.btn_generate_summary.setVisible(False)
                self.txt_ai_summary.setVisible(True)
            else:
                self.txt_ai_summary.clear()
                self.btn_generate_summary.setVisible(True)
                self.txt_ai_summary.setVisible(False)
                
        except Exception as e:
            logger.error(f"Error refreshing AnalysisPanel: {e}", exc_info=True)

    def _update_summary(self, summary):
        clear_layout(self.accuracy_layout)
        clear_layout(self.stats_layout)
        
        if not summary:
            logger.warning("AnalysisPanel: Summary is empty/None")
            return
            
        if "white" not in summary:
            logger.warning(f"AnalysisPanel: Summary missing 'white' key. Keys: {summary.keys()}")
            return
            
        w_acc = summary['white'].get('accuracy', 0)
        b_acc = summary['black'].get('accuracy', 0)
        
        self.accuracy_layout.addWidget(StatCard("White Accuracy", f"{w_acc:.1f}%", Styles.COLOR_TEXT_PRIMARY))
        self.accuracy_layout.addWidget(StatCard("Black Accuracy", f"{b_acc:.1f}%", Styles.COLOR_TEXT_PRIMARY))
        
        # Stats Grid
        self.stats_layout.addWidget(QLabel(""), 0, 0)
        lbl_w = QLabel("White")
        lbl_w.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_w.setStyleSheet("font-weight: bold;")
        self.stats_layout.addWidget(lbl_w, 0, 1)
        
        self.stats_layout.addWidget(QLabel(""), 0, 2)
        
        lbl_b = QLabel("Black")
        lbl_b.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_b.setStyleSheet("font-weight: bold;")
        self.stats_layout.addWidget(lbl_b, 0, 3)
        
        types = ["Brilliant", "Great", "Best", "Excellent", "Good", "Book", "Inaccuracy", "Mistake", "Miss", "Blunder"]
        
        for i, type_name in enumerate(types):
            color = Styles.get_class_color(type_name)
            
            lbl_type = QLabel(type_name)
            lbl_type.setStyleSheet(f"color: {color}; font-weight: bold; font-size: 12px;") # Smaller font
            self.stats_layout.addWidget(lbl_type, i+1, 0)
            
            val_w = summary['white'].get(type_name, 0)
            lbl_val_w = QLabel(str(val_w))
            lbl_val_w.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_val_w.setStyleSheet(f"color: {color}; font-weight: bold;")
            self.stats_layout.addWidget(lbl_val_w, i+1, 1)
            
            icon_label = QLabel()
            icon = self.resource_manager.get_icon(type_name)
            if not icon.isNull():
                icon_label.setPixmap(icon.pixmap(22, 22))
                icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            else:
                icon_label.setText("-")
            self.stats_layout.addWidget(icon_label, i+1, 2)
            
            val_b = summary['black'].get(type_name, 0)
            lbl_val_b = QLabel(str(val_b))
            lbl_val_b.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_val_b.setStyleSheet(f"color: {color}; font-weight: bold;")
            self.stats_layout.addWidget(lbl_val_b, i+1, 3)

    def _clear_layout(self, layout):
        # Legacy method for backward compatibility - uses shared utility
        clear_layout(layout)

    def generate_ai_summary(self):
        if not self.current_game:
            return
        if not self.groq_service.client:
            QMessageBox.information(
                self,
                "LLM Not Configured",
                "No LLM provider is configured.\n\n"
                "Go to Settings → API Configuration and choose a provider:\n"
                "  • Groq (cloud, free tier available)\n"
                "  • LM Studio (local, no key required)\n"
                "  • MiniMax (cloud)\n"
                "  • Custom OpenAI-compatible endpoint\n\n"
                "Save your settings and try again.",
            )
            return
        self.btn_generate_summary.setEnabled(False)
        self.loading_overlay.start("Generating AI Summary...")
        logger.info("Starting AI summary generation...")
        self.summary_thread = GenerateSummaryThread(self.groq_service, self.current_game)
        self.summary_thread.finished.connect(self.on_summary_generated)
        self.summary_thread.start()
        
    def refresh_styles(self):
        """Re-applies styles to widgets."""
        if hasattr(self, 'btn_generate_summary'):
            self.btn_generate_summary.setStyleSheet(Styles.get_button_style())
            
        if hasattr(self, 'txt_ai_summary'):
            self.txt_ai_summary.setStyleSheet(f"""
                QTextEdit {{
                    background-color: {Styles.COLOR_SURFACE_LIGHT};
                    border: 1px solid {Styles.COLOR_BORDER};
                    border-radius: 8px;
                    padding: 10px;
                    color: {Styles.COLOR_TEXT_PRIMARY};
                }}
            """)
        
        # Refresh move list panel styles
        if hasattr(self, 'move_list_panel'):
            self.move_list_panel.refresh_styles()
        
        # Refresh summary stats colors if game is loaded
        if self.current_game:
            self._update_summary(self.current_game.summary)

    def on_summary_generated(self, summary):
        self.loading_overlay.stop()
        self.btn_generate_summary.setEnabled(True)
        self.btn_generate_summary.setText("Generate AI Summary")

        if is_error_message(summary):
            logger.error(f"AI Summary generation failed: {summary}")
            # Reset to "no summary yet" so the button reappears
            self.current_game.ai_summary = ""
            self.txt_ai_summary.setVisible(False)
            self.btn_generate_summary.setVisible(True)
            show_error_dialog(
                self,
                "AI Summary Failed",
                "Could not generate the AI summary.",
                summary,
            )
            return

        logger.info("AI Summary generated successfully.")
        self.current_game.ai_summary = summary
        self.txt_ai_summary.setText(summary)
        self.txt_ai_summary.setVisible(True)
        self.btn_generate_summary.setVisible(False)
        
    def resizeEvent(self, event):
        self.loading_overlay.resize(self.size())
        super().resizeEvent(event)

    def update_lines(self, lines, is_white):
        self.lines_widget.update_lines(lines, chess.WHITE if is_white else chess.BLACK)

class GenerateSummaryThread(QThread):
    finished = pyqtSignal(str)
    
    def __init__(self, service, game):
        super().__init__()
        self.service = service
        self.game = game
        
    def run(self):
        try:
            # Replay the moves onto a fresh board and export a valid PGN.
            # The previous inline string-concat produced invalid notation
            # like "b4 1. Nf6 c4 2. d5 …" because every move was prefixed
            # with its number regardless of side-to-move.
            import chess
            import chess.pgn
            from io import StringIO

            board = chess.Board()
            pgn_game = chess.pgn.Game()
            node = pgn_game
            for move in self.game.moves:
                chess_move = chess.Move.from_uci(move.uci) if move.uci else None
                if chess_move is None or chess_move not in board.legal_moves:
                    # Fall back to SAN parsing for moves without a UCI
                    try:
                        chess_move = board.parse_san(move.san)
                    except Exception:
                        continue
                node = node.add_variation(chess_move)
                board.push(chess_move)

            exporter = chess.pgn.StringExporter(
                headers=False, comments=False, variations=False
            )
            pgn_text = pgn_game.accept(exporter)
            if not pgn_text.strip():
                pgn_text = " ".join(m.san for m in self.game.moves)

            time_stats = format_time_stats_for_llm(self.game.moves)
            summary = self.service.generate_summary(
                pgn_text, str(self.game.summary), time_stats
            )
            self.finished.emit(summary)
        except Exception as e:
            logger.error(f"GenerateSummaryThread failed: {e}", exc_info=True)
            self.finished.emit(f"Error [{type(e).__name__}]: {e}")
