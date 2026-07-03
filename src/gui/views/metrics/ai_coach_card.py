import os
import json
import re
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea, QFrame, QSizePolicy, QDialog
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from src.gui.views.metrics.base_card import MetricCard
from src.gui.styles import Styles
from src.gui.utils.gui_utils import resolve_asset, clear_layout, show_error_dialog
from src.gui.metrics.workers import InsightWorker

class AICoachCard(MetricCard):
    def __init__(self, groq_service, parent=None):
        self.groq_service = groq_service
        self.stats = None
        self.worker = None
        self.current_insights = None
        
        self.btn_refresh_insights = QPushButton("↻")
        self.btn_refresh_insights.setFixedSize(32, 32)
        self.btn_refresh_insights.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_refresh_insights.setToolTip("Refresh AI Insights")
        self.btn_refresh_insights.setStyleSheet(f"""
            QPushButton {{
                background-color: {Styles.COLOR_ACCENT};
                color: {Styles.COLOR_TEXT_PRIMARY};
                border-radius: 16px;
                border: none;
                font-size: 18px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {Styles.COLOR_ACCENT_HOVER};
            }}
        """)
        self.btn_refresh_insights.clicked.connect(self._generate_insights)
        
        super().__init__("AI Coach Insights", parent=parent, action_widget=self.btn_refresh_insights, min_height=400)
        self.setup_ui()

    def setup_ui(self):
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical {
                background: transparent; width: 6px; margin: 0;
            }
            QScrollBar::handle:vertical {
                background: rgba(255,255,255,0.15); border-radius: 3px; min-height: 20px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)

        self.insights_container = QWidget()
        self.insights_container.setStyleSheet("background: transparent;")
        self.insights_container.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self.insights_layout = QVBoxLayout(self.insights_container)
        self.insights_layout.setSpacing(15)
        self.insights_layout.setContentsMargins(10, 10, 10, 10)
        self.insights_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        lbl_placeholder = QLabel("Analysis ready. Click refresh to get insights.")
        lbl_placeholder.setStyleSheet(f"color: {Styles.COLOR_TEXT_SECONDARY}; font-style: italic;")
        lbl_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.insights_layout.addWidget(lbl_placeholder)

        for _ in range(3):
            line = QFrame()
            line.setFixedHeight(12)
            line.setStyleSheet(f"background-color: {Styles.COLOR_SURFACE_LIGHT}; border-radius: 6px;")
            self.insights_layout.addWidget(line)

        self.scroll.setWidget(self.insights_container)
        self.set_content(self.scroll)

    def set_stats(self, stats):
        self.stats = stats

    def set_insights(self, insight_text):
        self._populate_insights(insight_text)

    def get_insights(self):
        return self.current_insights

    def _generate_insights(self):
        if not self.stats:
            return
            
        clear_layout(self.insights_layout)
        
        lbl_loading = QLabel("Asking Coach Groq...")
        lbl_loading.setStyleSheet(f"color: {Styles.COLOR_TEXT_PRIMARY};")
        lbl_loading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.insights_layout.addWidget(lbl_loading)
        
        stats_str = json.dumps(self.stats, indent=2)
        
        if self.worker is not None and self.worker.isRunning():
            try:
                self.worker.finished.disconnect()
                self.worker.error.disconnect()
            except (TypeError, RuntimeError):
                pass
            self.worker.quit()
            self.worker.wait()

        self.worker = InsightWorker(self.groq_service, stats_str)
        self.worker.finished.connect(self._populate_insights)
        self.worker.error.connect(self._handle_insight_error)
        self.worker.start()

    def _handle_insight_error(self, err_msg):
        clear_layout(self.insights_layout)
        lbl_err = QLabel(f"Error: {err_msg}")
        lbl_err.setStyleSheet(f"color: {Styles.COLOR_BLUNDER};")
        lbl_err.setWordWrap(True)
        lbl_err.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        self.insights_layout.addWidget(lbl_err)

        btn_retry = QPushButton("Retry")
        btn_retry.setStyleSheet(Styles.get_button_style())
        btn_retry.clicked.connect(self._generate_insights)
        self.insights_layout.addWidget(btn_retry)

        if "not configured" in err_msg.lower():
            from ...dialogs.llm_error_dialog import LlmNotConfiguredDialog
            dlg = LlmNotConfiguredDialog(self)
            if dlg.exec() == QDialog.DialogCode.Accepted and dlg.wants_configure():
                window = self.window()
                if hasattr(window, "sidebar") and hasattr(window, "switch_page"):
                    window.sidebar.set_active(4)
                    window.switch_page(4)
        else:
            show_error_dialog(
                self,
                "AI Coach Insights Failed",
                "Could not generate AI insights. See the insight card and "
                "the details below for the full error.",
                err_msg,
            )
        
    def _populate_insights(self, insight_text):
        self.current_insights = insight_text
        clear_layout(self.insights_layout)
        
        def add_insight(icon, text):
            row = QHBoxLayout()
            row.setSpacing(15)
            row.setAlignment(Qt.AlignmentFlag.AlignTop)
            
            icon_path = None
            if icon.endswith(".png") or icon.endswith(".svg"):
                icon_path = resolve_asset(icon)
            else:
                icon_path = resolve_asset(f"{icon}.png")
                if not icon_path:
                    icon_path = resolve_asset(f"{icon}.svg")
            
            if icon_path and os.path.exists(icon_path):
                lbl_icon = QLabel()
                pixmap = QPixmap(icon_path)
                if not pixmap.isNull():
                    pixmap = pixmap.scaled(24, 24, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                    lbl_icon.setPixmap(pixmap)
                    lbl_icon.setStyleSheet("border: none; background: transparent;")
                    icon_container = QWidget()
                    icon_container.setFixedWidth(30)
                    icon_layout = QVBoxLayout(icon_container)
                    icon_layout.setContentsMargins(0,0,0,0)
                    icon_layout.addWidget(lbl_icon, alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
                    row.addWidget(icon_container)
                else:
                    lbl_icon = QLabel("💡") 
                    lbl_icon.setStyleSheet(f"color: {Styles.COLOR_ACCENT}; font-size: 20px; border: none; background: transparent;")
                    row.addWidget(lbl_icon)
            else:
                lbl_icon = QLabel("💡")
                lbl_icon.setStyleSheet(f"color: {Styles.COLOR_ACCENT}; font-size: 20px; border: none; background: transparent;")
                row.addWidget(lbl_icon)
 
            clean_text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
            clean_text = clean_text.strip('"').strip("'")
            clean_text = re.sub(r'[^\x00-\x7F]+', '', clean_text).strip()
            
            if clean_text and clean_text[0].islower():
                clean_text = clean_text[0].upper() + clean_text[1:]

            lbl_text = QLabel(clean_text)
            lbl_text.setWordWrap(True)
            lbl_text.setStyleSheet(f"color: {Styles.COLOR_TEXT_SECONDARY}; font-size: 13px; line-height: 1.4; border: none; background: transparent;")
            row.addWidget(lbl_text, stretch=1)
            
            self.insights_layout.addLayout(row)
        
        lines = insight_text.split('\n')
        count = 0
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            is_item = False
            content = line
            
            if line[0].isdigit() and ('.' in line[:4] or ')' in line[:4]):
                parts = line.split('.', 1)
                if len(parts) > 1:
                    content = parts[1].strip()
                else:
                    content = line.split(')', 1)[-1].strip()
                is_item = True
            elif line.startswith('- ') or line.startswith('* '):
                content = line[2:].strip()
                is_item = True
            
            if len(content) > 20: 
                lower_text = content.lower()
                icon = "idea"
                
                if "opening" in lower_text:
                    icon = "opening_icon.png"
                elif any(x in lower_text for x in ["endgame", "mate", "queen"]):
                    icon = "phase_icon.png"
                elif any(x in lower_text for x in ["accuracy", "precision", "blunder"]):
                    icon = "accuracy.png"
                elif any(x in lower_text for x in ["win", "momentum", "streak", "victory"]):
                    icon = "win_rate.png"
                elif any(x in lower_text for x in ["best", "great", "brilliant"]):
                    icon = "best_v2.svg"
                
                add_insight(icon, content)
                count += 1
        
        if count == 0:
            add_insight("idea", insight_text)
