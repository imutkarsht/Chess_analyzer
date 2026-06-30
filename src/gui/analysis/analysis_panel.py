"""
Analysis Panel - Coordinates evaluation graphs, stats summaries, and AI coach summaries.
"""
import chess
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFrame, QTabWidget, 
                             QSizePolicy, QLabel, QGridLayout, QPushButton, QTextEdit, QMessageBox)
from PyQt6.QtCore import pyqtSignal, Qt, QThread
from src.gui.styles import Styles
from src.gui.utils.gui_utils import (clear_layout, show_error_dialog, is_error_message, 
                                     format_time_stats_for_llm)
from src.gui.components import SimpleStatCard as StatCard
from src.gui.components.graph_widget import GraphWidget
from .analysis_lines_widget import AnalysisLinesWidget
from src.utils.resources import ResourceManager
from src.utils.logger import logger
from src.utils.config import ConfigManager
from src.backend.services.groq_service import GroqService
from src.gui.components.loading_widget import LoadingOverlay

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
        self.summary_thread = None
        
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
        
        # Toggles
        toggles_layout = QHBoxLayout()
        toggles_layout.setContentsMargins(0, 5, 0, 5)
        
        from PyQt6.QtWidgets import QCheckBox
        self.toggle_checkbox = QCheckBox("Engine Lines")
        self.toggle_checkbox.setChecked(False)
        self.toggle_checkbox.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_checkbox.setStyleSheet(f"""
            QCheckBox {{
                color: {Styles.COLOR_TEXT_PRIMARY};
                font-weight: bold;
                font-size: 13px;
                background: transparent;
                border: none;
            }}
        """)
        toggles_layout.addWidget(self.toggle_checkbox)
        
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
        """)
        self.cache_checkbox.toggled.connect(self.cache_toggled.emit)
        toggles_layout.addWidget(self.cache_checkbox)
        toggles_layout.addStretch()
        self.eval_layout.addLayout(toggles_layout)
        
        # Analysis Lines
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
        self.opening_label.setWordWrap(True)
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

            is_chess960 = self.game.metadata.chess960
            if self.game.metadata.starting_fen:
                board = chess.Board(self.game.metadata.starting_fen, chess960=is_chess960)
            else:
                board = chess.Board(chess960=is_chess960)
            pgn_game = chess.pgn.Game()
            if self.game.metadata.starting_fen:
                pgn_game.headers["SetUp"] = "1"
                pgn_game.headers["FEN"] = self.game.metadata.starting_fen
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
