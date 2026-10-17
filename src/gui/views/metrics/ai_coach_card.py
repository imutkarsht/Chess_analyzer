"""
AI Coach Insights Card.
Generates clean, structured coaching diagnostics from aggregated metrics,
highlighting Strengths & Superpowers, Critical Leaks, and a Personalized Training Prescription.
Open, modern design with zero nested box clutter.
"""

from __future__ import annotations

import re
from typing import Any

from PyQt6.QtCore import (
    QEasingCurve,
    QPropertyAnimation,
    QSequentialAnimationGroup,
    Qt,
    pyqtSignal,
)
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.backend.analysis.metrics_aggregator import MetricsAggregator
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
        self._skeleton_anim: QSequentialAnimationGroup | None = None

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
        self.btn_refresh_insights = QPushButton()
        self.btn_refresh_insights.setFixedSize(28, 28)
        self.btn_refresh_insights.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_refresh_insights.setToolTip("Generate / Refresh AI Coaching")
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
            self.btn_refresh_insights.setText("↻")

        self.btn_refresh_insights.clicked.connect(self._generate_insights)
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
        """Safely stops and cleans up the pulsing skeleton animation."""
        if self._skeleton_anim is not None:
            try:
                self._skeleton_anim.stop()
            except (RuntimeError, TypeError):
                pass
            self._skeleton_anim = None

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

    def _create_skeleton_row(
        self,
        width_ratio: float | None = None,
        fixed_width: int | None = None,
        height: int = 10,
        radius: int = 5,
    ) -> QWidget:
        row_widget = QWidget()
        row_widget.setStyleSheet("background: transparent;")
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(0)

        bar = QFrame()
        bar.setFixedHeight(height)
        bar.setStyleSheet(f"""
            background-color: {Styles.COLOR_SURFACE_LIGHT};
            border: 1px solid {Styles.COLOR_BORDER};
            border-radius: {radius}px;
        """)

        if fixed_width is not None:
            bar.setFixedWidth(fixed_width)
            row_layout.addWidget(bar)
            row_layout.addStretch()
        elif width_ratio is not None:
            w_int = max(1, int(width_ratio * 100))
            spacer_int = max(1, 100 - w_int)
            row_layout.addWidget(bar, w_int)
            spacer = QWidget()
            spacer.setStyleSheet("background: transparent;")
            row_layout.addWidget(spacer, spacer_int)
        else:
            bar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            row_layout.addWidget(bar)

        return row_widget

    def _show_loading_skeleton(self):
        """Displays a ChatGPT/Gemini-style pulsing skeleton UI while AI generates insights."""
        self._stop_skeleton_anim()
        clear_layout(self.insights_layout)

        skeleton_container = QWidget()
        skeleton_container.setObjectName("coach_skeleton_container")
        skeleton_container.setStyleSheet("background: transparent;")
        s_vbox = QVBoxLayout(skeleton_container)
        s_vbox.setContentsMargins(4, 8, 4, 12)
        s_vbox.setSpacing(14)

        # Header status row with pulsing indicator
        header_row = QHBoxLayout()
        header_row.setSpacing(8)
        header_row.setAlignment(Qt.AlignmentFlag.AlignLeft)

        dot = QLabel("●")
        dot.setStyleSheet(
            f"color: {Styles.COLOR_ACCENT}; font-size: 10px; background: transparent;"
        )
        header_row.addWidget(dot)

        lbl_title = QLabel("AI Coach is analyzing performance patterns...")
        lbl_title.setStyleSheet(
            f"color: {Styles.COLOR_TEXT_PRIMARY}; font-size: 13px; font-weight: 600; background: transparent;"
        )
        header_row.addWidget(lbl_title)
        header_row.addStretch()
        s_vbox.addLayout(header_row)

        lbl_sub = QLabel(
            "Synthesizing tactical motifs, advantage conversion, and clock discipline..."
        )
        lbl_sub.setStyleSheet(
            f"color: {Styles.COLOR_TEXT_SECONDARY}; font-size: 11px; background: transparent; padding-left: 16px;"
        )
        s_vbox.addWidget(lbl_sub)
        s_vbox.addSpacing(6)

        # Section 1 skeleton: Strengths & Superpowers (Header badge + 2 lines)
        sec1 = QVBoxLayout()
        sec1.setSpacing(8)
        sec1.addWidget(self._create_skeleton_row(fixed_width=140, height=12, radius=6))
        sec1.addWidget(self._create_skeleton_row(width_ratio=0.92, height=10, radius=5))
        sec1.addWidget(self._create_skeleton_row(width_ratio=0.68, height=10, radius=5))
        s_vbox.addLayout(sec1)

        # Divider
        div1 = QFrame()
        div1.setFixedHeight(1)
        div1.setStyleSheet(f"background-color: {Styles.COLOR_BORDER}; margin: 2px 0;")
        s_vbox.addWidget(div1)

        # Section 2 skeleton: Critical Leaks & Blindspots (Header badge + 3 lines)
        sec2 = QVBoxLayout()
        sec2.setSpacing(8)
        sec2.addWidget(self._create_skeleton_row(fixed_width=160, height=12, radius=6))
        sec2.addWidget(self._create_skeleton_row(width_ratio=0.95, height=10, radius=5))
        sec2.addWidget(self._create_skeleton_row(width_ratio=0.78, height=10, radius=5))
        sec2.addWidget(self._create_skeleton_row(width_ratio=0.48, height=10, radius=5))
        s_vbox.addLayout(sec2)

        # Divider
        div2 = QFrame()
        div2.setFixedHeight(1)
        div2.setStyleSheet(f"background-color: {Styles.COLOR_BORDER}; margin: 2px 0;")
        s_vbox.addWidget(div2)

        # Section 3 skeleton: Training Prescription (Header badge + 2 lines)
        sec3 = QVBoxLayout()
        sec3.setSpacing(8)
        sec3.addWidget(self._create_skeleton_row(fixed_width=135, height=12, radius=6))
        sec3.addWidget(self._create_skeleton_row(width_ratio=0.90, height=10, radius=5))
        sec3.addWidget(self._create_skeleton_row(width_ratio=0.60, height=10, radius=5))
        s_vbox.addLayout(sec3)

        self.insights_layout.addWidget(skeleton_container)

        # Opacity pulse animation (Gemini / ChatGPT style breathing effect)
        opacity_effect = QGraphicsOpacityEffect(skeleton_container)
        opacity_effect.setOpacity(0.28)
        skeleton_container.setGraphicsEffect(opacity_effect)

        anim_in = QPropertyAnimation(opacity_effect, b"opacity")
        anim_in.setDuration(900)
        anim_in.setStartValue(0.28)
        anim_in.setEndValue(0.85)
        anim_in.setEasingCurve(QEasingCurve.Type.InOutSine)

        anim_out = QPropertyAnimation(opacity_effect, b"opacity")
        anim_out.setDuration(900)
        anim_out.setStartValue(0.85)
        anim_out.setEndValue(0.28)
        anim_out.setEasingCurve(QEasingCurve.Type.InOutSine)

        self._skeleton_anim = QSequentialAnimationGroup(self)
        self._skeleton_anim.addAnimation(anim_in)
        self._skeleton_anim.addAnimation(anim_out)
        self._skeleton_anim.setLoopCount(-1)
        self._skeleton_anim.start()

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
            btn_cfg = QPushButton("Configure LLM in Settings")
            btn_cfg.setStyleSheet(Styles.get_button_style())
            btn_cfg.clicked.connect(self._open_settings)
            btn_row.addWidget(btn_cfg)
        else:
            show_error_dialog(
                self,
                "AI Coach Insights Failed",
                "Could not generate AI insights. See details below.",
                err_msg,
            )

        btn_retry = QPushButton("Retry Analysis")
        btn_retry.setStyleSheet(Styles.get_control_button_style())
        btn_retry.clicked.connect(self._generate_insights)
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
