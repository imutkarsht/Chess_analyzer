# SPDX-License-Identifier: GPL-3.0-only
"""Model-only renderer for shareable game report cards."""

from __future__ import annotations

import math
from collections.abc import Mapping

import chess
from PyQt6.QtCore import QLineF, QRectF, Qt
from PyQt6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QImage,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)

from src.backend.storage.models import GameAnalysis
from src.constants import APP_VERSION, DEFAULT_BOARD_THEME, WEBSITE_URL
from src.gui.board.mini_board import MiniBoardConfig, render_mini_board_pixmap
from src.gui.styles import Styles
from src.utils.config import ConfigManager
from src.utils.path_utils import get_resource_path

_CLASSIFICATIONS = (
    "Brilliant",
    "Great",
    "Best",
    "Excellent",
    "Good",
    "Book",
    "Inaccuracy",
    "Mistake",
    "Miss",
    "Blunder",
)


class ShareReportRenderer:
    """Render a fixed-size opaque PNG from game analysis data."""

    WIDTH = 1200
    HEIGHT = 675

    @staticmethod
    def can_render(game: GameAnalysis | None) -> bool:
        if game is None or game.status != "completed":
            return False
        summary = game.summary
        return (
            isinstance(summary, Mapping)
            and isinstance(summary.get("white"), Mapping)
            and isinstance(summary.get("black"), Mapping)
        )

    @classmethod
    def render(cls, game: GameAnalysis) -> QImage:
        """Create a report image without reading widgets or running analysis."""
        if not cls.can_render(game):
            raise ValueError("A game must have analysis data before it can be shared.")

        image = cls._new_image()
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        try:
            cls._draw_background(painter)
            cls._draw_matchup(painter, game)
            cls._draw_accuracy(painter, game)
            cls._draw_evaluation(painter, game)
            cls._draw_classifications(painter, game)
            cls._draw_final_board(painter, game)
            cls._draw_footer(painter)
        finally:
            painter.end()
        return image

    @staticmethod
    def markdown_summary(game: GameAnalysis) -> str:
        """Format a compact Markdown report from the same model data."""
        if not ShareReportRenderer.can_render(game):
            raise ValueError("A game must have analysis data before it can be shared.")

        metadata = game.metadata
        white = game.summary["white"]
        black = game.summary["black"]
        opening = _opening_context(metadata.eco, metadata.opening)
        termination = _termination_suffix(metadata.termination_mode)
        white_name = _display_value(metadata.white, "White")
        black_name = _display_value(metadata.black, "Black")
        lines = [
            f"# Game Report: {white_name} vs {black_name}",
            "",
            f"- **Result:** {_result_text(metadata.result)}{f' · {termination}' if termination else ''}",
            f"- **Date:** {_display_value(metadata.date, 'Unknown')}",
            f"- **Time control:** {_display_value(metadata.time_control, 'Unknown')}",
            f"- **Opening:** {opening}",
            (
                "- **Accuracy:** "
                f"White {_format_percent(white.get('accuracy'))}; "
                f"Black {_format_percent(black.get('accuracy'))}"
            ),
            (
                "- **ACPL:** "
                f"White {_format_number(white.get('acpl'))}; "
                f"Black {_format_number(black.get('acpl'))}"
            ),
            "",
            "**Move classifications**",
        ]
        for classification in _CLASSIFICATIONS:
            white_count = _format_count(white.get(classification, 0))
            black_count = _format_count(black.get(classification, 0))
            lines.append(
                f"- {classification}: White {white_count}, Black {black_count}"
            )
        lines.extend(("", f"[Chess Analyzer Pro v{APP_VERSION}]({WEBSITE_URL})"))
        return "\n".join(lines)

    @staticmethod
    def _new_image() -> QImage:
        image = QImage(
            ShareReportRenderer.WIDTH,
            ShareReportRenderer.HEIGHT,
            QImage.Format.Format_ARGB32_Premultiplied,
        )
        background = QColor(Styles.COLOR_BACKGROUND)
        background.setAlpha(255)
        image.fill(background)
        return image

    @classmethod
    def _draw_background(cls, painter: QPainter) -> None:
        cls._draw_panel(painter, QRectF(40, 54, 1120, 120))
        cls._draw_panel(painter, QRectF(40, 190, 270, 155))
        cls._draw_panel(painter, QRectF(325, 190, 270, 155))
        cls._draw_panel(painter, QRectF(610, 190, 550, 155))
        cls._draw_panel(painter, QRectF(40, 360, 760, 270))
        cls._draw_panel(painter, QRectF(820, 360, 340, 270))

    @staticmethod
    def _draw_panel(painter: QPainter, rect: QRectF) -> None:
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(Styles.COLOR_SURFACE_CARD))
        painter.drawRoundedRect(rect, 14, 14)

    @classmethod
    def _draw_matchup(cls, painter: QPainter, game: GameAnalysis) -> None:
        metadata = game.metadata
        logo_path = get_resource_path("assets/images/logo.png")
        logo = QPixmap(logo_path)
        if not logo.isNull():
            painter.drawPixmap(QRectF(48, 17, 26, 26), logo, QRectF(logo.rect()))
        cls._draw_text(
            painter,
            QRectF(82, 16, 300, 30),
            "CHESS ANALYZER PRO",
            15,
            Styles.COLOR_ACCENT,
            QFont.Weight.Bold,
        )
        cls._draw_text(
            painter,
            QRectF(860, 16, 292, 30),
            "GAME REPORT",
            13,
            Styles.COLOR_TEXT_SECONDARY,
            QFont.Weight.DemiBold,
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
        )

        cls._draw_text(
            painter,
            QRectF(62, 69, 420, 20),
            "WHITE",
            12,
            Styles.COLOR_TEXT_MUTED,
            QFont.Weight.Bold,
        )
        cls._draw_text(
            painter,
            QRectF(62, 87, 420, 36),
            _display_value(metadata.white, "White"),
            25,
            Styles.COLOR_TEXT_PRIMARY,
            QFont.Weight.Bold,
        )
        cls._draw_text(
            painter,
            QRectF(62, 126, 420, 22),
            f"ELO  {_display_value(metadata.white_elo, 'Unrated')}",
            13,
            Styles.COLOR_TEXT_SECONDARY,
        )

        cls._draw_text(
            painter,
            QRectF(518, 82, 164, 40),
            _display_value(metadata.result, "--"),
            26,
            Styles.COLOR_TEXT_PRIMARY,
            QFont.Weight.Bold,
            Qt.AlignmentFlag.AlignCenter,
        )
        cls._draw_text(
            painter,
            QRectF(518, 121, 164, 22),
            _result_display(metadata.result, metadata.termination_mode),
            11,
            Styles.COLOR_TEXT_SECONDARY,
            QFont.Weight.DemiBold,
            Qt.AlignmentFlag.AlignCenter,
        )

        cls._draw_text(
            painter,
            QRectF(718, 69, 420, 20),
            "BLACK",
            12,
            Styles.COLOR_TEXT_MUTED,
            QFont.Weight.Bold,
        )
        cls._draw_text(
            painter,
            QRectF(718, 87, 420, 36),
            _display_value(metadata.black, "Black"),
            25,
            Styles.COLOR_TEXT_PRIMARY,
            QFont.Weight.Bold,
        )
        cls._draw_text(
            painter,
            QRectF(718, 126, 420, 22),
            f"ELO  {_display_value(metadata.black_elo, 'Unrated')}",
            13,
            Styles.COLOR_TEXT_SECONDARY,
        )

        moves = _full_move_count(game)
        details = [
            f"DATE  {_display_value(metadata.date, 'Unknown')}",
            f"TIME CONTROL  {_display_value(metadata.time_control, 'Unknown')}",
            f"{moves} MOVES",
        ]
        cls._draw_text(
            painter,
            QRectF(62, 151, 1076, 18),
            "     ·     ".join(details),
            11,
            Styles.COLOR_TEXT_MUTED,
        )

    @classmethod
    def _draw_accuracy(cls, painter: QPainter, game: GameAnalysis) -> None:
        for side, x, data in (
            ("WHITE", 40, game.summary["white"]),
            ("BLACK", 325, game.summary["black"]),
        ):
            cls._draw_text(
                painter,
                QRectF(x + 18, 199, 230, 22),
                f"{side} ACCURACY",
                12,
                Styles.COLOR_TEXT_SECONDARY,
                QFont.Weight.Bold,
            )
            cls._draw_accuracy_gauge(
                painter, x + 76, 278, data.get("accuracy")
            )
            cls._draw_text(
                painter,
                QRectF(x + 143, 257, 112, 42),
                f"ACPL\n{_format_number(data.get('acpl'))}",
                13,
                Styles.COLOR_TEXT_SECONDARY,
                QFont.Weight.DemiBold,
            )

    @classmethod
    def _draw_accuracy_gauge(
        cls, painter: QPainter, center_x: int, center_y: int, value
    ) -> None:
        accuracy = _finite_number(value)
        rect = QRectF(center_x - 43, center_y - 43, 86, 86)
        background_pen = QPen(QColor(Styles.COLOR_BORDER), 9)
        background_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(background_pen)
        painter.drawArc(rect, 0, 360 * 16)

        if accuracy is not None:
            accuracy = max(0.0, min(100.0, accuracy))
            progress_pen = QPen(
                QColor(Styles.get_accuracy_color(accuracy)), 9
            )
            progress_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(progress_pen)
            painter.drawArc(rect, 90 * 16, -int(accuracy * 3.6 * 16))

        cls._draw_text(
            painter,
            QRectF(center_x - 38, center_y - 15, 76, 30),
            _format_percent(value),
            16,
            Styles.COLOR_TEXT_PRIMARY,
            QFont.Weight.Bold,
            Qt.AlignmentFlag.AlignCenter,
        )

    @classmethod
    def _draw_evaluation(cls, painter: QPainter, game: GameAnalysis) -> None:
        cls._draw_text(
            painter,
            QRectF(628, 199, 500, 22),
            "EVALUATION",
            12,
            Styles.COLOR_TEXT_SECONDARY,
            QFont.Weight.Bold,
        )
        plot = QRectF(640, 230, 490, 94)
        middle = plot.center().y()
        values = []
        for move in game.moves:
            value = _finite_number(move.eval_after_cp)
            if value is not None:
                values.append(max(-10.0, min(10.0, value / 100.0)))
            elif move.eval_after_mate is not None:
                mate = _finite_number(move.eval_after_mate)
                if mate is not None:
                    values.append(10.0 if mate > 0 else -10.0 if mate < 0 else 0.0)
        if not values:
            cls._draw_text(
                painter,
                plot,
                "Evaluation data unavailable",
                13,
                Styles.COLOR_TEXT_MUTED,
                alignment=Qt.AlignmentFlag.AlignCenter,
            )
            return

        path = QPainterPath()
        points = []
        samples = []
        for index, value in enumerate(values):
            x = plot.left() + (
                index * plot.width() / max(1, len(values) - 1)
            )
            y = plot.center().y() - (value / 10.0) * (plot.height() / 2)
            point = (x, y)
            points.append(point)
            samples.append((x, y, value))
            if index == 0:
                path.moveTo(*point)
            else:
                path.lineTo(*point)

        cls._draw_evaluation_fill(painter, samples, middle)
        painter.setPen(
            QPen(QColor(Styles.COLOR_BORDER), 1, Qt.PenStyle.DashLine)
        )
        painter.drawLine(QLineF(plot.left(), middle, plot.right(), middle))
        pen = QPen(QColor(Styles.COLOR_ACCENT), 3)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.drawPath(path)
        if len(points) == 1:
            painter.setBrush(QColor(Styles.COLOR_ACCENT))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QRectF(points[0][0] - 3, points[0][1] - 3, 6, 6))

    @staticmethod
    def _draw_evaluation_fill(
        painter: QPainter, samples: list[tuple[float, float, float]], zero_y: float
    ) -> None:
        for first, second in zip(samples, samples[1:], strict=False):
            x1, y1, value1 = first
            x2, y2, value2 = second
            if value1 * value2 < 0:
                ratio = -value1 / (value2 - value1)
                cross_x = x1 + (x2 - x1) * ratio
                cross_y = zero_y
                segments = (
                    ((x1, y1), (cross_x, cross_y), value1),
                    ((cross_x, cross_y), (x2, y2), value2),
                )
            else:
                segments = (((x1, y1), (x2, y2), value1),)
            for start, end, value in segments:
                fill = QPainterPath()
                fill.moveTo(start[0], zero_y)
                fill.lineTo(*start)
                fill.lineTo(*end)
                fill.lineTo(end[0], zero_y)
                fill.closeSubpath()
                color = QColor(
                    Styles.COLOR_BEST if value >= 0 else Styles.COLOR_BLUNDER
                )
                color.setAlpha(28)
                painter.fillPath(fill, color)

    @classmethod
    def _draw_classifications(cls, painter: QPainter, game: GameAnalysis) -> None:
        cls._draw_text(
            painter,
            QRectF(58, 372, 700, 24),
            "MOVE CLASSIFICATIONS",
            12,
            Styles.COLOR_TEXT_SECONDARY,
            QFont.Weight.Bold,
        )
        cls._draw_text(
            painter,
            QRectF(58, 396, 460, 21),
            _opening_context(game.metadata.eco, game.metadata.opening),
            11,
            Styles.COLOR_TEXT_MUTED,
        )
        cls._draw_text(
            painter,
            QRectF(542, 396, 95, 21),
            "WHITE",
            10,
            Styles.COLOR_TEXT_MUTED,
            QFont.Weight.Bold,
            Qt.AlignmentFlag.AlignCenter,
        )
        cls._draw_text(
            painter,
            QRectF(668, 396, 95, 21),
            "BLACK",
            10,
            Styles.COLOR_TEXT_MUTED,
            QFont.Weight.Bold,
            Qt.AlignmentFlag.AlignCenter,
        )
        white = game.summary["white"]
        black = game.summary["black"]
        for index, name in enumerate(_CLASSIFICATIONS):
            y = 417 + index * 20
            color = QColor(Styles.get_class_color(name))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color)
            painter.drawEllipse(QRectF(60, y + 6, 8, 8))
            cls._draw_text(
                painter,
                QRectF(78, y, 390, 20),
                name,
                12,
                Styles.COLOR_TEXT_PRIMARY,
                QFont.Weight.DemiBold,
            )
            cls._draw_text(
                painter,
                QRectF(542, y, 95, 20),
                _format_count(white.get(name, 0)),
                12,
                Styles.COLOR_TEXT_PRIMARY,
                QFont.Weight.Bold,
                Qt.AlignmentFlag.AlignCenter,
            )
            cls._draw_text(
                painter,
                QRectF(668, y, 95, 20),
                _format_count(black.get(name, 0)),
                12,
                Styles.COLOR_TEXT_PRIMARY,
                QFont.Weight.Bold,
                Qt.AlignmentFlag.AlignCenter,
            )

    @classmethod
    def _draw_final_board(cls, painter: QPainter, game: GameAnalysis) -> None:
        cls._draw_text(
            painter,
            QRectF(840, 372, 300, 24),
            "FINAL POSITION",
            12,
            Styles.COLOR_TEXT_SECONDARY,
            QFont.Weight.Bold,
        )
        metadata = game.metadata
        fen = _final_fen(game)
        board_theme = ConfigManager().get("board_theme", DEFAULT_BOARD_THEME)
        last_move = (
            game.moves[-1].uci
            if game.moves and isinstance(game.moves[-1].uci, str)
            else None
        )
        config = MiniBoardConfig(
            size=240,
            coordinates=False,
            chess960=metadata.chess960,
            board_theme=board_theme,
            last_move_uci=last_move,
        )
        pixmap = render_mini_board_pixmap(fen, config)
        if pixmap.isNull():
            pixmap = render_mini_board_pixmap(chess.STARTING_FEN, config)
        if not pixmap.isNull():
            painter.drawPixmap(QRectF(870, 390, 240, 240), pixmap, QRectF(pixmap.rect()))

    @classmethod
    def _draw_footer(cls, painter: QPainter) -> None:
        cls._draw_text(
            painter,
            QRectF(48, 644, 700, 18),
            f"Chess Analyzer Pro v{APP_VERSION}  ·  Share your game, keep improving",
            10,
            Styles.COLOR_TEXT_MUTED,
        )
        cls._draw_text(
            painter,
            QRectF(750, 644, 402, 18),
            WEBSITE_URL,
            10,
            Styles.COLOR_TEXT_SECONDARY,
            alignment=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
        )

    @staticmethod
    def _draw_text(
        painter: QPainter,
        rect: QRectF,
        text: str,
        pixel_size: int,
        color: str,
        weight: QFont.Weight = QFont.Weight.Normal,
        alignment: Qt.AlignmentFlag = (
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        ),
    ) -> None:
        font = QFont()
        font.setPixelSize(pixel_size)
        font.setWeight(weight)
        painter.setFont(font)
        painter.setPen(QColor(color))
        metrics = QFontMetrics(font)
        display_text = metrics.elidedText(
            str(text), Qt.TextElideMode.ElideRight, max(0, int(rect.width()))
        )
        painter.drawText(rect, alignment, display_text)


def _final_fen(game: GameAnalysis) -> str:
    metadata = game.metadata
    if metadata.last_fen:
        try:
            chess.Board(metadata.last_fen, chess960=metadata.chess960)
            return metadata.last_fen
        except (ValueError, AssertionError, TypeError, AttributeError):
            pass

    if game.moves:
        last_move = game.moves[-1]
        try:
            board = chess.Board(
                last_move.fen_before or metadata.starting_fen or chess.STARTING_FEN,
                chess960=metadata.chess960,
            )
            if not isinstance(last_move.uci, str) or not last_move.uci:
                return board.fen()
            move = chess.Move.from_uci(last_move.uci)
            if move in board.legal_moves:
                board.push(move)
            return board.fen()
        except (ValueError, AssertionError, TypeError, AttributeError):
            pass

    if metadata.starting_fen:
        try:
            chess.Board(metadata.starting_fen, chess960=metadata.chess960)
            return metadata.starting_fen
        except (ValueError, AssertionError, TypeError, AttributeError):
            pass
    return chess.STARTING_FEN


def _full_move_count(game: GameAnalysis) -> int:
    if game.moves:
        return (len(game.moves) + 1) // 2
    return max(0, game.total_moves_count)


def _opening_context(eco: str | None, opening: str | None) -> str:
    parts = [
        value
        for value in (eco, opening)
        if value and str(value).strip() and str(value).strip() != "?"
    ]
    return " · ".join(parts) if parts else "Opening unavailable"


def _termination_suffix(mode: str | None) -> str:
    if mode == "resignation":
        return "by resignation"
    if mode in {"timeout", "timeout_insufficient"}:
        return "by timeout"
    return ""


def _result_display(result: str | None, termination_mode: str | None) -> str:
    outcome = _result_text(result).upper()
    suffix = _termination_suffix(termination_mode)
    return f"{outcome} · {suffix.upper()}" if suffix else outcome


def _display_value(value, fallback: str) -> str:
    if value is None:
        return fallback
    text = str(value).strip()
    return text if text and text not in {"?", "*", "-"} else fallback


def _result_text(result: str | None) -> str:
    return {
        "1-0": "White wins",
        "0-1": "Black wins",
        "1/2-1/2": "Draw",
    }.get(result, "In progress")


def _finite_number(value) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _format_percent(value) -> str:
    number = _finite_number(value)
    return f"{number:.1f}%" if number is not None else "--"


def _format_number(value) -> str:
    number = _finite_number(value)
    if number is None:
        return "--"
    return str(round(number)) if number.is_integer() else f"{number:.1f}"


def _format_count(value) -> str:
    number = _finite_number(value)
    return str(max(0, int(number))) if number is not None else "0"
