"""History search, filter tokens, and progressive-disclosure filter panel."""

from __future__ import annotations

from PyQt6.QtCore import (
    QEasingCurve,
    QPropertyAnimation,
    Qt,
    pyqtSignal,
)
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QFrame,
    QGraphicsOpacityEffect,
    QGridLayout,
    QHBoxLayout,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.backend.storage.game_query import (
    ANALYSIS_ANALYZED,
    ANALYSIS_PAUSED,
    ANALYSIS_UNANALYZED,
    OWNERSHIP_MINE,
    OWNERSHIP_OTHER,
    RESULT_DRAW,
    RESULT_LOSS,
    RESULT_WIN,
)
from src.gui.components import (
    Button,
    ButtonSize,
    ButtonVariant,
    FilterChip,
    Input,
    InputSize,
    InputVariant,
    Label,
    SegmentedControl,
    Select,
    SelectSize,
    TextRole,
    TextTone,
)
from src.gui.styles import Styles
from src.gui.theme import ThemeManager


class HistoryFilterBar(QWidget):
    """Search, active-filter tokens, and one disclosure panel.

    The toolbar stays deliberately small. Filter state is surfaced through
    removable tokens instead of keeping every dropdown permanently visible.
    """

    search_changed = pyqtSignal()
    filters_changed = pyqtSignal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._token_buttons: list[Button] = []
        self._root_layout = QVBoxLayout(self)
        self._root_layout.setContentsMargins(0, 0, 0, 0)
        self._root_layout.setSpacing(10)
        self._build_toolbar()
        self._build_tokens()
        self._build_panel()
        self._root_layout.addWidget(self.toolbar)
        self._root_layout.addWidget(self.token_row)
        self._root_layout.addWidget(
            self.panel, 0, Qt.AlignmentFlag.AlignLeft
        )
        self._sync_summary()
        manager = ThemeManager.instance()
        manager.theme_changed.connect(self.refresh_styles)
        manager.accent_changed.connect(self.refresh_styles)
        self.refresh_styles()

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------
    def _build_toolbar(self) -> None:
        self.toolbar = QWidget()
        layout = QHBoxLayout(self.toolbar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        self.search_input = Input(
            placeholder="Search player, opening, date...",
            variant=InputVariant.SEARCH,
            size=InputSize.MD,
            clearable=True,
        )
        self.search_input.setAccessibleName("Search games")
        self.search_input.setMinimumWidth(220)
        self.search_input.setMaximumWidth(380)
        self.search_input.textChanged.connect(
            lambda *_: self.search_changed.emit()
        )
        layout.addWidget(self.search_input, 1)

        self.btn_filters = Button(
            "Filters",
            ButtonVariant.HOLLOW,
            ButtonSize.MD,
            icon="fa5s.filter",
            checkable=True,
            tooltip="Show game filters",
            on_click=self._toggle_panel,
        )
        self.btn_filters.setAccessibleName("Filters")
        layout.addWidget(self.btn_filters)

        layout.addStretch()

        self.sort_dropdown = Select(
            [
                ("Newest First", "newest"),
                ("Oldest First", "oldest"),
                ("Most Moves", "most_moves"),
                ("Fewest Moves", "fewest_moves"),
            ],
            size=SelectSize.SM,
            min_width=150,
            accessible_name="Sort games",
            on_change=lambda _value: self._on_filter_changed(),
        )
        layout.addWidget(self.sort_dropdown)

    def _build_tokens(self) -> None:
        self.token_row = QWidget()
        self.token_layout = QHBoxLayout(self.token_row)
        self.token_layout.setContentsMargins(0, 0, 0, 0)
        self.token_layout.setSpacing(8)
        self.token_row.setVisible(False)
        self.token_count_label = Label(
            "", role=TextRole.CAPTION, tone=TextTone.SECONDARY
        )
        self._result_count = 0
        self._token_effect = QGraphicsOpacityEffect(self.token_row)
        self._token_effect.setOpacity(1.0)
        self.token_row.setGraphicsEffect(self._token_effect)
        self._token_anim = QPropertyAnimation(
            self._token_effect, b"opacity", self
        )
        self._token_anim.setDuration(150)
        self._token_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._token_hide_pending = False
        self._token_anim.finished.connect(self._on_token_anim_finished)

    def _build_panel(self) -> None:
        self.panel = QFrame()
        self.panel.setObjectName("HistoryFilterPanel")
        # A full-width panel turns compact filters into a wall of empty space.
        # Keep the disclosure region tied to the search/filter group instead.
        self.panel.setMinimumWidth(680)
        self.panel.setMaximumWidth(760)
        layout = QVBoxLayout(self.panel)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(12)

        header = QHBoxLayout()
        header.setSpacing(8)
        title = Label(
            "Filter games",
            role=TextRole.BODY_STRONG,
            weight=600,
        )
        header.addWidget(title)
        header.addStretch()
        self.btn_reset = Button(
            "Clear filters",
            ButtonVariant.LINK,
            ButtonSize.SM,
            on_click=lambda: self.reset_filters(),
        )
        self.btn_reset.setAccessibleName("Clear all filters")
        header.addWidget(self.btn_reset)
        layout.addLayout(header)

        grid = QGridLayout()
        grid.setHorizontalSpacing(24)
        grid.setVerticalSpacing(12)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)

        self.result_filter = Select(
            [
                ("All results", ""),
                ("Wins", RESULT_WIN),
                ("Losses", RESULT_LOSS),
                ("Draws", RESULT_DRAW),
            ],
            size=SelectSize.MD,
            min_width=180,
            accessible_name="Result filter",
            on_change=lambda _value: self._on_filter_changed(),
        )
        self.result_filter.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )

        self.type_filter = Select(
            [
                ("All speeds", ""),
                ("Bullet", "Bullet"),
                ("Blitz", "Blitz"),
                ("Rapid", "Rapid"),
                ("Classical", "Classical"),
                ("Daily", "Daily"),
                ("UltraBullet", "UltraBullet"),
            ],
            size=SelectSize.MD,
            min_width=180,
            accessible_name="Time class filter",
            on_change=lambda _value: self._on_filter_changed(),
        )
        self.type_filter.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )

        self.source_filter = Select(
            [
                ("All sources", ""),
                ("Chess.com", "chesscom"),
                ("Lichess", "lichess"),
                ("File", "file"),
            ],
            size=SelectSize.MD,
            min_width=180,
            accessible_name="Source filter",
            on_change=lambda _value: self._on_filter_changed(),
        )
        self.source_filter.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )

        self.analysis_filter = SegmentedControl(
            [
                ("All", ""),
                ("Analyzed", ANALYSIS_ANALYZED),
                ("Unanalyzed", ANALYSIS_UNANALYZED),
                ("Paused", ANALYSIS_PAUSED),
            ],
            value="",
            size=ButtonSize.MD,
            expand_items=True,
        )
        self.analysis_filter.valueChanged.connect(
            self._on_filter_changed
        )
        self.analysis_filter.setAccessibleName("Analysis state filter")

        self.ownership_filter = SegmentedControl(
            [
                ("All", ""),
                ("My games", OWNERSHIP_MINE),
                ("Other games", OWNERSHIP_OTHER),
            ],
            value="",
            size=ButtonSize.MD,
            expand_items=True,
        )
        self.ownership_filter.valueChanged.connect(
            self._on_filter_changed
        )
        self.ownership_filter.setAccessibleName("Game ownership filter")

        grid.addWidget(
            self._field("Result", self.result_filter), 0, 0
        )
        grid.addWidget(
            self._field("Time class", self.type_filter), 0, 1
        )
        grid.addWidget(
            self._field("Source", self.source_filter), 1, 0
        )
        grid.addWidget(
            self._field("Games", self.ownership_filter), 1, 1
        )
        grid.addWidget(
            self._field("Analysis", self.analysis_filter), 2, 0, 1, 2
        )
        layout.addLayout(grid)

        footer = QHBoxLayout()
        footer.addStretch()
        self.btn_done = Button(
            "Done",
            ButtonVariant.PRIMARY,
            ButtonSize.MD,
            on_click=self._close_panel,
        )
        self.btn_done.setAccessibleName("Close filters")
        footer.addWidget(self.btn_done)
        layout.addLayout(footer)

        self.panel.setVisible(False)
        self._escape = QShortcut(QKeySequence("Escape"), self)
        self._escape.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self._escape.activated.connect(self._close_from_keyboard)

    @staticmethod
    def _field(text: str, control: QWidget) -> QWidget:
        box = QWidget()
        box.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        label = Label(
            text,
            role=TextRole.BODY_STRONG,
            tone=TextTone.SECONDARY,
        )
        label.setBuddy(control)
        layout.addWidget(label)
        layout.addWidget(control)
        return box

    # ------------------------------------------------------------------
    # Public state
    # ------------------------------------------------------------------
    def search_text(self) -> str:
        return self.search_input.text().strip().lower()

    def panel_filters_active(self) -> bool:
        return bool(self._active_tokens())

    def filters_active(self) -> bool:
        return self.panel_filters_active() or bool(self.search_text())

    def reset_filters(self, *, emit: bool = True) -> None:
        """Clear search and every filter; sorting is intentionally preserved."""
        self.search_input.blockSignals(True)
        self.search_input.clear()
        self.search_input.blockSignals(False)

        self.result_filter.set_current_index(0, emit=False)
        self.type_filter.set_current_index(0, emit=False)
        self.source_filter.set_current_index(0, emit=False)
        self.analysis_filter.set_value("", emit=False)
        self.ownership_filter.set_value("", emit=False)
        self._sync_summary()
        if emit:
            self.filters_changed.emit()

    def set_result_count(self, total: int) -> None:
        self._result_count = max(0, int(total))
        self._sync_count_label()

    def set_panel_open(self, open_: bool) -> None:
        self.panel.setVisible(open_)
        self.btn_filters.setChecked(open_)
        if open_:
            self._set_tokens_visible(False, animate=False)
            self.result_filter.setFocus()
        else:
            self._set_tokens_visible(
                self.panel_filters_active(), animate=True
            )

    # ------------------------------------------------------------------
    # Interaction
    # ------------------------------------------------------------------
    def _toggle_panel(self) -> None:
        self.set_panel_open(self.btn_filters.isChecked())

    def _close_panel(self) -> None:
        self.set_panel_open(False)
        self.btn_filters.setFocus()

    def _close_from_keyboard(self) -> None:
        if self.panel.isVisible():
            self._close_panel()

    def _on_filter_changed(self, *_args) -> None:
        self._sync_summary()
        self.filters_changed.emit()

    def _open_filter(self, key: str) -> None:
        self.set_panel_open(True)
        controls = {
            "result": self.result_filter,
            "speed": self.type_filter,
            "source": self.source_filter,
        }
        control = controls.get(key)
        if control is not None:
            control.setFocus()
        elif key == "analysis":
            self.analysis_filter.button(
                self.analysis_filter.value()
            ).setFocus()
        elif key == "ownership":
            self.ownership_filter.button(
                self.ownership_filter.value()
            ).setFocus()

    def _remove_filter(self, key: str) -> None:
        if key == "result":
            self.result_filter.set_current_index(0, emit=False)
        elif key == "speed":
            self.type_filter.set_current_index(0, emit=False)
        elif key == "source":
            self.source_filter.set_current_index(0, emit=False)
        elif key == "analysis":
            self.analysis_filter.set_value("", emit=False)
        elif key == "ownership":
            self.ownership_filter.set_value("", emit=False)
        self._on_filter_changed()

    # ------------------------------------------------------------------
    # Active-filter summary
    # ------------------------------------------------------------------
    def _active_tokens(self) -> list[tuple[str, str, str, str]]:
        tokens: list[tuple[str, str, str, str]] = []
        result = self.result_filter.current_value()
        if result:
            colors = {
                RESULT_WIN: Styles.COLOR_RESULT_WIN,
                RESULT_LOSS: Styles.COLOR_RESULT_LOSS,
                RESULT_DRAW: Styles.COLOR_RESULT_DRAW,
            }
            tokens.append(
                (
                    "result",
                    "Result",
                    self.result_filter.current_text(),
                    colors.get(result, Styles.COLOR_TEXT_MUTED),
                )
            )
        speed = self.type_filter.current_value()
        if speed:
            tokens.append(
                (
                    "speed",
                    "Time class",
                    self.type_filter.current_text(),
                    Styles.COLOR_ACCENT,
                )
            )
        source = self.source_filter.current_value()
        if source:
            tokens.append(
                (
                    "source",
                    "Source",
                    self.source_filter.current_text(),
                    Styles.COLOR_TEXT_MUTED,
                )
            )
        analysis = self.analysis_filter.value()
        if analysis:
            labels = {
                ANALYSIS_ANALYZED: (
                    "Analyzed",
                    Styles.COLOR_GOOD,
                ),
                ANALYSIS_UNANALYZED: (
                    "Unanalyzed",
                    Styles.COLOR_TEXT_MUTED,
                ),
                ANALYSIS_PAUSED: (
                    "Paused",
                    Styles.COLOR_INACCURACY,
                ),
            }
            label, color = labels[analysis]
            tokens.append(("analysis", "Analysis", label, color))
        ownership = self.ownership_filter.value()
        if ownership:
            labels = {
                OWNERSHIP_MINE: ("My games", Styles.COLOR_ACCENT),
                OWNERSHIP_OTHER: (
                    "Other games",
                    Styles.COLOR_TEXT_MUTED,
                ),
            }
            label, color = labels[ownership]
            tokens.append(("ownership", "Games", label, color))
        return tokens

    def _sync_summary(self) -> None:
        tokens = self._active_tokens()
        count = len(tokens)
        self.btn_filters.setText("Filters" if count == 0 else f"Filters · {count}")
        self.btn_filters.setAccessibleName(
            "Filters" if count == 0 else f"Filters, {count} active"
        )
        self.btn_filters.setToolTip(
            "Show game filters"
            if count == 0
            else f"Show game filters ({count} active)"
        )
        self._sync_count_label()
        self._rebuild_tokens(tokens)

    def _sync_count_label(self) -> None:
        count = len(self._active_tokens())
        games = f"{self._result_count:,} " + (
            "game" if self._result_count == 1 else "games"
        )
        filters = f"{count} " + ("filter" if count == 1 else "filters")
        self.token_count_label.setText(f"{games} · {filters}")

    def _rebuild_tokens(
        self, tokens: list[tuple[str, str, str, str]]
    ) -> None:
        # The count label is persistent; only the chips and Clear button are
        # rebuilt. Detach it before clearing so it is never deleted with them.
        self.token_layout.removeWidget(self.token_count_label)
        while self.token_layout.count():
            item = self.token_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.deleteLater()
        self._token_buttons.clear()

        if not tokens:
            self._set_tokens_visible(False)
            return

        for key, category, value, color in tokens:
            chip = FilterChip(
                f"{category}: {value}",
                dot_color=color,
                accessible_label=f"{category} filter, {value}",
            )
            chip.open_requested.connect(
                lambda k=key: self._open_filter(k)
            )
            chip.remove_requested.connect(
                lambda k=key: self._remove_filter(k)
            )
            self._token_buttons.append(chip)
            self.token_layout.addWidget(chip)
            chip.show()
        clear = Button(
            "Clear filters",
            ButtonVariant.LINK,
            ButtonSize.SM,
            on_click=lambda: self.reset_filters(),
        )
        clear.setAccessibleName("Clear all filters")
        self._token_buttons.append(clear)
        self.token_layout.addWidget(clear)
        clear.show()
        self.token_layout.addStretch()
        self.token_layout.addWidget(self.token_count_label)
        self.token_count_label.show()
        self._set_tokens_visible(
            not self.panel.isVisible(), animate=True
        )

    def _set_tokens_visible(self, visible: bool, *, animate: bool = True) -> None:
        if visible and not self._active_tokens():
            visible = False
        was_visible = self.token_row.isVisible()
        if not visible and not was_visible:
            return

        self._token_anim.stop()
        self._token_hide_pending = False
        if visible:
            self.token_row.setVisible(True)
            if not animate or was_visible:
                self._token_effect.setOpacity(1.0)
                return
            self._token_effect.setOpacity(0.0)
            self._token_anim.setStartValue(0.0)
            self._token_anim.setEndValue(1.0)
            self._token_anim.start()
            return

        if animate:
            self._token_hide_pending = True
            self._token_anim.setStartValue(self._token_effect.opacity())
            self._token_anim.setEndValue(0.0)
            self._token_anim.start()
        else:
            self.token_row.setVisible(False)
            self._token_effect.setOpacity(1.0)

    def _on_token_anim_finished(self) -> None:
        if self._token_hide_pending:
            self._token_hide_pending = False
            self.token_row.setVisible(False)
            self._token_effect.setOpacity(1.0)

    # ------------------------------------------------------------------
    # Styling
    # ------------------------------------------------------------------
    def refresh_styles(self, *_args) -> None:
        self.panel.setStyleSheet(Styles.get_history_filter_panel_style())
        self.search_input.refresh_styles()
        self.btn_filters.refresh_styles()
        self.sort_dropdown.refresh_styles()
        self.result_filter.refresh_styles()
        self.type_filter.refresh_styles()
        self.source_filter.refresh_styles()
        self.analysis_filter.refresh_styles()
        self.ownership_filter.refresh_styles()
        self.btn_reset.refresh_styles()
        self.btn_done.refresh_styles()
        # Dot colours come from semantic palette roles, so rebuild the chips
        # when light/dark or the accent changes.
        self._sync_summary()
