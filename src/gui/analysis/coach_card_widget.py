"""
Coach card: the per-move explanation surface in the Analysis panel's Coach tab.

The card is presentation only. It renders the deterministic offline summary
immediately, offers an "Ask Coach" action, and renders a validated narrative
when the owner hands one over. All LLM work belongs to
:class:`~src.gui.analysis.coach_worker.ExplainMoveWorker`.
"""

from __future__ import annotations

import math
from enum import StrEnum

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QFontMetrics
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.backend.analysis.tactics.insight import (
    MoveInsight,
    format_move_insight_offline,
    move_prefix,
)
from src.constants import LLM_WORTHY_CLASSIFICATIONS
from src.gui.components import Button, ButtonSize, ButtonVariant, TextArea
from src.gui.styles import Styles

# The body is sized to its wrapped text: the tab has room to grow downwards, so
# an explanation is shown in full instead of behind a scrollbar. The floor keeps
# short states from jittering, the ceiling stops a pathological reply from
# pushing the actions out of reach. Measured in text lines (not pixels) so it
# stays correct at any font/DPI scale.
_BODY_MIN_LINES = 4
_BODY_MAX_LINES = 12
_BODY_FONT_PX = 13
_BUTTON_HEIGHT = 32
# Header badges and action buttons wrap onto a second row when the panel is too
# narrow to show them all at their natural width (see ``_layout_rows``).
_MAX_ROWS = 2
_ROW_SPACING = 8


class CoachState(StrEnum):
    EMPTY = "empty"  # no move selected
    OFFLINE = "offline"  # deterministic summary only
    LOADING = "loading"
    READY = "ready"  # validated LLM narrative
    FALLBACK = "fallback"  # offline text + a retry hint


def is_llm_worthy(classification: str, allow_trivial: bool = False) -> bool:
    """
    Whether the Ask button is offered for this classification (D8).

    Sound moves (Best/Excellent/Good/Book) need no explanation; the setting
    ``explain_llm_for_trivial_moves`` can override that.
    """
    if allow_trivial:
        return bool(classification)
    return classification in LLM_WORTHY_CLASSIFICATIONS


class CoachCardWidget(QFrame):
    ask_requested = pyqtSignal()
    refutation_requested = pyqtSignal()
    best_move_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("CoachCard")
        # Horizontal ``Ignored``: the card always takes exactly the panel width
        # and never asks for more, so a long explanation can only ever wrap
        # (growing downwards), never widen the card or the panel.
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.insight: MoveInsight | None = None
        self.state = CoachState.EMPTY
        self._expected: tuple[int, int] | None = None
        # Kept so the offered actions can be derived from the current state
        # instead of from widget visibility (see ``_offered_actions``).
        self.allow_trivial = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # --- header: classification pill, move badge, eval swing, phase chip ---
        self._header_rows = self._add_row_containers(layout)

        self.class_pill = QLabel("-")
        self.san_label = QLabel("-")
        self.eval_label = QLabel("")
        self.eval_label.setToolTip(
            "Engine evaluation from White's perspective (positive = White is better). "
            "The explanation's win chance is from your perspective."
        )
        self.phase_label = QLabel("")

        # --- body: a fixed number of lines that scrolls anything longer ---
        self.body_edit = TextArea(variant="flat", font_size=_BODY_FONT_PX, readonly=True)
        # Wrap to the widget width and never demand width of our own, so the
        # body cannot push the card sideways as the text gets longer.
        self.body_edit.setMinimumWidth(0)
        self.body_edit.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.body_edit.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.body_edit.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        layout.addWidget(self.body_edit)

        # Stay visible (empty) when unused so the action row below never moves.
        self.caption = QLabel("")
        self.caption.setWordWrap(False)
        self.caption.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        layout.addWidget(self.caption)

        # --- actions: flow into rows so a narrow panel never clips a label ---
        self._action_rows = self._add_row_containers(layout)

        # Parented to the card so a button that is briefly outside a row layout
        # is never a stray top-level window.
        self.btn_ask = Button(
            "",
            ButtonVariant.TONAL,
            size=ButtonSize.SM,
            icon="fa5s.magic",
            on_click=self.ask_requested.emit,
            parent=self,
        )
        self.btn_ask.setFixedHeight(_BUTTON_HEIGHT)

        self.btn_refute = Button(
            "Show refutation",
            ButtonVariant.FILLED,
            size=ButtonSize.SM,
            on_click=self.refutation_requested.emit,
            parent=self,
        )
        self.btn_refute.setFixedHeight(_BUTTON_HEIGHT)

        self.btn_best = Button(
            "Show best move",
            ButtonVariant.FILLED,
            size=ButtonSize.SM,
            on_click=self.best_move_requested.emit,
            parent=self,
        )
        self.btn_best.setFixedHeight(_BUTTON_HEIGHT)

        self._header_badges = (self.class_pill, self.san_label, self.eval_label, self.phase_label)
        self._action_buttons = (self.btn_ask, self.btn_refute, self.btn_best)

        self.set_insight(None)
        self.refresh_styles()
        self._layout_rows()

    @staticmethod
    def _add_row_containers(layout: QVBoxLayout) -> list[QWidget]:
        """
        Add two empty row containers to the card's layout.

        Badges and buttons are moved between these rows as the card narrows, so
        each one keeps its natural width instead of being squeezed until its
        label is cut off.
        """
        rows: list[QWidget] = []
        for _ in range(_MAX_ROWS):
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(_ROW_SPACING)
            row_layout.addStretch()
            layout.addWidget(row)
            rows.append(row)
        return rows

    # ------------------------------------------------------------------
    # State transitions
    # ------------------------------------------------------------------

    def body_text(self) -> str:
        """The text currently shown in the body area."""
        return self.body_edit.toPlainText()

    def _set_body(self, text: str) -> None:
        """Replace the body text and refit the body to it."""
        self.body_edit.setPlainText(text)
        self.body_edit.verticalScrollBar().setValue(0)
        self._fit_body()

    def set_insight(self, insight: MoveInsight | None, allow_trivial: bool = False) -> None:
        """Reset the card for a (new) selected move."""
        self.insight = insight
        self.allow_trivial = allow_trivial
        self._expected = None
        self.caption.setText("")

        if insight is None:
            self.state = CoachState.EMPTY
            self.class_pill.setText("-")
            self.san_label.setText("-")
            self.eval_label.setText("")
            self.phase_label.setText("")
            self._restyle_header()
            self._set_body("Select a move to see why it was played.")
            self._layout_rows()
            return

        self.class_pill.setText(insight.classification or "Unclassified")
        self.san_label.setText(insight.numbered_san)
        self.eval_label.setText(f"White: {insight.eval_before} → {insight.eval_after}")
        self.phase_label.setText(insight.phase)
        self._restyle_header()

        self.state = CoachState.OFFLINE
        self._set_body(format_move_insight_offline(insight))

        self.btn_ask.setText(f"Ask Coach: why is this a {insight.classification}?")
        self.btn_refute.setToolTip(self.refutation_label())
        self.btn_best.setToolTip(self.best_move_label())
        self._layout_rows()

    def _offered_actions(self) -> tuple[QPushButton, ...]:
        """
        The actions the current insight and state offer, in display order.

        Derived from the state rather than from ``isHidden()``: a widget inside
        a hidden row reports itself as hidden too, so reading visibility back
        would make an action sticky once its row had been wrapped away.
        """
        if self.insight is None:
            return ()
        offered: list[QPushButton] = []
        if self.state is not CoachState.READY and is_llm_worthy(
            self.insight.classification, self.allow_trivial
        ):
            offered.append(self.btn_ask)  # READY already shows the narrative
        if self.insight.refutation_san:
            offered.append(self.btn_refute)
        if self.insight.best_move_san and self.insight.best_move_uci != self.insight.uci:
            offered.append(self.btn_best)
        return tuple(offered)

    def begin_loading(self, seq: int, ply: int) -> None:
        self.state = CoachState.LOADING
        self._expected = (seq, ply)
        self.btn_ask.setEnabled(False)
        self.caption.setText("Coach is thinking…")

    def show_narrative(self, seq: int, ply: int, text: str) -> bool:
        """
        Render a validated narrative. Returns False (ignoring it) when the
        result belongs to a request the card is no longer waiting for (D6).
        """
        if self._expected != (seq, ply):
            return False
        self.state = CoachState.READY
        self._set_body(text)
        self.caption.setText("Coach explanation — grounded in the analysis")
        self.btn_ask.setEnabled(True)
        self._layout_rows()  # READY drops the Ask action
        return True

    def show_fallback(self, seq: int, ply: int, reason: str = "") -> bool:
        """Keep the offline text and surface a quiet retry hint."""
        if self._expected != (seq, ply):
            return False
        self.state = CoachState.FALLBACK
        if self.insight is not None:
            self._set_body(format_move_insight_offline(self.insight))
        self.caption.setText("Coach couldn't respond, showing the analysis.")
        self.btn_ask.setEnabled(True)
        if reason:
            self.btn_ask.setToolTip(reason)
        self._layout_rows()
        return True

    def refutation_label(self) -> str:
        """Notation for the refutation button tooltip (opponent's move number)."""
        if self.insight is None or not self.insight.refutation_san:
            return ""
        return f"{self.insight.refutation_prefix}{' '.join(self.insight.refutation_san)}"

    def best_move_label(self) -> str:
        if self.insight is None or not self.insight.best_move_san:
            return ""
        return (
            f"{move_prefix(self.insight.move_number, self.insight.side)}"
            f"{self.insight.best_move_san}"
        )

    # ------------------------------------------------------------------
    # Row layout
    # ------------------------------------------------------------------

    def _layout_rows(self) -> None:
        """
        Flow the header badges and the action buttons across their rows.

        A narrow panel used to squeeze these widgets until their text was cut
        off; instead each one keeps its natural width and the overflow wraps
        onto the next row. The card then grows downwards, which is fine — it
        must never grow sideways, and it must never clip a label.
        """
        margins = self.layout().contentsMargins()
        available = max(self.width() - margins.left() - margins.right(), 0)

        self._flow(self._header_rows, self._header_badges, self._header_badges, available)
        self._flow(self._action_rows, self._action_buttons, self._offered_actions(), available)

    @staticmethod
    def _flow(
        rows: list[QWidget],
        universe: tuple[QWidget, ...],
        shown: tuple[QWidget, ...],
        available: int,
    ) -> None:
        """
        Lay ``shown`` out over ``rows`` greedily by width; hide the rest.

        Every widget keeps its ``sizeHint()`` width: one that would overflow the
        current row starts the next row, so nothing is ever squeezed into a
        clipped label. Rows without widgets are hidden, which ties the card
        height to the rows it really uses.
        """
        assignments: list[list[QWidget]] = []
        current: list[QWidget] = []
        used = 0
        for widget in shown:
            width = widget.sizeHint().width()
            if current and used + _ROW_SPACING + width > available:
                assignments.append(current)
                current, used = [], 0
            used += width + (_ROW_SPACING if current else 0)
            current.append(widget)
        if current:
            assignments.append(current)

        for index, row in enumerate(rows):
            wanted = assignments[index] if index < len(assignments) else []
            row_layout = row.layout()
            for widget in universe:
                placed = row_layout.indexOf(widget) != -1
                if widget in wanted and not placed:
                    row_layout.addWidget(widget)
                elif widget not in wanted and placed:
                    row_layout.removeWidget(widget)
            row.setVisible(bool(wanted))

        # Set visibility last: hiding a row also hides its children, so doing
        # this first would leave a widget's own flag out of sync with its row.
        placed_anywhere = {widget for row in assignments for widget in row}
        for widget in universe:
            widget.setVisible(widget in placed_anywhere)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._layout_rows()
        self._fit_body()  # a narrower card wraps the text into more lines

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._layout_rows()
        self._fit_body()

    # ------------------------------------------------------------------
    # Styling
    # ------------------------------------------------------------------

    def refresh_styles(self) -> None:
        self.setStyleSheet(Styles.get_frame_style(object_name="CoachCard", hover_accent=False))
        self.body_edit.refresh_styles()
        self._restyle_header()
        self.caption.setStyleSheet(
            Styles.get_label_style(size=11, color=Styles.COLOR_TEXT_MUTED)
            + " "
            + Styles.get_transparent_label_style()
        )
        for button in (self.btn_ask, self.btn_refute, self.btn_best):
            button.refresh_styles()
        self._layout_rows()  # the styles decide the badge/button widths
        self._fit_body()  # ...and the body font decides the line height

    def _fit_body(self) -> None:
        """
        Give the body exactly the height its wrapped text needs.

        The tab has plenty of room downwards, so a long explanation grows the
        card instead of hiding behind a scrollbar. Only a reply beyond
        ``_BODY_MAX_LINES`` is capped (and scrolls) so the actions below it stay
        reachable.
        """
        document = self.body_edit.document()
        width = self.body_edit.viewport().width()
        if width > 0:
            document.setTextWidth(width)
            self.body_edit.setFixedHeight(
                max(
                    self._body_lines(_BODY_MIN_LINES),
                    min(
                        math.ceil(document.size().height() + 2 * document.documentMargin()) + 2,
                        self._body_lines(_BODY_MAX_LINES),
                    ),
                )
            )

    def _body_lines(self, lines: int) -> int:
        """Height of ``lines`` text lines at the body font size."""
        font = QFont(self.body_edit.font())
        font.setPixelSize(_BODY_FONT_PX)
        return QFontMetrics(font).lineSpacing() * lines + 4

    def _restyle_header(self) -> None:
        """
        Style every header badge in every state.

        An unstyled QLabel is shorter than a badge-styled one, so leaving the
        placeholders plain would make the header jump the first time a move is
        selected. The pill's colour follows the classification.
        """
        color = (
            Styles.get_class_color(self.insight.classification)
            if self.insight is not None
            else Styles.COLOR_TEXT_MUTED
        )
        self.class_pill.setStyleSheet(Styles.get_result_badge_style(color))
        self.san_label.setStyleSheet(Styles.get_badge_style())
        self.phase_label.setStyleSheet(Styles.get_badge_style())
        self.eval_label.setStyleSheet(
            Styles.get_eval_badge_style(Styles.COLOR_ACCENT_SUBTLE, Styles.COLOR_TEXT_PRIMARY)
        )
