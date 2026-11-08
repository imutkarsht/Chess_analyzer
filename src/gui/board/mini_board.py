"""Shared, configurable mini chess board used across the app."""

from __future__ import annotations

from dataclasses import dataclass, replace

import chess
import chess.svg
from PyQt6.QtCore import QByteArray, Qt
from PyQt6.QtGui import QPainter, QPixmap, QPixmapCache
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

from src.constants import DEFAULT_BOARD_THEME
from src.gui.styles import Styles
from src.gui.theme import ThemeManager
from src.utils.config import ConfigManager


def _requires_chess960(fen: str) -> bool:
    fields = fen.split(" ")
    return len(fields) > 2 and any(c not in "KQkq-" for c in fields[2])


@dataclass(frozen=True)
class MiniBoardConfig:
    """Everything a mini board may vary between call sites."""

    size: int = 100
    orientation: chess.Color = chess.WHITE
    coordinates: bool = False
    chess960: bool = False
    board_theme: str | None = None
    show_border: bool = True
    border_width: int = 1
    border_radius: int = 6
    border_color: str | None = None
    background: str | None = None
    padding: int = 0
    last_move_uci: str | None = None
    last_move_san: str | None = None
    show_last_move: bool = True
    # History cards and drill-down rows hold the FEN *before* the played move;
    # import thumbnails hold the final FEN. Applying the move here keeps that
    # distinction out of every call site.
    fen_before_move: bool = False
    square_light: str | None = None
    square_dark: str | None = None


def _theme_name(config: MiniBoardConfig) -> str:
    return config.board_theme or ConfigManager().get(
        "board_theme", DEFAULT_BOARD_THEME
    )


def _resolved_colors(config: MiniBoardConfig) -> tuple[str, str]:
    colors = Styles.get_board_colors(_theme_name(config))
    return (
        config.square_light or colors["light"],
        config.square_dark or colors["dark"],
    )


def _last_move(
    board: chess.Board, config: MiniBoardConfig
) -> chess.Move | None:
    if not config.show_last_move:
        return None
    try:
        if config.last_move_uci:
            move = chess.Move.from_uci(config.last_move_uci)
            # A final FEN is already past the move, so legality cannot be
            # checked there; a pre-move FEN must still validate it.
            if not config.fen_before_move or move in board.legal_moves:
                return move
        if config.last_move_san and config.fen_before_move:
            return board.parse_san(config.last_move_san)
    except (ValueError, AssertionError):
        return None
    return None


def _display_position(
    fen: str, config: MiniBoardConfig
) -> tuple[chess.Board, chess.Move | None]:
    board = chess.Board(
        fen, chess960=config.chess960 or _requires_chess960(fen)
    )
    last_move = _last_move(board, config)
    if last_move is not None and config.fen_before_move:
        board.push(last_move)
    return board, last_move


def _cache_key(fen: str, config: MiniBoardConfig) -> str:
    light, dark = _resolved_colors(config)
    return "|".join(
        (
            "mini-board-v1",
            fen,
            str(int(config.orientation)),
            str(config.size),
            str(int(config.coordinates)),
            str(int(config.chess960)),
            str(int(config.fen_before_move)),
            light,
            dark,
            config.last_move_uci or "",
            config.last_move_san or "",
            str(int(config.show_last_move)),
        )
    )


def render_mini_board_pixmap(
    fen: str, config: MiniBoardConfig | None = None
) -> QPixmap:
    """Render (or reuse) one mini board pixmap; safe for table delegates."""
    config = config or MiniBoardConfig()
    fen = fen or chess.STARTING_FEN
    key = _cache_key(fen, config)
    cached = QPixmapCache.find(key)
    if cached is not None and not cached.isNull():
        return cached

    try:
        board, last_move = _display_position(fen, config)
        light, dark = _resolved_colors(config)
        svg = chess.svg.board(
            board=board,
            size=config.size,
            coordinates=config.coordinates,
            orientation=config.orientation,
            lastmove=last_move,
            colors={"square light": light, "square dark": dark},
        )
        renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
        pixmap = QPixmap(config.size, config.size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        try:
            renderer.render(painter)
        finally:
            painter.end()
    except (ValueError, AssertionError):
        return QPixmap()

    if not pixmap.isNull():
        QPixmapCache.insert(key, pixmap)
    return pixmap


class MiniBoardWidget(QFrame):
    """A static mini board for card layouts."""

    def __init__(
        self,
        fen: str = chess.STARTING_FEN,
        config: MiniBoardConfig | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setObjectName("MiniBoardWidget")
        self._fen = fen or chess.STARTING_FEN
        self._config = config or MiniBoardConfig()
        self._label = QLabel()
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setStyleSheet("background: transparent; border: none;")

        self._layout = QVBoxLayout(self)
        self._layout.setSpacing(0)
        self._layout.addWidget(self._label)
        self._apply_geometry()

        manager = ThemeManager.instance()
        manager.theme_changed.connect(self._on_theme_changed)
        manager.accent_changed.connect(self._on_theme_changed)
        self.refresh_styles()

    @property
    def config(self) -> MiniBoardConfig:
        return self._config

    def _apply_geometry(self) -> None:
        border = self._config.border_width if self._config.show_border else 0
        inset = self._config.padding + border
        self._layout.setContentsMargins(inset, inset, inset, inset)
        side = self._config.size + 2 * inset
        self.setFixedSize(side, side)
        self._label.setFixedSize(self._config.size, self._config.size)

    def set_position(
        self,
        fen: str,
        *,
        last_move_uci: str | None = None,
        last_move_san: str | None = None,
        orientation: chess.Color | None = None,
    ) -> None:
        self._fen = fen or chess.STARTING_FEN
        changes: dict = {
            "last_move_uci": last_move_uci,
            "last_move_san": last_move_san,
        }
        if orientation is not None:
            changes["orientation"] = orientation
        self._config = replace(self._config, **changes)
        self.refresh_styles()

    def set_config(self, config: MiniBoardConfig) -> None:
        self._config = config
        self._apply_geometry()
        self.refresh_styles()

    def _on_theme_changed(self, *_args) -> None:
        self.refresh_styles()

    def refresh_styles(self, *_args) -> None:
        self._label.setPixmap(
            render_mini_board_pixmap(self._fen, self._config)
        )
        background = self._config.background or Styles.COLOR_SURFACE
        border_color = self._config.border_color or Styles.COLOR_BORDER
        border = (
            f"{self._config.border_width}px solid {border_color}"
            if self._config.show_border
            else "none"
        )
        self.setStyleSheet(
            f"""
            QFrame#MiniBoardWidget {{
                background-color: {background};
                border: {border};
                border-radius: {self._config.border_radius}px;
            }}
            """
        )
