"""Hand-drawn outline glyphs for toast notifications.

The toast design uses thin outline icons rather than qtawesome's solid glyphs,
so the five variants are painted at runtime. Painting keeps stroke weight and
optical size identical on every platform and avoids gaps in the free icon set
(for example, there is no outline warning triangle).
"""

from __future__ import annotations

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap, QPolygonF

_MIN_STROKE = 1.35
_STROKE_RATIO = 0.075

# Painted at 2x so the stroke stays crisp on HiDPI displays and is smoothly
# downscaled on standard-density screens.
_RENDER_SCALE = 2.0


def _stroke_width(size: float) -> float:
    return max(_MIN_STROKE, size * _STROKE_RATIO)


def paint_toast_glyph(
    painter: QPainter,
    variant: str,
    color: str,
    size: float,
    angle: float = 0.0,
) -> None:
    """Draw one variant glyph into the square ``size`` box at the painter origin."""
    stroke = _stroke_width(size)
    paintable = size - stroke
    centre = paintable / 2
    radius = paintable / 2 - stroke * 0.35

    pen = QPen(QColor(color))
    pen.setWidthF(stroke)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    if variant == "loading":
        painter.save()
        painter.translate(centre, centre)
        painter.rotate(angle)
        arc = radius - stroke * 0.3
        painter.drawArc(QRectF(-arc, -arc, arc * 2, arc * 2), 0, 300 * 16)
        painter.restore()
        return

    if variant == "warning":
        inset = stroke * 1.4
        painter.drawPolygon(
            QPolygonF(
                [
                    QPointF(centre, inset * 1.1),
                    QPointF(paintable - inset * 1.2, paintable - inset),
                    QPointF(inset * 1.2, paintable - inset),
                ]
            )
        )
    else:
        painter.drawEllipse(QPointF(centre, centre), radius, radius)

    if variant == "success":
        painter.drawLine(
            QPointF(size * 0.34, size * 0.52), QPointF(size * 0.46, size * 0.64)
        )
        painter.drawLine(
            QPointF(size * 0.46, size * 0.64), QPointF(size * 0.68, size * 0.38)
        )
    elif variant == "error":
        painter.drawLine(
            QPointF(size * 0.37, size * 0.37), QPointF(size * 0.63, size * 0.63)
        )
        painter.drawLine(
            QPointF(size * 0.63, size * 0.37), QPointF(size * 0.37, size * 0.63)
        )
    elif variant == "info":
        painter.setBrush(QColor(color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPointF(size * 0.5, size * 0.35), stroke * 0.62, stroke * 0.62)
        painter.setPen(pen)
        painter.drawLine(QPointF(size * 0.5, size * 0.48), QPointF(size * 0.5, size * 0.69))
    else:  # warning exclamation
        painter.drawLine(QPointF(size * 0.5, size * 0.42), QPointF(size * 0.5, size * 0.62))
        painter.setBrush(QColor(color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPointF(size * 0.5, size * 0.73), stroke * 0.62, stroke * 0.62)


def toast_icon(
    variant: str,
    color: str,
    size: int = 20,
    angle: float = 0.0,
) -> QIcon:
    """Render a toast glyph to a HiDPI-aware :class:`QIcon`."""
    px_size = max(1, int(round(size * _RENDER_SCALE)))
    pixmap = QPixmap(px_size, px_size)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    try:
        painter.scale(_RENDER_SCALE, _RENDER_SCALE)
        paint_toast_glyph(painter, variant, color, float(size), angle)
    finally:
        painter.end()

    pixmap.setDevicePixelRatio(_RENDER_SCALE)
    return QIcon(pixmap)
