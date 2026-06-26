"""
Analysis Lines Widget - Renders candidate lines from the engine.
"""
import chess
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QVBoxLayout, QCheckBox, QWidget, QLabel, QSizePolicy
from PyQt6.QtCore import Qt, pyqtSignal
from ..styles import Styles
from src.utils.logger import logger

class AnalysisRowWidget(QWidget):
    clicked = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.uci_move = None
        
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.uci_move:
            self.clicked.emit(self.uci_move)

class AnalysisLinesWidget(QFrame):
    line_clicked = pyqtSignal(str)
    
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
        
        # No header layout here anymore

        
        self.rows = [] # List of (widget, lbl_depth, lbl_eval, lbl_pv) tuples
        self.lines_layout = QVBoxLayout()
        self.lines_layout.setSpacing(6)
        self.layout.addLayout(self.lines_layout)
        self.layout.addStretch() # Push lines to top

    def clear(self):
        """Clears all analysis lines."""
        for row_data in self.rows:
            row_data[0].hide()

    def _remove_excess_rows(self, target_count):
        """Remove excess row widgets when the row count exceeds target_count."""
        while len(self.rows) > target_count:
            row_widget, _, _, _ = self.rows.pop()
            self.lines_layout.removeWidget(row_widget)
            row_widget.deleteLater()

    def _format_pv_to_html(self, pv_text: str) -> str:
        if not pv_text:
            return ""
        words = pv_text.split()
        html_words = []
        first_move = True
        for word in words:
            if not word:
                continue
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
            
            # Clickable move logic
            if pv_data.get("pv_uci"):
                row_widget.uci_move = pv_data["pv_uci"][0]
            else:
                row_widget.uci_move = None
                
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
            score_val = pv_data.get("score_value")
            display_score = score_val if score_val else "--"
            bg_color = Styles.COLOR_SURFACE_LIGHT
            text_color = Styles.COLOR_TEXT_PRIMARY

            if score_val is not None:
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
                except Exception as e:
                    logger.warning(f"Failed to format eval score '{score_val}': {e}")

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

        # Hide unused rows and remove excess to prevent memory leak
        if len(multi_pvs) < len(self.rows):
            for i in range(len(multi_pvs), len(self.rows)):
                self.rows[i][0].hide()
            # Trim rows if more than 2 are unused (avoid churn on small fluctuations)
            if len(self.rows) - len(multi_pvs) > 2:
                self._remove_excess_rows(len(multi_pvs))

    def _create_row(self):
        row_widget = AnalysisRowWidget()
        row_widget.clicked.connect(self.line_clicked.emit)
        row_widget.setObjectName("AnalysisRow")
        row_layout = QVBoxLayout(row_widget)
        row_layout.setContentsMargins(8, 8, 8, 8)
        row_layout.setSpacing(6)
        
        # Bottom row layout for evaluation and depth badges
        top_layout = QHBoxLayout()
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(8)
        
        # Eval Badge
        lbl_eval = QLabel("+0.00")
        lbl_eval.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        lbl_eval.setFixedWidth(65)
        lbl_eval.setAlignment(Qt.AlignmentFlag.AlignCenter)
        top_layout.addWidget(lbl_eval, alignment=Qt.AlignmentFlag.AlignVCenter)

        # Depth Badge
        lbl_depth = QLabel("d0")
        lbl_depth.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        lbl_depth.setFixedWidth(40)
        lbl_depth.setAlignment(Qt.AlignmentFlag.AlignCenter)
        top_layout.addWidget(lbl_depth, alignment=Qt.AlignmentFlag.AlignVCenter)
        
        top_layout.addStretch()
        row_layout.addLayout(top_layout)
        
        # PV Move sequence line (rendered below the badges)
        lbl_pv = QLabel("")
        lbl_pv.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        lbl_pv.setWordWrap(True) # Wrap text
        lbl_pv.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        lbl_pv.setStyleSheet(f"font-size: 12px; color: {Styles.COLOR_TEXT_PRIMARY};")
        row_layout.addWidget(lbl_pv)
        
        self.lines_layout.addWidget(row_widget)
        self.rows.append((row_widget, lbl_depth, lbl_eval, lbl_pv))
