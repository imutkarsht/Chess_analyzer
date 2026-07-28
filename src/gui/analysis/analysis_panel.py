"""
Analysis Panel - Coordinates evaluation graphs, stats summaries, and AI coach summaries.
"""
import chess
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFrame, QTabWidget, 
                             QSizePolicy, QLabel, QGridLayout, QPushButton, QTextEdit, QMessageBox, QDialog)
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
from src.utils.path_utils import get_resource_path
from src.backend.services.groq_service import GroqService
from src.gui.components.loading_widget import LoadingOverlay

from src.gui.components import CircularAccuracyWidget
from src.backend.storage.termination_detector import TerminationDetector


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
        self._analysis_running = False

        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        # Tabs
        self.tabs = QTabWidget()
        self.tabs.currentChanged.connect(self._on_tab_changed)
        self.layout.addWidget(self.tabs)
        
        # --- Tab 1: Evaluation ---
        self.eval_tab = QWidget()
        self.eval_tab.setStyleSheet("background: transparent;")
        self.eval_layout = QVBoxLayout(self.eval_tab)
        self.eval_layout.setContentsMargins(5, 5, 5, 5)
        
        # Graph
        self.graph_widget = GraphWidget()
        self.graph_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.eval_layout.addWidget(self.graph_widget, stretch=2)
        
        # Toggles
        toggles_layout = QHBoxLayout()
        toggles_layout.setContentsMargins(0, 6, 0, 6)
        toggles_layout.setSpacing(10)
        
        from PyQt6.QtWidgets import QCheckBox
        self.toggle_checkbox = QCheckBox("Engine Lines")
        self.toggle_checkbox.setChecked(False)
        self.toggle_checkbox.setCursor(Qt.CursorShape.PointingHandCursor)
        toggles_layout.addWidget(self.toggle_checkbox)
        
        self.cache_checkbox = QCheckBox("Use Cache")
        self.cache_checkbox.setChecked(True)
        self.cache_checkbox.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cache_checkbox.toggled.connect(self.cache_toggled.emit)
        toggles_layout.addWidget(self.cache_checkbox)
        toggles_layout.addStretch()
        self.eval_layout.addLayout(toggles_layout)
        self._apply_toggle_style()
        
        # Analysis Lines
        self.lines_widget = AnalysisLinesWidget()
        self.eval_layout.addWidget(self.lines_widget, stretch=1)
        
        self.tabs.addTab(self.eval_tab, "Evaluation")
        self._apply_tabs_style()
        
        # --- Tab 2: Report ---
        self.report_tab = QWidget()
        self.report_tab.setStyleSheet("background: transparent;")
        tab_layout = QVBoxLayout(self.report_tab)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        tab_layout.setSpacing(0)

        self.report_card = QFrame()
        self.report_card.setObjectName("ReportCard")
        tab_layout.addWidget(self.report_card)

        self.report_layout = QVBoxLayout(self.report_card)
        self.report_layout.setContentsMargins(12, 12, 12, 12)
        self.report_layout.setSpacing(10)

        # 1. Top Section: Hero Outcome Header
        self.hero_card = QFrame()
        self.hero_card.setStyleSheet(Styles.get_transparent_label_style())
        hero_layout = QVBoxLayout(self.hero_card)
        hero_layout.setContentsMargins(0, 0, 0, 0)
        hero_layout.setSpacing(2)

        self.result_banner_lbl = QLabel("-")
        self.result_banner_lbl.setStyleSheet(Styles.get_transparent_label_style())
        hero_layout.addWidget(self.result_banner_lbl)

        self.opening_label = QLabel("-")
        self.opening_label.setStyleSheet(
            Styles.get_label_style(size=12, weight=600) + " " + Styles.get_transparent_label_style()
        )
        self.opening_label.setWordWrap(True)
        hero_layout.addWidget(self.opening_label)

        self.details_label = QLabel("-")
        self.details_label.setStyleSheet(
            Styles.get_label_style(size=11, color=Styles.COLOR_TEXT_MUTED) + " " + Styles.get_transparent_label_style()
        )
        hero_layout.addWidget(self.details_label)

        self.report_layout.addWidget(self.hero_card)

        # Subtle divider 1
        self.div1 = QFrame()
        self.div1.setFrameShape(QFrame.Shape.HLine)
        self.div1.setStyleSheet(Styles.get_divider_style())
        self.report_layout.addWidget(self.div1)
        
        # 2. Accuracy Gauges (Side by side White & Black)
        self.accuracy_frame = QFrame()
        self.accuracy_frame.setStyleSheet(Styles.get_transparent_label_style())
        self.accuracy_layout = QHBoxLayout(self.accuracy_frame)
        self.accuracy_layout.setContentsMargins(0, 4, 0, 4)
        self.accuracy_layout.setSpacing(16)

        self.w_circular_acc = CircularAccuracyWidget(side="White", accuracy=0.0, acpl=None)
        self.b_circular_acc = CircularAccuracyWidget(side="Black", accuracy=0.0, acpl=None)
        self.accuracy_layout.addWidget(self.w_circular_acc)
        self.accuracy_layout.addWidget(self.b_circular_acc)

        self.report_layout.addWidget(self.accuracy_frame)

        # Subtle divider 2
        self.div2 = QFrame()
        self.div2.setFrameShape(QFrame.Shape.HLine)
        self.div2.setStyleSheet(Styles.get_divider_style())
        self.report_layout.addWidget(self.div2)
        
        # 3. Move Quality Classification Table
        self.stats_frame = QFrame()
        self.stats_frame.setStyleSheet(Styles.get_transparent_label_style())
        self.stats_layout = QGridLayout(self.stats_frame)
        self.stats_layout.setSpacing(4)
        self.stats_layout.setContentsMargins(0, 4, 0, 4)
        self.report_layout.addWidget(self.stats_frame)

        # Subtle divider 3
        self.div3 = QFrame()
        self.div3.setFrameShape(QFrame.Shape.HLine)
        self.div3.setStyleSheet(Styles.get_divider_style())
        self.report_layout.addWidget(self.div3)
        
        # 4. AI Coach Summary (Takes remaining vertical height)
        self.ai_summary_frame = QFrame()
        self.ai_summary_layout = QVBoxLayout(self.ai_summary_frame)
        self.ai_summary_layout.setContentsMargins(0, 4, 0, 0)
        self.ai_summary_layout.setSpacing(6)
        
        self.btn_generate_summary = QPushButton(" ✨  Generate AI coach summary")
        self.btn_generate_summary.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_generate_summary.setFixedHeight(34)
        self.btn_generate_summary.setStyleSheet(Styles.get_outline_button_style())
        self.btn_generate_summary.clicked.connect(self.generate_ai_summary)
        self.ai_summary_layout.addWidget(self.btn_generate_summary)
        
        self.txt_ai_summary = QTextEdit()
        self.txt_ai_summary.setReadOnly(True)
        self.txt_ai_summary.setPlaceholderText("AI Coach summary & key takeaways will appear here...")
        self.txt_ai_summary.setStyleSheet(Styles.get_text_edit_style())
        self.txt_ai_summary.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.ai_summary_layout.addWidget(self.txt_ai_summary)
        
        self.report_layout.addWidget(self.ai_summary_frame, stretch=1)
        
        self.tabs.addTab(self.report_tab, "Report")
        
        # Loading Overlay
        self.loading_overlay = LoadingOverlay(self)

    def set_analysis_running(self, running: bool):
        self._analysis_running = running

    def _on_tab_changed(self, index):
        if self._analysis_running and index == 1:
            self.tabs.setCurrentIndex(0)

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

            meta = self.current_game.metadata
            w_name = meta.white or "White"
            b_name = meta.black or "Black"

            # Result Header
            term_mode, term_desc = TerminationDetector.detect_termination(
                headers={"Result": meta.result, "White": w_name, "Black": b_name, "Termination": meta.termination or ""},
                moves=getattr(self.current_game, "moves", []) or [],
                starting_fen=meta.starting_fen
            )

            res_color = self._get_result_color(meta)

            self.result_banner_lbl.setText(f"<span style='color: {res_color}; font-weight: 800; font-size: 13px;'>{meta.result}</span> &nbsp;<span style='color: {Styles.COLOR_TEXT_SECONDARY}; font-size: 12px; font-weight: 500;'>{term_desc}</span>")

            # Opening & details section
            opening = meta.opening or "Unknown Opening"
            self.opening_label.setText(opening)

            speed_cat = getattr(meta, "speed_category", "")
            num_moves = (len(self.current_game.moves) + 1) // 2 if hasattr(self.current_game, 'moves') and self.current_game.moves else 0
            
            details_parts = []
            if speed_cat:
                details_parts.append(speed_cat)
            if num_moves:
                details_parts.append(f"{num_moves} moves")

            if details_parts:
                self.details_label.setText("  •  ".join(details_parts))
                self.details_label.setVisible(True)
            else:
                self.details_label.setVisible(False)
            
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

    def _get_result_color(self, meta):
        chesscom = self.config_manager.get("chesscom_username", "")
        lichess = self.config_manager.get("lichess_username", "")
        usernames = [u.lower() for u in [chesscom, lichess] if u]

        w_name = (meta.white or "").lower()
        b_name = (meta.black or "").lower()

        user_is_white = w_name in usernames if w_name else False
        user_is_black = b_name in usernames if b_name else False

        if meta.result == "1-0":
            if user_is_black:
                return Styles.COLOR_BLUNDER
            return Styles.COLOR_BEST
        elif meta.result == "0-1":
            if user_is_white:
                return Styles.COLOR_BLUNDER
            return Styles.COLOR_BEST

        return Styles.COLOR_TEXT_PRIMARY

    def _update_summary(self, summary):
        clear_layout(self.stats_layout)
        
        if not summary or "white" not in summary:
            self.w_circular_acc.set_data(0.0, None)
            self.b_circular_acc.set_data(0.0, None)
            return

        w_acc = summary['white'].get('accuracy', 0.0)
        b_acc = summary['black'].get('accuracy', 0.0)
        w_acpl = summary['white'].get('acpl', None)
        b_acpl = summary['black'].get('acpl', None)

        self.w_circular_acc.set_data(w_acc, w_acpl)
        self.b_circular_acc.set_data(b_acc, b_acpl)
        
        # Stats Grid Header
        self.stats_layout.addWidget(QLabel(""), 0, 0)
        lbl_w = QLabel("White")
        lbl_w.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_w.setStyleSheet(Styles.get_label_style(bold=True))
        self.stats_layout.addWidget(lbl_w, 0, 1)
        
        self.stats_layout.addWidget(QLabel(""), 0, 2)
        
        lbl_b = QLabel("Black")
        lbl_b.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_b.setStyleSheet(Styles.get_label_style(bold=True))
        self.stats_layout.addWidget(lbl_b, 0, 3)
        
        types = ["Brilliant", "Great", "Best", "Excellent", "Good", "Book", "Inaccuracy", "Mistake", "Miss", "Blunder"]
        
        for i, type_name in enumerate(types):
            color = Styles.get_class_color(type_name)
            bg_tint = f"{color}15"

            # Create row container widget for subtle background tint
            row_frame = QFrame()
            row_frame.setStyleSheet(f"background-color: {bg_tint}; border-radius: 4px;")
            row_layout = QHBoxLayout(row_frame)
            row_layout.setContentsMargins(6, 2, 6, 2)

            lbl_type = QLabel(type_name)
            lbl_type.setStyleSheet(
                Styles.get_label_style(size=12, color=color, bold=True) + " " + Styles.get_transparent_label_style()
            )
            self.stats_layout.addWidget(lbl_type, i+1, 0)
            
            val_w = summary['white'].get(type_name, 0)
            lbl_val_w = QLabel(str(val_w))
            lbl_val_w.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_val_w.setStyleSheet(
                Styles.get_label_style(color=color, bold=True) + " " + Styles.get_transparent_label_style()
            )
            self.stats_layout.addWidget(lbl_val_w, i+1, 1)
            
            icon_label = QLabel()
            icon = self.resource_manager.get_icon(type_name)
            if not icon.isNull():
                icon_label.setPixmap(icon.pixmap(20, 20))
                icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            else:
                icon_label.setText("-")
            icon_label.setStyleSheet(Styles.get_transparent_label_style())
            self.stats_layout.addWidget(icon_label, i+1, 2)
            
            val_b = summary['black'].get(type_name, 0)
            lbl_val_b = QLabel(str(val_b))
            lbl_val_b.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_val_b.setStyleSheet(
                Styles.get_label_style(color=color, bold=True) + " " + Styles.get_transparent_label_style()
            )
            self.stats_layout.addWidget(lbl_val_b, i+1, 3)

    def _clear_layout(self, layout):
        # Legacy method for backward compatibility - uses shared utility
        clear_layout(layout)

    def generate_ai_summary(self):
        if not self.current_game:
            return
        if not self.groq_service.client:
            from ..dialogs.llm_error_dialog import LlmNotConfiguredDialog
            dlg = LlmNotConfiguredDialog(self)
            if dlg.exec() == QDialog.DialogCode.Accepted and dlg.wants_configure():
                window = self.window()
                if hasattr(window, "sidebar") and hasattr(window, "switch_page"):
                    window.sidebar.set_active(4)
                    window.switch_page(4)
            return
        self.btn_generate_summary.setEnabled(False)
        self.loading_overlay.start("Generating AI Summary...")
        logger.info("Starting AI summary generation...")
        self.summary_thread = GenerateSummaryThread(self.groq_service, self.current_game)
        self.summary_thread.finished.connect(self.on_summary_generated)
        self.summary_thread.start()
        
    def refresh_styles(self):
        """Re-applies styles to widgets."""
        self.setStyleSheet(Styles.get_background_style())

        if hasattr(self, 'report_card') and self.report_card:
            self.report_card.setStyleSheet(Styles.get_frame_style(object_name="ReportCard", hover_accent=False))

        if hasattr(self, 'opening_label') and self.opening_label:
            self.opening_label.setStyleSheet(
                Styles.get_label_style(size=12, weight=600) + " " + Styles.get_transparent_label_style()
            )

        if hasattr(self, 'details_label') and self.details_label:
            self.details_label.setStyleSheet(
                Styles.get_label_style(size=11, color=Styles.COLOR_TEXT_MUTED) + " " + Styles.get_transparent_label_style()
            )

        if hasattr(self, 'w_circular_acc'):
            self.w_circular_acc.refresh_styles()
        if hasattr(self, 'b_circular_acc'):
            self.b_circular_acc.refresh_styles()

        for div_name in ('div1', 'div2', 'div3'):
            if hasattr(self, div_name):
                getattr(self, div_name).setStyleSheet(Styles.get_divider_style())

        if hasattr(self, 'btn_generate_summary'):
            self.btn_generate_summary.setStyleSheet(Styles.get_outline_button_style())
            
        if hasattr(self, 'txt_ai_summary'):
            self.txt_ai_summary.setStyleSheet(Styles.get_text_edit_style())

        if hasattr(self, 'graph_widget'):
            self.graph_widget.refresh_styles()

        self._apply_toggle_style()

        if hasattr(self, 'tabs'):
            self.tabs.setStyleSheet(Styles.get_tab_style())

        if hasattr(self, 'lines_widget'):
            self.lines_widget.refresh_styles()

        if hasattr(self, 'move_list_panel'):
            self.move_list_panel.refresh_styles()
        
        if self.current_game:
            self._update_summary(self.current_game.summary)

    def _apply_toggle_style(self):
        tick_path = get_resource_path("assets/images/tick.svg").replace("\\", "/")
        cb_style = Styles.get_checkbox_style(tick_path)
        if hasattr(self, 'toggle_checkbox'):
            self.toggle_checkbox.setStyleSheet(cb_style)
        if hasattr(self, 'cache_checkbox'):
            self.cache_checkbox.setStyleSheet(cb_style)

    def _apply_tabs_style(self):
        """Applies the themed QTabWidget stylesheet."""
        self.tabs.setStyleSheet(Styles.get_tab_style())

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
            if "not configured" in summary.lower():
                from ..dialogs.llm_error_dialog import LlmNotConfiguredDialog
                dlg = LlmNotConfiguredDialog(self)
                if dlg.exec() == QDialog.DialogCode.Accepted and dlg.wants_configure():
                    window = self.window()
                    if hasattr(window, "sidebar") and hasattr(window, "switch_page"):
                        window.sidebar.set_active(4)
                        window.switch_page(4)
            else:
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
