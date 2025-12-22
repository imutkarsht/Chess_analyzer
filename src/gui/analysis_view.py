from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, 
                             QHeaderView, QLabel, QGridLayout, QFrame, QHBoxLayout, 
                             QPushButton, QAbstractItemView, QCheckBox, QTabWidget, QSizePolicy)
from .graph_widget import GraphWidget
from PyQt6.QtCore import pyqtSignal, Qt, QTimer, QThread, QSize
from PyQt6.QtGui import QColor, QBrush, QFont, QIcon
from .styles import Styles
from .gui_utils import clear_layout, create_button
from .components import SimpleStatCard as StatCard
from .analysis import CapturedPiecesWidget, GameControlsWidget  # From analysis package
from ..utils.resources import ResourceManager
from ..utils.logger import logger
import chess
from .live_analysis import LiveAnalysisWorker
from ..backend.gemini_service import GeminiService
from PyQt6.QtWidgets import QTextEdit, QMessageBox, QInputDialog, QLineEdit
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
                border-radius: 8px;
                padding: 10px;
            }}
            QLabel {{ border: none; background: transparent; }}
        """)
        
        self.layout = QVBoxLayout(self)
        self.layout.setSpacing(8)
        self.layout.setContentsMargins(10, 10, 10, 10)
        
        self.rows = [] # List of (widget, lbl_depth, lbl_eval, lbl_pv) tuples
        self.lines_layout = QVBoxLayout()
        self.lines_layout.setSpacing(8)
        self.layout.addLayout(self.lines_layout)
        self.layout.addStretch() # Push lines to top

    def clear(self):
        """Clears all analysis lines."""
        for row_data in self.rows:
            row_data[0].hide()
        # We keep the widgets in self.rows to reuse them later, just hide them.
        
        # Or if we want to show a "No analysis" message
        # For now, just hiding is fine.

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
            
            # Eval
            score_val = pv_data.get("score_value", "?")
            display_score = score_val
            score_color = Styles.COLOR_TEXT_PRIMARY
            
            try:
                if not score_val.startswith("M"):
                    val = float(score_val)
                    if turn_color == chess.BLACK:
                        val = -val
                    display_score = f"{val:+.2f}"
                    
                    # Color coding
                    if val > 0.5: score_color = Styles.COLOR_BEST     # Greenish
                    elif val < -0.5: score_color = Styles.COLOR_BLUNDER # Redish
                    
            except:
                pass
                
            lbl_eval.setText(display_score)
            lbl_eval.setStyleSheet(f"color: {score_color}; font-weight: bold; font-family: monospace;")
            
            # PV
            pv_text = pv_data.get("pv_san", "")
            if not pv_text:
                pv_moves = pv_data.get("pv", [])
                pv_text = " ".join(pv_moves[:5]) 
            else:
                # Better truncation or wrapping
                # Just show as much as possible for now
                pass
            
            lbl_pv.setText(pv_text)

        # Hide unused rows
        for i in range(len(multi_pvs), len(self.rows)):
            self.rows[i][0].hide()

    def _create_row(self):
        row_widget = QWidget()
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(10)
        
        # Depth
        lbl_depth = QLabel("d0")
        lbl_depth.setFixedWidth(40)
        lbl_depth.setStyleSheet(f"color: {Styles.COLOR_TEXT_SECONDARY}; font-size: 11px;")
        row_layout.addWidget(lbl_depth)
        
        # Eval
        lbl_eval = QLabel("+0.00")
        lbl_eval.setFixedWidth(60)
        lbl_eval.setStyleSheet(f"color: {Styles.COLOR_TEXT_PRIMARY}; font-weight: bold;")
        lbl_eval.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        row_layout.addWidget(lbl_eval)
        
        # PV
        lbl_pv = QLabel("")
        lbl_pv.setStyleSheet(f"color: {Styles.COLOR_TEXT_SECONDARY};")
        lbl_pv.setWordWrap(True) # Wrap text
        lbl_pv.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
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
    
    def __init__(self, engine_path="stockfish"):
        super().__init__()
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(5)
        
        self.resource_manager = ResourceManager()
        self.current_game = None
        
        # Live Analysis
        self.engine_path = engine_path
        self.live_worker = LiveAnalysisWorker(self.engine_path)
        self.live_worker.info_ready.connect(self.on_live_analysis_update)
        self.live_worker.start()
        
        self.live_data = {}
        self.current_turn = chess.WHITE
        
        self.analysis_timer = QTimer()
        self.analysis_timer.setSingleShot(True)
        self.analysis_timer.setInterval(4000) # 4 seconds delay
        self.analysis_timer.timeout.connect(self.start_live_analysis)
        
        # Move List Table
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["#", "White", "Black"])
        
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(0, 40) # Reduced width
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.cellClicked.connect(self.on_cell_clicked)
        self.table.setIconSize(QSize(20, 20))
        
        # Tighter table styling
        self.table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {Styles.COLOR_SURFACE};
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 4px;
                gridline-color: {Styles.COLOR_BORDER};
            }}
            QTableWidget::item {{
                padding: 2px 4px; /* Reduced padding */
                border-bottom: 1px solid {Styles.COLOR_SURFACE_LIGHT};
            }}
            QTableWidget::item:selected {{
                background-color: {Styles.COLOR_HIGHLIGHT};
                color: {Styles.COLOR_TEXT_PRIMARY};
            }}
        """)
        
        self.layout.addWidget(self.table)
        
        # Stretch factors
        self.layout.setStretch(0, 1) # Table

    def set_game(self, game_analysis):
        self.current_game = game_analysis
        self.refresh()
        
    def refresh(self):
        if not self.current_game:
            self.table.setRowCount(0)
            return
            
        try:
            # Set row count
            num_rows = (len(self.current_game.moves) + 1) // 2
            self.table.setRowCount(num_rows)
            
            # Update vertical header labels (Move numbers)
            labels = [str(i+1) for i in range(num_rows)]
            self.table.setVerticalHeaderLabels(labels)
            
            for i, move in enumerate(self.current_game.moves):
                row = i // 2
                col = (i % 2) + 1 # 0->1 (White), 1->2 (Black)
                
                # Set Move Number for White moves
                if col == 1:
                    num_item = QTableWidgetItem(str(move.move_number))
                    num_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    num_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
                    num_item.setForeground(QBrush(QColor(Styles.COLOR_TEXT_SECONDARY)))
                    self.table.setItem(row, 0, num_item)
                    
                    # Clear Black cell (optional, but good for safety)
                    self.table.setItem(row, 2, None)
                
                self._set_move_item(row, col, move, i)
            
            self.table.viewport().update()
            
        except Exception as e:
            logger.error(f"Error refreshing move list: {e}", exc_info=True)

    def _set_move_item(self, row, col, move, index):
        item = QTableWidgetItem(move.san)
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        item.setData(Qt.ItemDataRole.UserRole, index)
        
        item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
        
        if move.classification:
            icon = self.resource_manager.get_icon(move.classification)
            if not icon.isNull():
                item.setIcon(icon)
        
        color = Styles.get_class_color(move.classification)
        if not color:
            color = Styles.COLOR_TEXT_PRIMARY
            
        item.setForeground(QBrush(QColor(color)))
             
        self.table.setItem(row, col, item)

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
        self.analysis_timer.start()

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
        self.live_worker = LiveAnalysisWorker(self.engine_path)
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
        api_key = self.config_manager.get("gemini_api_key")
        self.gemini_service = GeminiService(api_key)
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
        
        # Cache Checkbox
        self.cache_checkbox = QCheckBox("Use Analysis Cache")
        self.cache_checkbox.setChecked(True)
        self.cache_checkbox.toggled.connect(self.cache_toggled.emit)
        self.layout.addWidget(self.cache_checkbox)
        
        # Loading Overlay
        self.loading_overlay = LoadingOverlay(self)

    def set_game(self, game_analysis):
        logger.info(f"AnalysisPanel: Setting game {game_analysis.game_id if game_analysis else 'None'}")
        self.current_game = game_analysis
        self.refresh()
        
    def refresh(self):
        if not self.current_game:
            self.lines_widget.clear()
            return
            
        try:
            logger.info("AnalysisPanel: Refreshing UI...")
            self.lines_widget.clear() # Clear old lines initially or let live analysis fill them
            self.graph_widget.plot_game(self.current_game)
            
            logger.info(f"AnalysisPanel: Updating summary with keys: {self.current_game.summary.keys() if self.current_game.summary else 'None'}")
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
                icon_label.setPixmap(icon.pixmap(16, 16)) # Smaller icons
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
        if not self.gemini_service.model:
            # Prompt user for key
            key, ok = QInputDialog.getText(self, "Gemini API Key Required", 
                                         "To use AI Summary, please enter your Google Gemini API Key:\n(Get one at aistudio.google.com)",
                                         QLineEdit.EchoMode.Password)
            if ok and key:
                self.gemini_service.configure(key)
                if self.gemini_service.model:
                    self.config_manager.set("gemini_api_key", key)
                    QMessageBox.information(self, "Success", "API Key saved and Gemini configured!")
                else:
                    QMessageBox.critical(self, "Error", "Invalid API Key or configuration failed.")
                    return
            else:
                return
        self.btn_generate_summary.setEnabled(False)
        self.loading_overlay.start("Generating AI Summary...")
        logger.info("Starting AI summary generation...")
        self.summary_thread = GenerateSummaryThread(self.gemini_service, self.current_game)
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
        
        # Refresh summary stats colors if game is loaded
        if self.current_game:
            self._update_summary(self.current_game.summary)

    def on_summary_generated(self, summary):
        self.loading_overlay.stop()
        if summary.startswith("Error"):
            logger.error(f"AI Summary generation failed: {summary}")
        else:
            logger.info("AI Summary generated successfully.")
        self.current_game.ai_summary = summary
        self.txt_ai_summary.setText(summary)
        self.txt_ai_summary.setVisible(True)
        self.btn_generate_summary.setVisible(False)
        self.btn_generate_summary.setEnabled(True)
        self.btn_generate_summary.setText("Generate AI Summary")
        
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
            pgn_text = ""
            for move in self.game.moves:
                if move.move_number % 1 == 0 and move.ply % 2 != 0:
                     pgn_text += f"{move.move_number}. {move.san} "
                else:
                     pgn_text += f"{move.san} "
            summary = self.service.generate_summary(pgn_text, str(self.game.summary))
            self.finished.emit(summary)
        except Exception as e:
            logger.error(f"GenerateSummaryThread failed: {e}", exc_info=True)
            self.finished.emit(f"Error: {e}")
