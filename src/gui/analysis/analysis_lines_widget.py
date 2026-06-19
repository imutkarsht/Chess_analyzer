"""
Analysis Lines Widget - Renders candidate lines from the engine.
"""
import chess
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QVBoxLayout, QCheckBox, QWidget, QLabel, QSizePolicy
from PyQt6.QtCore import Qt
from ..styles import Styles

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
        
        # Bottom row layout for evaluation and depth badges
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
