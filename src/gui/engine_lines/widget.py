"""Shared, config-driven engine-lines panel.

Used by the Analysis evaluation tab and the Explorer.  The widget is pure
presentation: it receives White-perspective :class:`EngineLine` objects and
never flips scores, never starts searches and never creates/destroys rows
while the engine is thinking (which is what made the old panels jump).
"""

from __future__ import annotations

import html

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFontMetrics
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.backend.analysis.engine_line import EngineLine
from src.gui.styles import Styles

from .config import EngineLinesConfig


def format_pv_html(text: str) -> str:
    """Render a SAN sequence: move numbers muted, first move accented."""
    if not text:
        return ""
    parts: list[str] = []
    first_move = True
    for word in text.split():
        if not word:
            continue
        safe = html.escape(word)
        if word[0].isdigit() or word.endswith("..."):
            parts.append(
                f"<span style='color: {Styles.COLOR_TEXT_MUTED};'>{safe}</span>"
            )
        elif first_move:
            parts.append(
                f"<span style='color: {Styles.COLOR_ACCENT}; font-weight: 600;'>{safe}</span>"
            )
            first_move = False
        else:
            parts.append(f"<span style='color: {Styles.COLOR_TEXT_PRIMARY};'>{safe}</span>")
    return " ".join(parts)


class EngineLineRow(QWidget):
    """One candidate line.  Reused forever; only its labels change."""

    clicked = pyqtSignal(str)

    def __init__(self, config: EngineLinesConfig, parent=None):
        super().__init__(parent)
        self.config = config
        self.uci_move: str | None = None
        self._line: EngineLine | None = None
        self._key: tuple | None = None
        self._pv_text = ""
        self._pv_full = ""

        self.setObjectName("EngineLineRow")
        # Plain QWidget subclasses only paint a stylesheet background/border
        # when these attributes are set.
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setFixedHeight(config.row_height)

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 6, 8, 6)
        root.setSpacing(3)

        meta = QHBoxLayout()
        meta.setContentsMargins(0, 0, 0, 0)
        meta.setSpacing(8)

        self._lbl_eval = QLabel()
        self._lbl_eval.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lbl_eval.setFixedHeight(22)
        self._lbl_eval.setMinimumWidth(58)
        self._lbl_eval.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        meta.addWidget(self._lbl_eval)

        self._lbl_depth = QLabel()
        self._lbl_depth.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self._lbl_depth.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        meta.addWidget(self._lbl_depth)

        meta.addStretch()
        root.addLayout(meta)

        self._lbl_pv = QLabel()
        self._lbl_pv.setFixedHeight(18)
        self._lbl_pv.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._lbl_pv.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        root.addWidget(self._lbl_pv)

        self._apply_styles()

    # ------------------------------------------------------------------
    def _apply_styles(self) -> None:
        self._lbl_depth.setStyleSheet(
            Styles.get_label_style(size=10, color=Styles.COLOR_TEXT_MUTED)
        )
        self._lbl_pv.setStyleSheet(Styles.get_label_style(size=12))
        self._lbl_eval.setStyleSheet(
            Styles.get_eval_badge_style(Styles.COLOR_SURFACE_LIGHT, Styles.COLOR_TEXT_PRIMARY)
        )

    def refresh_styles(self) -> None:
        self._apply_styles()
        if self._line is not None:
            self.set_line(self._line, force=True)

    # ------------------------------------------------------------------
    def set_line(self, line: EngineLine, force: bool = False) -> None:
        key = (line.rank, line.depth, line.cp, line.mate, line.pv_uci, line.pv_san)
        if not force and key == self._key:
            return
        self._key = key
        self._line = line

        self.uci_move = line.first_move if self.config.clickable else None
        self.setCursor(
            Qt.CursorShape.PointingHandCursor
            if self.uci_move
            else Qt.CursorShape.ArrowCursor
        )

        if self.config.show_depth:
            self._lbl_depth.setText(f"d{line.depth}" if line.depth else "")
            self._lbl_depth.show()
        else:
            self._lbl_depth.hide()

        if self.config.show_eval:
            self._lbl_eval.setText(line.score_text)
            self._lbl_eval.setStyleSheet(Styles.get_engine_score_badge_style(line))
            self._lbl_eval.show()
        else:
            self._lbl_eval.hide()

        tokens = (line.pv_san or " ".join(line.pv_uci)).split()
        self._pv_full = " ".join(tokens)
        self._pv_text = " ".join(tokens[: self.config.max_pv_plies])
        self._render_pv()

        depth = f"depth {line.depth}" if line.depth else "depth unknown"
        self.setToolTip(f"{line.score_text} · {depth}\n{self._pv_full}")

    def clear(self) -> None:
        self._key = None
        self._line = None
        self.uci_move = None
        self._pv_text = ""
        self._pv_full = ""
        self._lbl_eval.clear()
        self._lbl_depth.clear()
        self._lbl_pv.clear()
        self.setToolTip("")
        self.setCursor(Qt.CursorShape.ArrowCursor)

    # ------------------------------------------------------------------
    def _render_pv(self) -> None:
        if not self._pv_text:
            self._lbl_pv.clear()
            return
        metrics = QFontMetrics(self._lbl_pv.font())
        width = max(40, self._lbl_pv.width() - 2)
        elided = metrics.elidedText(self._pv_text, Qt.TextElideMode.ElideRight, width)
        self._lbl_pv.setText(format_pv_html(elided))

    def resizeEvent(self, event):  # noqa: N802 - Qt API
        super().resizeEvent(event)
        self._render_pv()

    def showEvent(self, event):  # noqa: N802 - Qt API
        super().showEvent(event)
        # Rows are created hidden, so the first render would otherwise use a
        # placeholder width and elide the PV too aggressively.
        self._render_pv()

    def mousePressEvent(self, event):  # noqa: N802 - Qt API
        if event.button() == Qt.MouseButton.LeftButton and self.uci_move:
            self.clicked.emit(self.uci_move)
        super().mousePressEvent(event)


class EngineLinesWidget(QFrame):
    """Scrollable list of engine lines, sized to its content."""

    line_clicked = pyqtSignal(str)

    def __init__(self, config: EngineLinesConfig | None = None, parent=None):
        super().__init__(parent)
        self.config = config or EngineLinesConfig()
        self._empty_text = self.config.empty_text
        self._lines: list[EngineLine] = []

        self.setObjectName("EngineLinesPanel")
        self.setFrameShape(QFrame.Shape.NoFrame)
        self._build_ui()
        self._apply_styles()
        self.clear()

    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(0)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )

        self._body = QWidget()
        self._rows_layout = QVBoxLayout(self._body)
        self._rows_layout.setContentsMargins(0, 0, 0, 0)
        self._rows_layout.setSpacing(self.config.row_spacing)
        self._rows_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self._empty = QLabel(self._empty_text)
        self._empty.setObjectName("EngineLinesEmpty")
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty.setFixedHeight(self.config.row_height)
        self._rows_layout.addWidget(self._empty)

        self._rows: list[EngineLineRow] = []
        for _ in range(max(1, self.config.max_lines)):
            row = EngineLineRow(self.config, self._body)
            row.clicked.connect(self.line_clicked.emit)
            row.hide()
            self._rows_layout.addWidget(row)
            self._rows.append(row)

        self._scroll.setWidget(self._body)
        root.addWidget(self._scroll)

    def _apply_styles(self) -> None:
        self.setStyleSheet(Styles.get_engine_lines_style())
        self._scroll.setStyleSheet(Styles.get_transparent_scroll_area_style())
        self._empty.setStyleSheet(
            Styles.get_label_style(size=12, color=Styles.COLOR_TEXT_MUTED)
        )
        for row in self._rows:
            row.refresh_styles()

    def _apply_height(self, visible: int) -> None:
        visible = max(1, min(visible, self.config.visible_lines, self.config.max_lines))
        spacing = self.config.row_spacing * (visible - 1)
        scroll_height = visible * self.config.row_height + spacing
        self._scroll.setFixedHeight(scroll_height)
        self.setFixedHeight(scroll_height + 16)

    # ------------------------------------------------------------------
    def set_lines(self, lines: list[EngineLine]) -> None:
        lines = list(lines or [])[: self.config.max_lines]
        self._lines = lines
        for index, row in enumerate(self._rows):
            if index < len(lines):
                row.set_line(lines[index])
                row.show()
            else:
                row.clear()
                row.hide()
        self._empty.setVisible(not lines)
        self._apply_height(len(lines) or 1)

    def clear(self) -> None:
        """Clear the panel and forget the lines (theme refreshes must not restore them)."""
        self._lines = []
        for row in self._rows:
            row.clear()
            row.hide()
        self._empty.setText(self._empty_text)
        self._empty.show()
        self._apply_height(1)

    def set_empty_text(self, text: str) -> None:
        self._empty_text = text
        self._empty.setText(text)

    def refresh_styles(self) -> None:
        self._apply_styles()
        for index, row in enumerate(self._rows):
            if index < len(self._lines):
                row.set_line(self._lines[index], force=True)

    @property
    def lines(self) -> list[EngineLine]:
        return list(self._lines)
