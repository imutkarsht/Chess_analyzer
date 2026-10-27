"""Time & Clock Analytics card shell."""

from __future__ import annotations

from PyQt6.QtWidgets import QStackedWidget, QWidget

from src.gui.components import SegmentedControl
from src.gui.views.metrics.base_card import MetricCard
from src.gui.views.metrics.time.time_formats_view import FormatsView
from src.gui.views.metrics.time.time_pace_view import PaceView
from src.gui.views.metrics.time.time_trouble_view import TroubleView


class TimeManagementCard(MetricCard):
    """Card displaying time control and clock analytics.

    Three executive views via a header segmented control and ``QStackedWidget``:
    - Formats: performance breakdown per speed category
    - Move Pace: thinking time across phases and decision quality
    - Time Trouble: error rates under time pressure vs normal clock
    """

    def __init__(self, parent=None):
        self.stats: dict = {}
        self.current_mode = "formats"  # "formats", "pace", "trouble"

        self.segmented_control = SegmentedControl(
            options=[
                ("Formats", "formats"),
                ("Move Pace", "pace"),
                ("Time Trouble", "trouble"),
            ],
            value=self.current_mode,
        )
        self.segmented_control.valueChanged.connect(self.set_mode)

        super().__init__(
            "Time & Clock Analytics",
            parent=parent,
            min_height=320,
            action_widget=self.segmented_control,
        )

        # Compatibility aliases for existing callers/tests.
        self.btn_formats = self.segmented_control.button("formats")
        self.btn_pace = self.segmented_control.button("pace")
        self.btn_trouble = self.segmented_control.button("trouble")

        self.stack = QStackedWidget()
        self.stack.setStyleSheet("background: transparent;")

        self.formats_page = FormatsView()
        self.pace_page = PaceView()
        self.trouble_page = TroubleView()
        self._views: dict[str, QWidget] = {
            "formats": self.formats_page,
            "pace": self.pace_page,
            "trouble": self.trouble_page,
        }
        for page in self._views.values():
            self.stack.addWidget(page)

        self.set_content(self.stack)

    def set_mode(self, mode: str):
        page = self._views.get(mode)
        if page is None:
            return
        self.current_mode = mode
        self.segmented_control.set_value(mode, emit=False)
        self.stack.setCurrentWidget(page)
        page.ensure_rendered()

    def set_stats(self, stats: dict):
        self.stats = stats or {}
        time_data = self.stats.get("time_stats", {})
        has_clock = time_data.get("has_clock_data", False)
        formats = time_data.get("formats", {})

        self.formats_page.set_data(formats, has_clock)
        self.pace_page.set_data(time_data, has_clock)
        self.trouble_page.set_data(time_data, has_clock)
        self._views[self.current_mode].ensure_rendered()

    def refresh_styles(self):
        super().refresh_styles()
        for page in self._views.values():
            page.mark_dirty()
        self._views[self.current_mode].ensure_rendered()
