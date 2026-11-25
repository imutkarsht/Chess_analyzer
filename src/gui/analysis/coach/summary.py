# SPDX-License-Identifier: GPL-3.0-only
"""Full-game AI coach summary: presentation, generation, and persistence."""

from __future__ import annotations

from PyQt6.QtWidgets import QFrame, QSizePolicy, QVBoxLayout

from src.backend.services.groq_service import GroqService
from src.gui.components import (
    Button,
    ButtonVariant,
    PulsingSkeleton,
    TextArea,
    open_llm_settings,
    show_error_dialog,
)
from src.utils.logger import logger
from src.utils.text_utils import is_error_message
from src.workers.analysis import GenerateSummaryThread

# The Generate button lives below the summary: once a report exists the text
# fills the space above it, so the action has to sit in the lower half to stay
# reachable and to stop competing with the first line of the report.
_BTN_GENERATE_SUMMARY = "Generate AI coach summary"
_BTN_REGENERATE_SUMMARY = "Regenerate AI coach summary"

# Placeholder shape for the report: a title line, then paragraphs of prose.
_REPORT_SKELETON_SECTIONS = ((150, (0.96, 0.88, 0.62)), (120, (0.94, 0.70)))


class SummaryPanel(QFrame):
    """AI-written game report shown under the per-move coach card."""

    def __init__(self, groq_service: GroqService | None = None) -> None:
        super().__init__()
        self.groq_service = groq_service or GroqService()
        self.current_game = None
        self.user_side: str | None = None
        self.summary_thread = None

        self.ai_summary_layout = QVBoxLayout(self)
        self.ai_summary_layout.setContentsMargins(0, 4, 0, 0)
        self.ai_summary_layout.setSpacing(8)

        self.txt_ai_summary = TextArea(
            placeholder="AI Coach summary & key takeaways will appear here...",
            readonly=True,
        )
        self.txt_ai_summary.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.ai_summary_layout.addWidget(self.txt_ai_summary, stretch=1)

        # Same pulsing placeholder as the metrics AI Coach card: the summary is a
        # long generation, so the wait should look like the model is writing
        # rather than like the whole panel is blocked.
        self.ai_summary_skeleton = PulsingSkeleton(
            title="AI Coach is writing the game report...",
            subtitle="Weighing the turning points, accuracy and clock usage...",
            sections=_REPORT_SKELETON_SECTIONS,
            parent=self,
        )
        self.ai_summary_skeleton.setVisible(False)
        self.ai_summary_layout.addWidget(self.ai_summary_skeleton, stretch=1)

        # Below the summary, at the bottom of the Coach tab, so a full report
        # never pushes the action off the panel.
        self.btn_generate_summary = Button(
            _BTN_GENERATE_SUMMARY,
            ButtonVariant.TONAL,
            icon="fa5s.magic",
            tooltip="Write a full-game report from this analysis",
        )
        self.btn_generate_summary.clicked.connect(self.generate_ai_summary)
        self.ai_summary_layout.addWidget(self.btn_generate_summary)

    def set_context(self, game, user_side: str | None) -> None:
        self.current_game = game
        self.user_side = user_side
        self.render_current()

    def set_llm_service(self, service: GroqService) -> None:
        self.groq_service = service

    def render_current(self) -> None:
        """Mirror the stored report after a game load or an analysis refresh."""
        if self.current_game is None:
            return
        if self.current_game.ai_summary:
            self.txt_ai_summary.setText(self.current_game.ai_summary)
            self.btn_generate_summary.setText(_BTN_REGENERATE_SUMMARY)
        else:
            self.txt_ai_summary.clear()
            self.btn_generate_summary.setText(_BTN_GENERATE_SUMMARY)
        # The body stays visible even when empty: it is what pins the action
        # to the bottom of the tab, and its placeholder explains the state.
        self.txt_ai_summary.setVisible(True)
        self.btn_generate_summary.setVisible(True)

    def generate_ai_summary(self) -> None:
        if not self.current_game:
            return
        if not self.groq_service.client:
            open_llm_settings(self)
            return
        self._set_loading(True)
        logger.info("Starting AI summary generation...")
        self.summary_thread = GenerateSummaryThread(
            self.groq_service, self.current_game, user_side=self.user_side
        )
        self.summary_thread.finished.connect(self.on_summary_generated)
        self.summary_thread.start()

    def _set_loading(self, loading: bool) -> None:
        """Swap the report for the pulsing placeholder while the model writes."""
        self.btn_generate_summary.setEnabled(not loading)
        self.ai_summary_skeleton.setVisible(loading)
        if loading:
            self.txt_ai_summary.setVisible(False)
            self.ai_summary_skeleton.start()
            return

        self.ai_summary_skeleton.stop()
        # The body is never collapsed: it keeps the action pinned to the bottom
        # of the tab and shows its placeholder until the first report arrives.
        self.txt_ai_summary.setVisible(True)

    def on_summary_generated(self, summary: str) -> None:
        self._set_loading(False)
        self.btn_generate_summary.setEnabled(True)

        if is_error_message(summary):
            logger.error("AI Summary generation failed: %s", summary)
            # Keep whatever report was already there: a failed regeneration must
            # not throw away a good one.
            previous = (self.current_game.ai_summary if self.current_game else "") or ""
            self.txt_ai_summary.setPlainText(previous)
            self.btn_generate_summary.setText(
                _BTN_REGENERATE_SUMMARY if previous else _BTN_GENERATE_SUMMARY
            )
            if "not configured" in summary.lower():
                open_llm_settings(self)
            else:
                show_error_dialog(
                    self,
                    "AI Summary Failed",
                    "Could not generate the AI summary.",
                    summary,
                )
            return

        logger.info("AI Summary generated successfully.")
        if self.current_game is None:
            return
        self.current_game.ai_summary = summary
        self.txt_ai_summary.setText(summary)
        self.txt_ai_summary.setVisible(True)
        self.txt_ai_summary.verticalScrollBar().setValue(0)
        self.btn_generate_summary.setText(_BTN_REGENERATE_SUMMARY)
        self._persist_ai_summary(summary)

    def _persist_ai_summary(self, text: str) -> None:
        """
        Store the report on the game record so reloading the game keeps it.

        The main window owns the history database; standalone embeddings of the
        panel (previews, tests) have no manager and simply keep it in memory.
        """
        game_id = getattr(self.current_game, "game_id", "") if self.current_game else ""
        manager = getattr(self.window(), "history_manager", None)
        if not game_id or manager is None:
            return
        try:
            manager.save_ai_summary(game_id, text)
        except Exception as e:
            logger.warning("Could not store the AI summary for game %s: %s", game_id, e)

    def refresh_styles(self) -> None:
        self.btn_generate_summary.refresh_styles()
        self.txt_ai_summary.refresh_styles()

    def shutdown(self) -> None:
        """Stop the generation thread without leaving a dangling signal."""
        thread, self.summary_thread = self.summary_thread, None
        if thread is None:
            return
        try:
            thread.finished.disconnect()
        except (TypeError, RuntimeError):
            pass
        if thread.isRunning():
            thread.quit()
            thread.wait()

    def closeEvent(self, event):
        self.shutdown()
        super().closeEvent(event)
