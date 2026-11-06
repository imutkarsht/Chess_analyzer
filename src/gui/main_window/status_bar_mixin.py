from src.backend.analysis.engine import resolve_engine_path
from src.gui.components import TextTone
from src.gui.components.feedback.toast import ToastManager


class StatusBarMixin:
    """Status bar pill, status messages, spinner animation, and toasts."""

    _STATUS_STYLES = {
        "idle": ("○", TextTone.MUTED),
        "info": ("◎", TextTone.ACCENT),
        "success": ("✔", TextTone.ENGINE_READY),
        "warning": ("⚠", TextTone.ENGINE_BUSY),
        "error": ("✖", TextTone.BLUNDER),
        "progress": ("◌", TextTone.ACCENT),
    }

    def show_toast(
        self,
        message: str,
        kind: str = "info",
        duration: int | None = None,
        **options,
    ):
        """Show a toast on this window; ``duration=None`` uses the variant default."""
        return ToastManager.show(self, message, kind, duration=duration, **options)

    @staticmethod
    def toast_from_widget(
        widget,
        message: str,
        kind: str = "info",
        duration: int | None = None,
        **options,
    ):
        return ToastManager.show(widget, message, kind, duration=duration, **options)

    def _on_live_thinking_started(self):
        """Live engine started computing — show Calculating unless full analysis is running."""
        if not getattr(self, "_full_analysis_running", False):
            self._set_engine_state("calculating")

    def _on_live_thinking_stopped(self):
        """Live engine finished computing — revert to Ready unless full analysis is running."""
        if not getattr(self, "_full_analysis_running", False):
            self._set_engine_state("ready")

    def _on_live_engine_state(self, state: str):
        """Map a live-engine session state to the status-bar pill."""
        if state == "thinking":
            self._on_live_thinking_started()
        else:
            self._on_live_thinking_stopped()

    def _refresh_engine_status(self):
        """Check engine binary and update pill. Call after path changes."""
        found = resolve_engine_path(self.config_manager) is not None
        self._set_engine_state("ready" if found else "offline")

    def _set_engine_state(self, state: str, progress_msg: str = ""):
        """Update engine status text. state: 'offline' | 'ready' | 'calculating'."""
        if state == "calculating":
            self._spinner_idx = 0
            if not self._spinner_timer.isActive():
                self._spinner_timer.start(120)
            self._engine_pill.setText("⬤  Calculating")
            self._engine_pill.set_tone(TextTone.ENGINE_BUSY)
        else:
            self._spinner_timer.stop()
            if state == "ready":
                self._engine_pill.setText("●  Engine ready")
                self._engine_pill.set_tone(TextTone.ENGINE_READY)
            else:  # offline
                self._engine_pill.setText("⬤  Engine Offline")
                self._engine_pill.set_tone(TextTone.BLUNDER)

    def _tick_spinner(self):
        """Advance the braille spinner animation one frame."""
        frame = self._spinner_frames[self._spinner_idx % len(self._spinner_frames)]
        self._spinner_idx += 1
        self._engine_pill.setText(f"{frame}  Calculating")

    def _set_status(self, message: str, kind: str = "info"):
        """Update the status label with an icon prefix and matching colour.

        Idle has no separate status: the engine pill alone is the indicator, so
        the separator and label stay hidden until there is something real to
        report (loading, analysing, warnings, errors).
        """
        idle = not message or message == "Ready"
        for widget in (
            getattr(self, "_status_sep", None),
            getattr(self, "_status_lbl", None),
        ):
            if widget is not None:
                widget.setVisible(not idle)
        if idle:
            return
        icon, tone = self._STATUS_STYLES.get(kind, ("◎", TextTone.ACCENT))
        self._status_lbl.setText(f"{icon}  {message}")
        self._status_lbl.set_tone(tone)
