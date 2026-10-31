"""Layout and theme-refresh behaviour for the Opening Explorer page."""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from src.gui.analysis.captured import CapturedPiecesWidget
from src.gui.analysis.explorer_move_list import ExplorerMoveListWidget
from src.gui.board import Board, BoardConfig
from src.gui.components import (
    Button,
    ButtonSize,
    ButtonVariant,
    Input,
    InputSize,
    InputVariant,
)
from src.gui.engine_lines import EngineLinesConfig, EngineLinesWidget
from src.gui.styles import Styles


class ExplorerUiMixin:
    """Builds the page chrome and rebuilds its palette-derived styles."""

    def setup_ui(self):
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self._build_header_bar(main_layout)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setHandleWidth(2)
        self.splitter.setStyleSheet(Styles.get_splitter_style())

        self._build_left_panel()
        self._build_right_panel()

        self.splitter.setSizes([700, 450])
        main_layout.addWidget(self.splitter, 1)

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def _build_header_bar(self, main_layout: QVBoxLayout) -> None:
        self.header_bar = QFrame()
        self.header_bar.setStyleSheet(
            Styles.get_header_bar_ext_style(bg_color=Styles.COLOR_BACKGROUND)
        )
        header_layout = QHBoxLayout(self.header_bar)
        header_layout.setContentsMargins(20, 6, 20, 6)

        self.title_lbl = QLabel("Opening Explorer")
        self.title_lbl.setStyleSheet(
            Styles.get_label_style(
                size=16, color=Styles.COLOR_TEXT_PRIMARY, bold=True
            )
            + " "
            + Styles.get_transparent_label_style()
        )
        header_layout.addWidget(self.title_lbl)

        self.opening_badge = QLabel("Opening: -")
        self.opening_badge.setStyleSheet(
            Styles.get_label_style(size=13, color=Styles.COLOR_TEXT_SECONDARY)
            + "; padding: 0px 0px 0px 12px; "
            + Styles.get_transparent_label_style()
        )
        header_layout.addWidget(self.opening_badge)
        header_layout.addStretch()

        self.btn_flip = Button(
            "Flip Board", ButtonVariant.HOLLOW, ButtonSize.SM, on_click=self._flip_board
        )
        header_layout.addWidget(self.btn_flip)

        self.btn_copy_fen = Button(
            "Copy FEN", ButtonVariant.HOLLOW, ButtonSize.SM, on_click=self._copy_fen
        )
        header_layout.addWidget(self.btn_copy_fen)

        self.btn_copy_pgn = Button(
            "Copy PGN", ButtonVariant.HOLLOW, ButtonSize.SM, on_click=self._copy_pgn
        )
        header_layout.addWidget(self.btn_copy_pgn)

        main_layout.addWidget(self.header_bar)

    def _build_left_panel(self) -> None:
        self.left_panel = QWidget()
        self.left_panel.setStyleSheet(Styles.get_background_style())
        self.left_layout = QVBoxLayout(self.left_panel)
        self.left_layout.setContentsMargins(8, 8, 8, 8)
        self.left_layout.setSpacing(6)

        self.black_header_widget = self._build_player_header(
            "Black", side="black", label_attr="lbl_black", captured_attr="captured_black"
        )
        self.left_layout.addWidget(self.black_header_widget)

        self.board_widget = Board(BoardConfig(classification_overlay="last_move"))
        self.board_widget.move_made.connect(self.on_move_made)
        self.left_layout.addWidget(self.board_widget, stretch=1)

        self.white_header_widget = self._build_player_header(
            "White", side="white", label_attr="lbl_white", captured_attr="captured_white"
        )
        self.left_layout.addWidget(self.white_header_widget)

        self.splitter.addWidget(self.left_panel)

    def _build_player_header(
        self, title: str, *, side: str, label_attr: str, captured_attr: str
    ) -> QWidget:
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)

        label = QLabel(title)
        label.setStyleSheet(Styles.get_label_style(size=16, bold=True))
        captured = CapturedPiecesWidget(side=side)

        layout.addWidget(label)
        layout.addWidget(captured)
        layout.addStretch()

        setattr(self, label_attr, label)
        setattr(self, captured_attr, captured)
        return widget

    def _build_right_panel(self) -> None:
        self.right_panel = QWidget()
        self.right_panel.setStyleSheet(Styles.get_background_style())
        right_layout = QVBoxLayout(self.right_panel)
        right_layout.setContentsMargins(8, 8, 12, 8)
        right_layout.setSpacing(6)

        self._build_toggles(right_layout)
        self._build_engine_lines(right_layout)
        self._build_book_section(right_layout)
        self._build_moves_section(right_layout)

        self.engine_status_label = QLabel("")
        self.engine_status_label.setStyleSheet(
            Styles.get_engine_status_style(Styles.COLOR_TEXT_MUTED)
        )
        right_layout.addWidget(self.engine_status_label)

        self.splitter.addWidget(self.right_panel)

    def _build_toggles(self, right_layout: QVBoxLayout) -> None:
        toggles_layout = QHBoxLayout()
        toggles_layout.setContentsMargins(0, 0, 0, 4)
        toggles_layout.setSpacing(8)

        self.chk_classify = QCheckBox("Classify Moves")
        self.chk_classify.setChecked(self.classify_enabled)
        self.chk_classify.toggled.connect(self.on_classify_toggled)

        self.chk_legal = QCheckBox("Legal Moves")
        self.chk_legal.setChecked(True)
        self.chk_legal.toggled.connect(self.on_legal_moves_toggled)

        self.chk_engine = QCheckBox("Engine Lines")
        self.chk_engine.setChecked(False)
        self.chk_engine.toggled.connect(self.on_engine_toggled)

        self.chk_cache = QCheckBox("Use Cache")
        self.chk_cache.setChecked(True)

        for chk in (self.chk_classify, self.chk_legal, self.chk_engine, self.chk_cache):
            chk.setStyleSheet(
                Styles.get_label_style(
                    size=12, color=Styles.COLOR_TEXT_SECONDARY, weight=500
                )
            )
            chk.setCursor(Qt.CursorShape.PointingHandCursor)
            toggles_layout.addWidget(chk)

        right_layout.addLayout(toggles_layout)

    def _build_engine_lines(self, right_layout: QVBoxLayout) -> None:
        self.lines_widget = EngineLinesWidget(
            EngineLinesConfig(empty_text="Enable Engine Lines to see analysis")
        )
        self.lines_widget.line_clicked.connect(self.on_engine_line_clicked)
        self.lines_widget.setVisible(False)
        right_layout.addWidget(self.lines_widget, stretch=0)

    def _build_book_section(self, right_layout: QVBoxLayout) -> None:
        self.book_toggle = Button(
            "▶  Book Moves",
            ButtonVariant.GHOST,
            checkable=True,
            align="left",
            on_click=None,
        )
        self.book_toggle.setChecked(True)
        self.book_toggle.toggled.connect(self._toggle_book)
        right_layout.addWidget(self.book_toggle)

        self.explorer_hint = QLabel()
        self.explorer_hint.setWordWrap(True)
        self.explorer_hint.setOpenExternalLinks(False)
        self.explorer_hint.setStyleSheet(
            Styles.get_label_style(size=11, color=Styles.COLOR_TEXT_MUTED)
            + "; padding: 2px 14px; "
            + Styles.get_transparent_label_style()
        )
        self.explorer_hint.hide()
        right_layout.addWidget(self.explorer_hint)

        self.book_scroll = QScrollArea()
        self.book_scroll.setWidgetResizable(True)
        self.book_scroll.setStyleSheet(Styles.get_scroll_area_style())

        self.book_container = QWidget()
        self.book_container.setStyleSheet(Styles.get_surface_style())
        self.book_layout = QVBoxLayout(self.book_container)
        self.book_layout.setContentsMargins(0, 0, 0, 0)
        self.book_layout.setSpacing(0)
        self.book_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.book_scroll.setWidget(self.book_container)

        right_layout.addWidget(self.book_scroll, stretch=1)

        self.lichess_attribution = QLabel()
        self.lichess_attribution.setStyleSheet(
            Styles.get_label_style(size=11, color=Styles.COLOR_TEXT_MUTED)
            + "; padding: 4px 14px; "
            + Styles.get_transparent_label_style()
        )
        self.lichess_attribution.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self.lichess_attribution.setOpenExternalLinks(True)
        self.lichess_attribution.setVisible(False)
        right_layout.addWidget(self.lichess_attribution)
        self._refresh_attribution_text()

    def _build_moves_section(self, right_layout: QVBoxLayout) -> None:
        moves_header = QHBoxLayout()
        moves_header.setContentsMargins(0, 0, 0, 0)
        moves_header.setSpacing(8)

        self.move_list_label = QLabel("Moves")
        self.move_list_label.setStyleSheet(Styles.get_label_style(size=14, bold=True))
        moves_header.addWidget(self.move_list_label)

        self.move_input = Input(
            placeholder="type SAN move...",
            variant=InputVariant.INLINE,
            size=InputSize.SM,
            on_submit=self._on_move_text_entered,
        )
        self.move_input.setToolTip(
            "Enter a move in standard algebraic notation (e.g. e4, Nf3, O-O)"
        )
        self.move_input.setMinimumWidth(120)
        moves_header.addWidget(self.move_input)
        moves_header.addStretch()
        right_layout.addLayout(moves_header)

        self.move_list_widget = ExplorerMoveListWidget()
        self.move_list_widget.move_selected.connect(self.on_move_list_clicked)
        self.move_list_widget.nav_first.connect(lambda: self.on_move_list_clicked(-1))
        self.move_list_widget.nav_prev.connect(
            lambda: self.on_move_list_clicked(self.move_list_widget.current_index - 1)
        )
        self.move_list_widget.nav_next.connect(
            lambda: self.on_move_list_clicked(self.move_list_widget.current_index + 1)
        )
        self.move_list_widget.nav_last.connect(
            lambda: self.on_move_list_clicked(len(self.move_history) - 1)
        )
        right_layout.addWidget(self.move_list_widget, stretch=1)

    def _refresh_attribution_text(self) -> None:
        self.lichess_attribution.setText(
            'powered by <a href="https://lichess.org" '
            f'style="color: {Styles.COLOR_ACCENT}; text-decoration: none;">'
            "lichess.org</a>"
        )

    # ------------------------------------------------------------------
    # Theme refresh
    # ------------------------------------------------------------------

    def refresh_styles(self):
        """Re-applies styles to explorer view components."""
        self._refresh_header_styles()
        self._refresh_panel_styles()
        self._refresh_book_styles()
        self._refresh_move_styles()
        for child in self.findChildren(QWidget):
            child.style().unpolish(child)
            child.style().polish(child)

    def _refresh_header_styles(self) -> None:
        self.header_bar.setStyleSheet(
            Styles.get_header_bar_ext_style(bg_color=Styles.COLOR_BACKGROUND)
        )
        self.title_lbl.setStyleSheet(
            Styles.get_label_style(
                size=16, color=Styles.COLOR_TEXT_PRIMARY, bold=True
            )
            + " "
            + Styles.get_transparent_label_style()
        )
        self.opening_badge.setStyleSheet(
            Styles.get_label_style(size=13, color=Styles.COLOR_TEXT_SECONDARY)
            + "; padding: 0px 0px 0px 12px; "
            + Styles.get_transparent_label_style()
        )
        for button in (self.btn_flip, self.btn_copy_fen, self.btn_copy_pgn):
            button.refresh_styles()

    def _refresh_panel_styles(self) -> None:
        self.splitter.setStyleSheet(Styles.get_splitter_style())
        self.left_panel.setStyleSheet(Styles.get_background_style())
        self.right_panel.setStyleSheet(Styles.get_background_style())
        self.lbl_black.setStyleSheet(Styles.get_label_style(size=16, bold=True))
        self.lbl_white.setStyleSheet(Styles.get_label_style(size=16, bold=True))
        self.captured_white.refresh_styles()
        self.captured_black.refresh_styles()
        self.lines_widget.refresh_styles()

    def _refresh_book_styles(self) -> None:
        self.book_toggle.refresh_styles()
        self.explorer_hint.setStyleSheet(
            Styles.get_label_style(size=11, color=Styles.COLOR_TEXT_MUTED)
            + "; padding: 2px 14px; "
            + Styles.get_transparent_label_style()
        )
        self.book_scroll.setStyleSheet(Styles.get_scroll_area_style())
        self.book_container.setStyleSheet(Styles.get_surface_style())
        self.lichess_attribution.setStyleSheet(
            Styles.get_label_style(size=11, color=Styles.COLOR_TEXT_MUTED)
            + "; padding: 4px 14px; "
            + Styles.get_transparent_label_style()
        )
        self._refresh_attribution_text()
        skeleton = getattr(self, "_book_skeleton", None)
        if skeleton is not None:
            skeleton.refresh_styles()

    def _refresh_move_styles(self) -> None:
        self.move_list_label.setStyleSheet(
            Styles.get_label_style(size=14, bold=True)
        )
        self.move_input.refresh_styles()
        self.engine_status_label.setStyleSheet(
            Styles.get_engine_status_style(Styles.COLOR_TEXT_MUTED)
        )
