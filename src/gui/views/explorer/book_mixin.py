"""Book-row rendering for the Opening Explorer page."""

from PyQt6.QtCore import QByteArray, Qt
from PyQt6.QtGui import QPainter, QPixmap
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QLayout

from src.backend.analysis.opening_db import _normalize_fen
from src.gui.styles import Styles
from src.gui.views.explorer.book_row import BookRowWidget
from src.gui.views.explorer.book_skeleton import ExplorerBookSkeleton
from src.gui.views.explorer.ratio_bar import RatioBar
from src.utils.logger import logger


class ExplorerBookMixin:
    """Builds local/Polyglot/Lichess rows and owns the loading skeleton."""

    # ------------------------------------------------------------------
    # Row widgets
    # ------------------------------------------------------------------

    def _get_piece_pixmap(self, symbol, size=18):
        cache_key = (symbol, size)
        if cache_key not in self._piece_pixmap_cache:
            from src.gui.board.piece_themes import (
                _load_theme_cached,
                get_current_theme_name,
            )

            pieces_svg = _load_theme_cached(get_current_theme_name())
            g_content = pieces_svg.get(symbol, "")
            if g_content:
                svg_str = (
                    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 45 45">'
                    f"{g_content}</svg>"
                )
                renderer = QSvgRenderer(QByteArray(svg_str.encode("utf-8")))
                pixmap = QPixmap(size, size)
                pixmap.fill(Qt.GlobalColor.transparent)
                painter = QPainter(pixmap)
                renderer.render(painter)
                painter.end()
                self._piece_pixmap_cache[cache_key] = pixmap
            else:
                self._piece_pixmap_cache[cache_key] = None
        return self._piece_pixmap_cache[cache_key]

    def _create_book_row_widget(self, san, info_text, piece_symbol=None, stats=None):
        row_widget = BookRowWidget(san, on_click=self.on_book_move_clicked, parent=self)
        row_widget.setStyleSheet(Styles.get_book_row_style())
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(14, 8, 14, 8)
        row_layout.setSpacing(8)

        left_layout = QHBoxLayout()
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)

        if piece_symbol:
            pixmap = self._get_piece_pixmap(piece_symbol)
            if pixmap:
                icon_label = QLabel()
                icon_label.setPixmap(pixmap)
                icon_label.setFixedSize(18, 18)
                icon_label.setStyleSheet(Styles.get_transparent_label_style())
                left_layout.addWidget(icon_label)

        lbl_san = QLabel(san)
        lbl_san.setStyleSheet(
            Styles.get_label_style(
                size=15, color=Styles.COLOR_TEXT_PRIMARY, bold=True
            )
            + " "
            + Styles.get_transparent_label_style()
        )
        left_layout.addWidget(lbl_san)

        row_layout.addLayout(left_layout)
        row_layout.addStretch()

        if stats:
            w_pct, d_pct, b_pct, count_str = stats

            right_layout = QHBoxLayout()
            right_layout.setContentsMargins(0, 0, 0, 0)
            right_layout.setSpacing(12)

            lbl_count = QLabel(count_str)
            lbl_count.setStyleSheet(
                Styles.get_label_style(
                    size=13, color=Styles.COLOR_TEXT_MUTED, weight=500
                )
                + " "
                + Styles.get_transparent_label_style()
            )
            right_layout.addWidget(lbl_count)

            ratio_bar = RatioBar(w_pct, d_pct, b_pct, self)
            right_layout.addWidget(ratio_bar)
            row_layout.addLayout(right_layout)
        elif info_text:
            lbl_info = QLabel(info_text)
            lbl_info.setStyleSheet(
                Styles.get_label_style(size=13, color=Styles.COLOR_TEXT_SECONDARY)
                + "; font-style: italic; "
                + Styles.get_transparent_label_style()
            )
            lbl_info.setMinimumWidth(0)
            row_layout.addWidget(lbl_info)

        return row_widget

    # ------------------------------------------------------------------
    # List lifecycle
    # ------------------------------------------------------------------

    def _clear_book_rows(self) -> None:
        self._clear_book_skeleton()
        for widget in self._book_row_widgets:
            self.book_layout.removeWidget(widget)
            # Hide and detach immediately: deleteLater() only runs on the next
            # event-loop turn, and until then stale rows keep painting over the
            # freshly built list.
            widget.hide()
            widget.setParent(None)
            widget.deleteLater()
        self._book_row_widgets = []
        self._current_book_count = 0
        self.book_container.setMinimumHeight(0)
        # The book container is transparent, so removed rows would otherwise
        # leave ghost pixels behind until the parent repaints.
        self.book_container.update()

    def _clear_book_skeleton(self) -> None:
        skeleton = getattr(self, "_book_skeleton", None)
        if skeleton is None:
            return
        skeleton.stop()
        self.book_layout.removeWidget(skeleton)
        skeleton.hide()
        skeleton.setParent(None)
        skeleton.deleteLater()
        self._book_skeleton = None

    def _finalize_book_layout(self) -> None:
        """Let the container grow so the scroll area scrolls instead of squeezing."""
        self.book_layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        self.book_layout.activate()
        self.book_container.setMinimumHeight(self.book_layout.sizeHint().height())
        self.book_container.update()

    def _update_book_toggle(self, suffix: str = "", *, loading: bool = False) -> None:
        arrow = "▼" if self.book_toggle.isChecked() else "▶"
        if loading:
            self.book_toggle.setText(f"{arrow}  Book Moves  (loading…)")
            self.book_toggle.show()
            self.book_scroll.setVisible(self.book_toggle.isChecked())
            return
        self.book_toggle.setText(
            f"{arrow}  Book Moves  ({self._current_book_count}){suffix}"
        )
        if self._current_book_count > 0:
            self.book_toggle.show()
            self.book_scroll.setVisible(self.book_toggle.isChecked())
        else:
            self.book_toggle.hide()
            self.book_scroll.hide()

    def _toggle_book(self, checked):
        self.book_scroll.setVisible(checked)
        self._update_book_toggle(loading=self._book_skeleton is not None)

    def _show_book_skeleton(self) -> None:
        """Replace the list with placeholder rows while Lichess is fetched."""
        self._clear_book_rows()
        skeleton = ExplorerBookSkeleton(self.book_container)
        self._book_skeleton = skeleton
        self.book_layout.addWidget(skeleton)
        skeleton.start()
        self.lichess_attribution.setVisible(False)
        self._update_book_toggle(loading=True)
        self._finalize_book_layout()

    # ------------------------------------------------------------------
    # Local book sources
    # ------------------------------------------------------------------

    def _draw_local_book(self, node_id) -> int:
        """Render the offline Polyglot/SQLite book; return the row count."""
        self._clear_book_rows()

        # Polyglot has higher priority than the SQLite ECO tree.
        polyglot_used = False
        current_path = self.config_manager.get("polyglot_book_path", "")
        if current_path != (self.polyglot_manager.book_path or ""):
            self.polyglot_manager.set_book_path(current_path if current_path else None)
        if self.polyglot_manager.is_available():
            try:
                board = self.board_widget.board
                entries = list(self.polyglot_manager.reader.find_all(board))
                if entries:
                    polyglot_used = True
                    entries.sort(key=lambda e: e.weight, reverse=True)
                    for entry in entries:
                        ply_move = entry.move
                        try:
                            san = board.san(ply_move)
                        except Exception:
                            san = ply_move.uci()
                        piece = board.piece_at(ply_move.from_square)
                        row_widget = self._create_book_row_widget(
                            san,
                            str(entry.weight),
                            piece.symbol() if piece else None,
                        )
                        self.book_layout.addWidget(row_widget)
                        self._book_row_widgets.append(row_widget)
            except Exception as e:
                logger.warning(f"Polyglot query failed: {e}", exc_info=True)

        if not polyglot_used:
            for san, move_name, piece_symbol in self._sqlite_book_entries(node_id):
                row_widget = self._create_book_row_widget(
                    san, move_name, piece_symbol
                )
                self.book_layout.addWidget(row_widget)
                self._book_row_widgets.append(row_widget)

        self._current_book_count = len(self._book_row_widgets)
        self._update_book_toggle()
        self._finalize_book_layout()
        return self._current_book_count

    def _sqlite_book_entries(
        self, node_id
    ) -> list[tuple[str, str, str | None]]:
        """Resolve child moves without mutating the live board."""
        if node_id is None:
            return []
        try:
            candidates = self.opening_db.get_children(node_id)
        except Exception as e:
            logger.warning(f"Error reading SQLite book moves: {e}")
            return []

        board = self.board_widget.board
        entries: list[tuple[str, str, str | None]] = []
        for san in candidates:
            try:
                move = board.parse_san(san)
                child_board = board.copy()
                child_board.push(move)
                child_fen = _normalize_fen(child_board.fen())

                move_name = ""
                child_node_id = self.opening_db.get_node_by_fen(child_fen)
                if child_node_id is not None:
                    child_openings = self.opening_db.get_openings_at_node(
                        child_node_id
                    )
                    if child_openings:
                        move_name = max(
                            child_openings, key=lambda x: len(x[1])
                        )[1]

                piece = board.piece_at(move.from_square)
                entries.append((san, move_name, piece.symbol() if piece else None))
            except Exception as e:
                logger.warning(f"Error processing SQLite book move {san}: {e}")
        return entries

    def _draw_local_book_fallback(self) -> None:
        """Show the local book after the online request failed or returned nothing."""
        node_id = self.opening_db.get_node_by_fen(
            _normalize_fen(self.board_widget.board.fen())
        )
        self._draw_local_book(node_id)
        if self._current_book_count:
            self._update_book_toggle("  · local book")
        self.lichess_attribution.setVisible(False)
        self.board_widget.draw_interactive_overlays()

    # ------------------------------------------------------------------
    # Lichess rows
    # ------------------------------------------------------------------

    @staticmethod
    def _format_count(total: int) -> str:
        if total >= 1_000_000:
            return f"{total / 1_000_000:.1f}M"
        if total >= 1000:
            return f"{total / 1000:.1f}K"
        return str(total)

    def on_lichess_explorer_finished(self, data):
        self._clear_book_rows()

        for move in data.get("moves", []):
            san = move.get("san")
            white_wins = move.get("white", 0)
            draws = move.get("draws", 0)
            black_wins = move.get("black", 0)
            total = white_wins + draws + black_wins
            if total == 0:
                continue

            w_pct = int(white_wins / total * 100)
            d_pct = int(draws / total * 100)
            b_pct = 100 - w_pct - d_pct
            stats = (w_pct, d_pct, b_pct, self._format_count(total))

            piece_symbol = None
            try:
                move_obj = self.board_widget.board.parse_san(san)
                piece = self.board_widget.board.piece_at(move_obj.from_square)
                if piece:
                    piece_symbol = piece.symbol()
            except Exception:
                pass

            row_widget = self._create_book_row_widget(
                san, None, piece_symbol, stats=stats
            )
            self.book_layout.addWidget(row_widget)
            self._book_row_widgets.append(row_widget)

        self._current_book_count = len(self._book_row_widgets)
        self._update_book_toggle()
        self.lichess_attribution.setVisible(self._current_book_count > 0)
        self._finalize_book_layout()
        self.board_widget.draw_interactive_overlays()
