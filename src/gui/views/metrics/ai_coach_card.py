"""
AI Coach Insights Card.
Generates clean, structured coaching diagnostics from aggregated metrics,
highlighting Strengths & Superpowers, Critical Leaks, and a Personalized Training Prescription.
Open, modern design with zero nested box clutter.
"""

from __future__ import annotations

import re
from typing import Any

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.backend.analysis.metrics_aggregator import MetricsAggregator
from src.gui.components import Button, ButtonSize, ButtonVariant
from src.gui.components.pulsing_skeleton import PulsingSkeleton
from src.gui.metrics.workers import InsightWorker
from src.gui.styles import Styles
from src.gui.utils.gui_utils import clear_layout, create_button, show_error_dialog
from src.gui.views.metrics.base_card import MetricCard


class AICoachCard(MetricCard):
    """
    Card displaying AI Coaching diagnostics:
    - Strengths & Superpowers (Tactics, prep, endgame accuracy)
    - Critical Leaks & Blindspots (Piece hangs, clock panic, rushing in Rapid, dropped leads)
    - Personalized Training Prescription (Concrete practice routines)
    """

    insights_generated = pyqtSignal(str)

    def __init__(self, groq_service: Any, parent=None):
        self.groq_service = groq_service
        self.stats: dict[str, Any] = {}
        self.worker: InsightWorker | None = None
        self.current_insights: str | None = None
        self._skeleton: PulsingSkeleton | None = None

        # Action widget container in card header
        self.header_action_widget = QWidget()
        self.header_action_widget.setStyleSheet("background: transparent;")
        header_act_layout = QHBoxLayout(self.header_action_widget)
        header_act_layout.setContentsMargins(0, 0, 0, 0)
        header_act_layout.setSpacing(8)

        # Provider / Model status badge
        self.provider_badge = QLabel("AI Coach")
        self.provider_badge.setStyleSheet(f"""
            background-color: {Styles.COLOR_SURFACE_LIGHT};
            color: {Styles.COLOR_TEXT_SECONDARY};
            font-size: 11px;
            font-weight: 600;
            border: 1px solid {Styles.COLOR_BORDER};
            border-radius: 6px;
            padding: 3px 8px;
        """)
        header_act_layout.addWidget(self.provider_badge)

        # Refresh / Generate button
        self.btn_refresh_insights = Button(
            variant=ButtonVariant.FILLED,
            size=ButtonSize.SM,
            icon="fa5s.sync-alt",
            icon_position="only",
            tooltip="Generate / Refresh AI Coaching",
            on_click=self._generate_insights,
        )
        self.btn_refresh_insights.setFixedSize(28, 28)
        header_act_layout.addWidget(self.btn_refresh_insights)

        super().__init__(
            "AI Coach Insights",
            parent=parent,
            action_widget=self.header_action_widget,
            min_height=380,
        )
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
        self.insights_layout.setSpacing(16)
        self.insights_layout.setContentsMargins(6, 6, 6, 8)
        self.insights_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.scroll.setWidget(self.insights_container)
        self.set_content(self.scroll)
        self._show_initial_state()

    def set_stats(self, stats: dict[str, Any]):
        self.stats = stats or {}
        self._update_provider_badge()
        if not self.current_insights:
            self._show_initial_state()

    def set_insights(self, insight_text: str):
        if not insight_text:
            return
        self._stop_skeleton_anim()
        self.current_insights = insight_text
        self._populate_insights(insight_text)

    def get_insights(self) -> str | None:
        return self.current_insights

    def _update_provider_badge(self):
        """Reflect active provider and model in header badge without pretension."""
        if hasattr(self.groq_service, "get_model_name"):
            model = self.groq_service.get_model_name()
            if model:
                short_model = model.split("/")[-1].replace(":latest", "")
                self.provider_badge.setText(short_model)
                return
        self.provider_badge.setText("AI Coach")

    def _stop_skeleton_anim(self):
        """Safely stops and removes the pulsing placeholder."""
        skeleton, self._skeleton = self._skeleton, None
        if skeleton is not None:
            skeleton.stop()
            skeleton.deleteLater()

    def _show_initial_state(self):
        self._stop_skeleton_anim()
        clear_layout(self.insights_layout)
        total = self.stats.get("total", 0)

        intro_container = QWidget()
        intro_container.setObjectName("coach_intro_container")
        intro_container.setStyleSheet("background: transparent;")
        vbox = QVBoxLayout(intro_container)
        vbox.setContentsMargins(16, 24, 16, 24)
        vbox.setSpacing(10)
        vbox.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel("Performance Diagnosis")
        title.setStyleSheet(
            f"color: {Styles.COLOR_TEXT_PRIMARY}; font-size: 16px; font-weight: 700; background: transparent;"
        )
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        vbox.addWidget(title)

        desc = QLabel(
            f"Synthesizes {total} analyzed games across tactical blindspots, conversion, and clock discipline."
            if total > 0
            else "Analyze your games to receive tailored coaching insights and practice recommendations."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet(
            f"color: {Styles.COLOR_TEXT_SECONDARY}; font-size: 13px; background: transparent;"
        )
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        vbox.addWidget(desc)

        vbox.addSpacing(10)

        btn_analyze = create_button(
            "Generate Coach Insights",
            style="primary",
            on_click=self._generate_insights,
            icon_name="fa5s.robot",
        )
        btn_analyze.setFixedWidth(220)
        btn_analyze.setFixedHeight(38)
        btn_analyze.setEnabled(total > 0)
        vbox.addWidget(btn_analyze, alignment=Qt.AlignmentFlag.AlignCenter)

        self.insights_layout.addWidget(intro_container)

    def refresh_styles(self):
        self.provider_badge.setStyleSheet(f"""
            background-color: {Styles.COLOR_SURFACE_LIGHT};
            color: {Styles.COLOR_TEXT_SECONDARY};
            font-size: 11px;
            font-weight: 600;
            border: 1px solid {Styles.COLOR_BORDER};
            border-radius: 6px;
            padding: 3px 8px;
        """)
        self.btn_refresh_insights.setStyleSheet(f"""
            QPushButton {{
                background-color: {Styles.COLOR_SURFACE_LIGHT};
                color: {Styles.COLOR_TEXT_PRIMARY};
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 6px;
            }}
            QPushButton:hover {{
                background-color: {Styles.COLOR_SURFACE};
                border-color: {Styles.COLOR_ACCENT};
            }}
        """)
        try:
            import qtawesome as qta

            self.btn_refresh_insights.setIcon(
                qta.icon("fa5s.sync-alt", color=Styles.COLOR_TEXT_SECONDARY)
            )
        except ImportError:
            pass

        super().refresh_styles()
        if self.current_insights:
            self._populate_insights(self.current_insights)
        else:
            self._show_initial_state()

    def _show_loading_skeleton(self):
        """Displays the shared pulsing placeholder while AI generates insights."""
        self._stop_skeleton_anim()
        clear_layout(self.insights_layout)

        self._skeleton = PulsingSkeleton(
            title="AI Coach is analyzing performance patterns...",
            subtitle="Synthesizing tactical motifs, advantage conversion, and clock discipline...",
            parent=self.insights_container,
        )
        self.insights_layout.addWidget(self._skeleton)
        self._skeleton.start()

    def _generate_insights(self):
        if not self.stats or self.stats.get("total", 0) == 0:
            return

        self._show_loading_skeleton()

        # Build clean high-density coach dossier
        dossier_text = MetricsAggregator.build_coach_dossier(self.stats)

        if self.worker is not None and self.worker.isRunning():
            try:
                self.worker.finished.disconnect()
                self.worker.error.disconnect()
            except (TypeError, RuntimeError):
                pass
            self.worker.quit()
            self.worker.wait(1000)

        self.worker = InsightWorker(self.groq_service, dossier_text)
        self.worker.finished.connect(self._on_worker_finished)
        self.worker.error.connect(self._handle_insight_error)
        self.worker.start()

    def _on_worker_finished(self, insight_text: str):
        self._stop_skeleton_anim()
        self.current_insights = insight_text
        self.insights_generated.emit(insight_text)
        self._populate_insights(insight_text)

    def _handle_insight_error(self, err_msg: str):
        self._stop_skeleton_anim()
        clear_layout(self.insights_layout)

        err_frame = QFrame()
        err_frame.setStyleSheet(f"""
            background-color: {Styles.COLOR_SURFACE_LIGHT};
            border: 1px solid {Styles.COLOR_BLUNDER};
            border-radius: 8px;
            padding: 16px;
        """)
        vbox = QVBoxLayout(err_frame)
        vbox.setSpacing(10)

        lbl_title = QLabel("AI Coaching Unavailable")
        lbl_title.setStyleSheet(
            f"color: {Styles.COLOR_BLUNDER}; font-size: 14px; font-weight: 700; background: transparent;"
        )
        vbox.addWidget(lbl_title)

        lbl_err = QLabel(f"{err_msg}")
        lbl_err.setStyleSheet(
            f"color: {Styles.COLOR_TEXT_SECONDARY}; font-size: 12px; background: transparent;"
        )
        lbl_err.setWordWrap(True)
        lbl_err.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        vbox.addWidget(lbl_err)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        if "not configured" in err_msg.lower():
            btn_cfg = Button(
                "Configure LLM in Settings",
                ButtonVariant.PRIMARY,
                on_click=self._open_settings,
            )
            btn_row.addWidget(btn_cfg)
        else:
            show_error_dialog(
                self,
                "AI Coach Insights Failed",
                "Could not generate AI insights. See details below.",
                err_msg,
            )

        btn_retry = Button(
            "Retry Analysis", ButtonVariant.FILLED, on_click=self._generate_insights
        )
        btn_row.addWidget(btn_retry)
        btn_row.addStretch()

        vbox.addLayout(btn_row)
        self.insights_layout.addWidget(err_frame)

    def _open_settings(self):
        from ...dialogs.llm_error_dialog import LlmNotConfiguredDialog

        dlg = LlmNotConfiguredDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.wants_configure():
            window = self.window()
            if hasattr(window, "sidebar") and hasattr(window, "switch_page"):
                window.sidebar.set_active(4)
                window.switch_page(4)

    def _populate_insights(self, insight_text: str):
        self.current_insights = insight_text
        clear_layout(self.insights_layout)

        sections = self._parse_structured_insights(insight_text)

        if not sections or not any(sections.values()):
            # Fallback for plain text or unexpected formatting
            fallback_widget = QWidget()
            fallback_widget.setStyleSheet("background: transparent;")
            fb_vbox = QVBoxLayout(fallback_widget)
            fb_vbox.setContentsMargins(6, 6, 6, 6)
            fb_lbl = QLabel(insight_text)
            fb_lbl.setWordWrap(True)
            fb_lbl.setStyleSheet(
                f"color: {Styles.COLOR_TEXT_PRIMARY}; font-size: 12px; background: transparent;"
            )
            fb_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            fb_vbox.addWidget(fb_lbl)
            self.insights_layout.addWidget(fallback_widget)
            return

        section_meta = {
            "strengths": ("STRENGTHS & SUPERPOWERS", Styles.COLOR_RESULT_WIN),
            "leaks": ("CRITICAL LEAKS & BLINDSPOTS", Styles.COLOR_BLUNDER),
            "prescription": ("TRAINING PRESCRIPTION", Styles.COLOR_ACCENT),
        }

        first_section = True
        for sec_key, items in sections.items():
            if not items:
                continue
            title_text, color_accent = section_meta.get(
                sec_key, ("COACHING OBSERVATIONS", Styles.COLOR_TEXT_PRIMARY)
            )

            # Divider between sections
            if not first_section:
                divider = QFrame()
                divider.setFixedHeight(1)
                divider.setStyleSheet(
                    f"background-color: {Styles.COLOR_BORDER}; margin-top: 6px; margin-bottom: 6px;"
                )
                self.insights_layout.addWidget(divider)
            first_section = False

            sec_container = QWidget()
            sec_container.setObjectName(f"coach_sec_{sec_key}")
            sec_container.setStyleSheet("background: transparent;")
            sec_vbox = QVBoxLayout(sec_container)
            sec_vbox.setContentsMargins(0, 2, 0, 4)
            sec_vbox.setSpacing(10)

            # Header row (clean, non-boxy)
            h_row = QHBoxLayout()
            h_row.setSpacing(6)
            h_row.setAlignment(Qt.AlignmentFlag.AlignLeft)

            h_lbl = QLabel(title_text)
            h_lbl.setStyleSheet(f"""
                color: {color_accent};
                font-size: 11px;
                font-weight: 700;
                letter-spacing: 0.6px;
                background: transparent;
            """)
            h_row.addWidget(h_lbl)
            h_row.addStretch()
            sec_vbox.addLayout(h_row)

            # Items
            for item_title, item_body in items:
                item_widget = QWidget()
                item_widget.setStyleSheet("background: transparent;")
                ivbox = QVBoxLayout(item_widget)
                ivbox.setContentsMargins(0, 0, 0, 0)
                ivbox.setSpacing(3)

                t_lbl = QLabel(item_title)
                t_lbl.setStyleSheet(
                    f"color: {Styles.COLOR_TEXT_PRIMARY}; font-size: 13px; font-weight: 600; background: transparent;"
                )
                t_lbl.setWordWrap(True)
                ivbox.addWidget(t_lbl)

                if item_body:
                    b_lbl = QLabel(item_body)
                    b_lbl.setStyleSheet(
                        f"color: {Styles.COLOR_TEXT_SECONDARY}; font-size: 12px; background: transparent;"
                    )
                    b_lbl.setWordWrap(True)
                    ivbox.addWidget(b_lbl)

                sec_vbox.addWidget(item_widget)

            self.insights_layout.addWidget(sec_container)

        # Footer attribution (clean, modest)
        total = self.stats.get("total", 0)
        footer_lbl = QLabel(f"Generated by AI Coach • Based on {total} analyzed games")
        footer_lbl.setStyleSheet(
            f"color: {Styles.COLOR_TEXT_SECONDARY}; font-size: 10px; font-style: italic; background: transparent; padding-top: 10px;"
        )
        footer_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.insights_layout.addWidget(footer_lbl)

    def _parse_structured_insights(self, text: str) -> dict[str, list[tuple[str, str]]]:
        """
        Parses 3-tier coaching response into clean, un-mangled title/body tuples.
        Strips dangling asterisks, colons, and markdown artifacts.
        """
        result: dict[str, list[tuple[str, str]]] = {
            "strengths": [],
            "leaks": [],
            "prescription": [],
        }

        current_section = None
        lines = text.split("\n")

        for line in lines:
            line_s = line.strip()
            if not line_s:
                continue

            lower = line_s.lower()
            if "strength" in lower or "superpower" in lower:
                current_section = "strengths"
                continue
            elif "leak" in lower or "blindspot" in lower or "weakness" in lower:
                current_section = "leaks"
                continue
            elif "prescription" in lower or "training" in lower or "recommendation" in lower:
                current_section = "prescription"
                continue

            if not current_section:
                continue

            # Check if this is a bullet point or numbered item
            if line_s.startswith(("- ", "* ", "• ")) or (
                line_s[0].isdigit() and line_s[1:3] in (". ", ") ")
            ):
                content = re.sub(r"^[-*•\d.)\s]+", "", line_s).strip()

                # Extract title and body
                item_title = ""
                item_body = ""

                # Case 1: **Title**: Body or **Title** - Body
                bold_match = re.search(r"\*\*(.*?)\*\*", content)
                if bold_match:
                    raw_title = bold_match.group(1)
                    raw_body = content[bold_match.end() :].lstrip(":-— ").strip()
                    item_title = raw_title
                    item_body = raw_body
                else:
                    parts = content.split(":", 1)
                    if len(parts) == 2 and len(parts[0]) < 50:
                        item_title = parts[0]
                        item_body = parts[1]
                    else:
                        item_title = content
                        item_body = ""

                # Robust cleanup: strip all lingering markdown symbols, asterisks, colons, quotes
                clean_title = re.sub(r"[\*_#]+", "", item_title).strip(":-— \t")
                clean_body = re.sub(r"[\*_#]+", "", item_body).strip(":-— \t")

                if clean_title:
                    result[current_section].append((clean_title, clean_body))

        return result
