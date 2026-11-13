"""
Per-game Tactics tab.

A compact, scrollable timeline of validated tactical events for one side:
executed tactics, allowed punishments, missed chances, and pieces lost or won.
Clicking a row asks the host panel to jump the board to that move.

Presentation only: the data comes from ``tactics.report`` and all colours from
``Styles``.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QKeyEvent, QMouseEvent
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.backend.analysis.tactics.report import GameTacticEntry, GameTacticsReport
from src.gui.components import (
    EmptyState,
    IconLabel,
    Label,
    SegmentedControl,
    TextRole,
    TextTone,
)
from src.gui.styles import Styles
from src.gui.tactics_meta import motif_meta

_CLASSIFICATION_TONES: dict[str, str] = {
    "brilliant": "brilliant",
    "great": "great",
    "best": "best",
    "excellent": "excellent",
    "good": "good",
    "inaccuracy": "inaccuracy",
    "mistake": "mistake",
    "blunder": "blunder",
    "miss": "miss",
    "book": "book",
}

_PIECE_ICONS: dict[str, str] = {
    "pawn": "fa5s.chess-pawn",
    "knight": "fa5s.chess-knight",
    "bishop": "fa5s.chess-bishop",
    "rook": "fa5s.chess-rook",
    "queen": "fa5s.chess-queen",
    "king": "fa5s.chess-king",
}


class _ElidedLabel(Label):
    """Semantic label that ellipsizes instead of forcing the row wider."""

    def __init__(self, text: str = "", **kwargs) -> None:
        self._full_text = text
        super().__init__("", **kwargs)
        self.setText(text)

    def setText(self, text: str) -> None:  # noqa: N802 - Qt override
        self._full_text = text
        self._update_elide()

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt override
        super().resizeEvent(event)
        self._update_elide()

    def _update_elide(self) -> None:
        if not hasattr(self, "_full_text"):
            return
        width = self.width()
        if width <= 0:
            super().setText(self._full_text)
            return
        super().setText(
            self.fontMetrics().elidedText(
                self._full_text, Qt.TextElideMode.ElideRight, width
            )
        )


class TacticRow(QFrame):
    """One clickable tactical event."""

    move_requested = pyqtSignal(int)

    def __init__(self, entry: GameTacticEntry, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.entry = entry
        self.setObjectName("TacticRow")
        self.setProperty("active", False)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName(self._accessible_name())
        self.setToolTip(self._tooltip())
        self._build()
        self.refresh_styles()

    def _build(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(10)

        icon_frame = QFrame()
        icon_frame.setObjectName("TacticIcon")
        icon_frame.setFixedSize(32, 32)
        icon_layout = QVBoxLayout(icon_frame)
        icon_layout.setContentsMargins(0, 0, 0, 0)
        icon_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_layout.addWidget(
            IconLabel(_row_icon(self.entry), size=15, color=_row_color(self.entry))
        )
        layout.addWidget(icon_frame, 0, Qt.AlignmentFlag.AlignTop)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(1)

        primary = Label(self.entry.move_label, role=TextRole.CAPTION_STRONG)
        primary.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        text_layout.addWidget(primary)

        secondary_text = _secondary_text(self.entry)
        secondary = _ElidedLabel(
            secondary_text, role=TextRole.MICRO, tone=TextTone.SECONDARY
        )
        secondary.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred
        )
        secondary.setToolTip(secondary_text)
        text_layout.addWidget(secondary)
        layout.addLayout(text_layout, 1)

        trailing = QHBoxLayout()
        trailing.setSpacing(8)
        trailing.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        if self.entry.classification:
            classification = Label(
                self.entry.classification,
                role=TextRole.MICRO_STRONG,
                tone=_classification_tone(self.entry.classification),
            )
            classification.setAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            trailing.addWidget(classification)
        trailing.addWidget(
            IconLabel("fa5s.chevron-right", size=10, tone=TextTone.MUTED)
        )
        layout.addLayout(trailing, 0)

    def set_active(self, active: bool) -> None:
        if bool(self.property("active")) == active:
            return
        self.setProperty("active", active)
        self.style().unpolish(self)
        self.style().polish(self)

    def refresh_styles(self) -> None:
        color = _row_color(self.entry)
        self.setStyleSheet(
            f"""
            QFrame#TacticRow {{
                background: transparent;
                border: 1px solid transparent;
                border-left: 2px solid transparent;
                border-radius: 6px;
            }}
            QFrame#TacticRow:hover {{
                background-color: {Styles.COLOR_SURFACE_LIGHT};
            }}
            QFrame#TacticRow[active="true"] {{
                background-color: {Styles.COLOR_ACCENT_SUBTLE};
                border-left: 2px solid {Styles.COLOR_ACCENT};
            }}
            QFrame#TacticRow:focus {{
                border: 1px solid {Styles.COLOR_ACCENT};
                border-left: 2px solid {Styles.COLOR_ACCENT};
            }}
            QFrame#TacticIcon {{
                background-color: {color}15;
                border-radius: 6px;
            }}
            """
        )

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.move_requested.emit(self.entry.move_index)
        super().mousePressEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (
            Qt.Key.Key_Return,
            Qt.Key.Key_Enter,
            Qt.Key.Key_Space,
        ):
            self.move_requested.emit(self.entry.move_index)
            event.accept()
            return
        super().keyPressEvent(event)

    def _accessible_name(self) -> str:
        parts = [self.entry.move_label, motif_meta(self.entry.motif).label]
        if self.entry.classification:
            parts.append(self.entry.classification)
        parts.append("Jump to this move")
        return ", ".join(parts)

    def _tooltip(self) -> str:
        meta = motif_meta(self.entry.motif)
        lines = [meta.label, meta.description]
        if self.entry.summary:
            lines.append(self.entry.summary)
        lines.extend(self.entry.details)
        if self.entry.eval_text:
            lines.append(f"Eval: {self.entry.eval_text}")
        lines.append("Click to jump to this move.")
        return "\n".join(lines)


class TacticsTab(QWidget):
    """Scrollable per-game tactical timeline with a White/Black side toggle."""

    move_requested = pyqtSignal(int)

    SECTIONS: tuple[tuple[str, str], ...] = (
        ("executed", "Executed Tactics"),
        ("allowed", "Tactics Allowed"),
        ("missed", "Tactics Missed"),
        ("lost", "Pieces Lost"),
        ("won", "Pieces Won"),
    )

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._reports: dict[str, GameTacticsReport] = {}
        self._players: dict[str, str] = {}
        self._result = ""
        self._selected_move: int | None = None
        self._rows: list[TacticRow] = []
        self._empty_message = "Analyze this game to reveal its tactics."

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.side_control = SegmentedControl(
            (("White", "white"), ("Black", "black")),
            value="white",
            expand_items=True,
        )
        self.side_control.valueChanged.connect(self._on_side_changed)
        layout.addWidget(self.side_control)

        self.side_label = Label(
            "", role=TextRole.MICRO, tone=TextTone.SECONDARY, wrap=True
        )
        layout.addWidget(self.side_label)

        self.summary_label = Label(
            "", role=TextRole.MICRO, tone=TextTone.MUTED, wrap=True
        )
        layout.addWidget(self.summary_label)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
        )

        self.content = QWidget()
        self.content.setStyleSheet("background: transparent;")
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(8)
        self.scroll.setWidget(self.content)
        layout.addWidget(self.scroll, 1)

        self.show_empty("Analyze this game to reveal its tactics.")

    def set_reports(
        self,
        reports: dict[str, GameTacticsReport],
        preferred_side: str,
        players: dict[str, str],
        result: str,
    ) -> None:
        """Load both side reports and render the preferred side."""
        self._reports = reports
        self._players = players
        self._result = result
        side = preferred_side if preferred_side in reports else "white"
        self.side_control.set_value(side, emit=False)
        self._render_current()

    def set_selected_move(self, index: int) -> None:
        self._selected_move = index
        for row in self._rows:
            row.set_active(row.entry.move_index == index)

    def show_empty(self, message: str) -> None:
        self._empty_message = message
        self._reports = {}
        self._rows = []
        self.side_label.clear()
        self.summary_label.clear()
        self._clear_content()
        self.content_layout.addWidget(EmptyState(message), 1)

    def refresh_styles(self) -> None:
        self.scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
        )
        if self._reports:
            self._render_current()
        else:
            self.show_empty(self._empty_message)

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def _on_side_changed(self, side: str) -> None:
        self._render_current()

    def _render_current(self) -> None:
        report = self._reports.get(self.side_control.value())
        self._update_side_label()
        self._clear_content()
        self._rows = []

        if report is None or report.is_empty:
            self.summary_label.clear()
            message = (
                f"No confirmed tactics for "
                f"{self.side_control.value().title()} in this game."
            )
            self._empty_message = message
            self.content_layout.addWidget(EmptyState(message), 1)
            return

        self._render_summary(report)
        for key, title in self.SECTIONS:
            entries = getattr(report, key)
            if entries:
                self._render_section(title, entries)

        self.content_layout.addStretch(1)
        selected = self._selected_move if self._selected_move is not None else -1
        self.set_selected_move(selected)

    def _render_summary(self, report: GameTacticsReport) -> None:
        summary = report.summary
        parts: list[str] = []
        for key, label in (
            ("executed", "executed"),
            ("allowed", "allowed"),
            ("missed", "missed"),
            ("lost", "lost"),
            ("won", "won"),
        ):
            count = summary[key]
            if count:
                parts.append(f"{count} {label}")
        self.summary_label.setText(" · ".join(parts))

    def _render_section(
        self,
        title: str,
        entries: tuple[GameTacticEntry, ...],
    ) -> None:
        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(2, 6, 2, 0)
        header_layout.setSpacing(6)
        header_layout.addWidget(
            Label(title.upper(), role=TextRole.MICRO_STRONG, tone=TextTone.MUTED)
        )
        header_layout.addStretch()
        header_layout.addWidget(
            Label(str(len(entries)), role=TextRole.MICRO, tone=TextTone.MUTED)
        )
        self.content_layout.addWidget(header)

        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setStyleSheet(Styles.get_divider_style())
        self.content_layout.addWidget(divider)

        for entry in entries:
            row = TacticRow(entry)
            row.move_requested.connect(self.move_requested.emit)
            self._rows.append(row)
            self.content_layout.addWidget(row)

        self.content_layout.addSpacing(4)

    def _update_side_label(self) -> None:
        name = (self._players.get(self.side_control.value()) or "").strip()
        parts = [name] if name else []
        if self._result and self._result != "*":
            parts.append(self._result)
        text = " · ".join(parts)
        self.side_label.setText(text)
        self.side_label.setToolTip(text)

    def _clear_content(self) -> None:
        self._clear_layout(self.content_layout)

    @staticmethod
    def _clear_layout(layout: QVBoxLayout | QHBoxLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()


def _row_icon(entry: GameTacticEntry) -> str:
    if entry.role in ("lost", "won") and entry.target_piece:
        return _PIECE_ICONS.get(entry.target_piece.lower(), "fa5s.chess")
    return motif_meta(entry.motif).icon


def _row_color(entry: GameTacticEntry) -> str:
    if entry.role == "lost":
        return Styles.COLOR_MISTAKE
    if entry.role == "won":
        return Styles.COLOR_GOOD
    meta = motif_meta(entry.motif)
    return getattr(Styles, meta.color_attr, Styles.COLOR_ACCENT)


def _secondary_text(entry: GameTacticEntry) -> str:
    if entry.role in ("lost", "won"):
        return entry.summary
    meta = motif_meta(entry.motif)
    return meta.label + (f" · {entry.summary}" if entry.summary else "")


def _classification_tone(classification: str) -> str:
    return _CLASSIFICATION_TONES.get(classification.lower(), TextTone.SECONDARY.value)


__all__ = ["TacticRow", "TacticsTab"]
