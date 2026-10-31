"""Pulsing placeholder rows for the Opening Explorer book panel.

The online Lichess explorer is fetched off the UI thread, so the panel needs a
stable loading affordance: rendering the offline book while a live request is
in flight makes the list look like it already answered. These rows mirror the
geometry of a real book row (piece icon, SAN, game count, ratio bar) so the
swap to real data does not jump the layout.
"""

from PyQt6.QtCore import QAbstractAnimation
from PyQt6.QtWidgets import (
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
)

from src.gui.styles import Styles
from src.gui.theme.motion import Motion, MotionDuration, MotionEasing


class ExplorerBookSkeleton(QWidget):
    """Five breathing book-row placeholders."""

    ROW_COUNT = 5

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._animation = None
        self._effect: QGraphicsOpacityEffect | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        for _ in range(self.ROW_COUNT):
            layout.addWidget(self._build_row())

        self.refresh_styles()

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _build_row(self) -> QFrame:
        row = QFrame()
        row.setObjectName("explorerBookSkeletonRow")
        row.setMinimumHeight(40)

        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(14, 8, 14, 8)
        row_layout.setSpacing(8)

        icon = QFrame()
        icon.setObjectName("explorerBookSkeletonIcon")
        icon.setFixedSize(18, 18)
        row_layout.addWidget(icon)

        san_bar = QFrame()
        san_bar.setObjectName("explorerBookSkeletonBar")
        san_bar.setFixedSize(46, 10)
        row_layout.addWidget(san_bar)
        row_layout.addStretch()

        count_bar = QFrame()
        count_bar.setObjectName("explorerBookSkeletonBar")
        count_bar.setFixedSize(30, 10)
        row_layout.addWidget(count_bar)

        ratio_bar = QFrame()
        ratio_bar.setObjectName("explorerBookSkeletonRatio")
        ratio_bar.setFixedSize(140, 16)
        row_layout.addWidget(ratio_bar)

        return row

    def refresh_styles(self) -> None:
        """Rebuild row QSS from the live palette after a theme switch."""
        self.setStyleSheet(
            f"""
            QFrame#explorerBookSkeletonRow {{
                border: none;
                border-bottom: 1px solid {Styles.COLOR_BORDER};
                background: transparent;
            }}
            QFrame#explorerBookSkeletonIcon {{
                background-color: {Styles.COLOR_SURFACE_LIGHT};
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 4px;
            }}
            QFrame#explorerBookSkeletonBar {{
                background-color: {Styles.COLOR_SURFACE_LIGHT};
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 5px;
            }}
            QFrame#explorerBookSkeletonRatio {{
                background-color: {Styles.COLOR_SURFACE_LIGHT};
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 8px;
            }}
            """
        )

    # ------------------------------------------------------------------
    # Animation
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Begin the breathing animation, respecting reduced-motion settings."""
        if not Motion.enabled():
            return
        self.stop()
        self._effect = QGraphicsOpacityEffect(self)
        self._effect.setOpacity(0.35)
        self.setGraphicsEffect(self._effect)
        self._animation = Motion.animate_value(
            self,
            0.35,
            0.85,
            self._effect.setOpacity,
            duration=MotionDuration.PULSE,
            easing=MotionEasing.LOOP,
            loops=-1,
        )

    def stop(self) -> None:
        animation, self._animation = self._animation, None
        if animation is not None:
            animation.stop()
        if self._effect is not None:
            self._effect.setOpacity(0.85)

    def is_animating(self) -> bool:
        return (
            self._animation is not None
            and self._animation.state()
            == QAbstractAnimation.State.Running
        )
