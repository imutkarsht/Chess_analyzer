from src.backend.analysis.engine import resolve_engine_path
from src.gui.components.toast import Toast
from src.gui.styles import Styles


class StatusBarMixin:
    """Status bar pill, status messages, spinner animation, and toasts."""

    _STATUS_STYLES = {
        "idle": ("○", Styles.COLOR_TEXT_MUTED),
        "info": ("◎", "#3498db"),
        "success": ("✔", Styles.COLOR_ENGINE_READY),
        "warning": ("⚠", Styles.COLOR_ENGINE_BUSY),
        "error": ("✖", Styles.COLOR_BLUNDER),
        "progress": ("◌", "#3498db"),
    }

    def show_toast(self, message: str, kind: str = "info", duration: int | None = None):
        Toast.show_message(self, message, kind, duration)

    @staticmethod
    def toast_from_widget(widget, message: str, kind: str = "info", duration: int | None = None):
        win = widget.window()
        if hasattr(win, "show_toast"):
            win.show_toast(message, kind, duration)

    def _on_live_thinking_started(self):
        """Live engine started computing — show Calculating unless full analysis is running."""
        if not getattr(self, "_full_analysis_running", False):
            self._set_engine_state("calculating")

    def _on_live_thinking_stopped(self):
        """Live engine finished computing — revert to Ready unless full analysis is running."""
        if not getattr(self, "_full_analysis_running", False):
            self._set_engine_state("ready")

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
            self._engine_pill.setStyleSheet(
                f"font-size: 12px; font-weight: 600; padding: 0 6px; color: {Styles.COLOR_ENGINE_BUSY};"
            )
        else:
            self._spinner_timer.stop()
            if state == "ready":
                self._engine_pill.setText("⬤  Engine Ready")
                self._engine_pill.setStyleSheet(
                    f"font-size: 12px; font-weight: 600; padding: 0 6px; color: {Styles.COLOR_ENGINE_READY};"
                )
            else:  # offline
                self._engine_pill.setText("⬤  Engine Offline")
                self._engine_pill.setStyleSheet(
                    f"font-size: 12px; font-weight: 600; padding: 0 6px; color: {Styles.COLOR_BLUNDER};"
                )

    def _tick_spinner(self):
        """Advance the braille spinner animation one frame."""
        frame = self._spinner_frames[self._spinner_idx % len(self._spinner_frames)]
        self._spinner_idx += 1
        self._engine_pill.setText(f"{frame}  Calculating")

    def _set_status(self, message: str, kind: str = "info"):
        """Update the status label with an icon prefix and matching colour."""
        icon, color = self._STATUS_STYLES.get(kind, ("◎", "#3498db"))
        self._status_lbl.setText(f"{icon}  {message}")
        self._status_lbl.setStyleSheet(f"font-size: 12px; color: {color}; background: transparent;")
