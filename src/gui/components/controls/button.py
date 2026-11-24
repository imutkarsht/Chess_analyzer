"""Single reusable button component for the whole app.

One widget and one stylesheet generator replace the ad-hoc button styles that
used to live in ``styles.py`` getters, helper factories and per-widget QSS:

* nine variants: primary, filled, outlined, tonal, hollow, ghost, danger, link, segment
* four sizes with optional icon-only and full-width layouts
* built-in loading state (spinner + input lock) and checkable support

Call sites never ship their own button QSS; the look comes from the
central ``theme_template.qss`` matrix via the ``btnVariant`` / ``btnSize`` /
``btnDanger`` properties, so theme and accent changes propagate everywhere
without rebuilding per-widget stylesheets.
"""

from __future__ import annotations

from enum import StrEnum

from PyQt6.QtCore import QRectF, QSize, Qt, QTimer
from PyQt6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import QPushButton, QSizePolicy, QWidget

from src.gui.styles import Styles
from src.gui.theme import ThemeManager
from src.gui.utils.icons import HAS_QTAWESOME

try:
    import qtawesome as qta
except ImportError:
    qta = None


class ButtonVariant(StrEnum):
    """Visual variants; ``danger`` is the outlined destructive look."""

    PRIMARY = "primary"
    FILLED = "filled"
    OUTLINED = "outlined"
    TONAL = "tonal"
    HOLLOW = "hollow"
    GHOST = "ghost"
    DANGER = "danger"
    LINK = "link"
    SEGMENT = "segment"


class ButtonSize(StrEnum):
    XS = "xs"
    SM = "sm"
    MD = "md"
    LG = "lg"


_SIZE_SPECS: dict[ButtonSize, dict[str, int]] = {
    ButtonSize.XS: {"height": 22, "icon": 12, "font": 11, "pad_v": 1, "pad_h": 7},
    ButtonSize.SM: {"height": 28, "icon": 14, "font": 12, "pad_v": 4, "pad_h": 10},
    ButtonSize.MD: {"height": 34, "icon": 16, "font": 13, "pad_v": 8, "pad_h": 16},
    ButtonSize.LG: {"height": 42, "icon": 18, "font": 14, "pad_v": 10, "pad_h": 22},
}

_ICON_POSITIONS = ("left", "right", "only")


class Button(QPushButton):
    """The app's only button widget.

    ``icon`` accepts a qtawesome name (recolored per variant) or a ready
    ``QIcon``. ``icon_position="only"`` renders a square icon button and
    requires a tooltip for accessibility. ``loading`` swaps the icon for a
    spinner and blocks input until cleared.
    """

    def __init__(
        self,
        text: str = "",
        variant: ButtonVariant | str = ButtonVariant.PRIMARY,
        size: ButtonSize | str = ButtonSize.MD,
        *,
        icon: QIcon | str | None = None,
        icon_position: str = "left",
        icon_size: int | None = None,
        loading: bool = False,
        checkable: bool = False,
        full_width: bool = False,
        align: str | None = None,
        accent: str | None = None,
        danger: bool = False,
        text_color: str | None = None,
        font_size: int | None = None,
        font_weight: int | None = None,
        tooltip: str | None = None,
        on_click=None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(text, parent)
        if icon_position not in _ICON_POSITIONS:
            raise ValueError(f"icon_position must be one of {_ICON_POSITIONS}")
        self._variant = ButtonVariant(variant)
        self._size = ButtonSize(size)
        self._icon_spec = icon
        self._icon_position = icon_position
        self._icon_size_override = icon_size
        self._align = align
        self._accent = accent
        self._danger = danger
        self._text_color = text_color
        self._font_size = font_size
        self._font_weight = font_weight
        self._loading = False
        self._enabled_before_loading = True
        self._spin_angle = 0

        self._spin_timer = QTimer(self)
        self._spin_timer.setInterval(70)
        self._spin_timer.timeout.connect(self._advance_spinner)

        self.setCheckable(checkable)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        if tooltip:
            self.setToolTip(tooltip)
        if full_width:
            self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        if icon_position == "only":
            self.setText("")
            side = _SIZE_SPECS[self._size]["height"]
            self.setFixedSize(side, side)
        else:
            self.setMinimumHeight(_SIZE_SPECS[self._size]["height"])

        # Theme/accent changes must retint the icon and regenerate the QSS even
        # when a parent widget forgets to call refresh_styles().
        theme_manager = ThemeManager.instance()
        theme_manager.theme_changed.connect(self._on_theme_changed)
        theme_manager.accent_changed.connect(self._on_theme_changed)

        self.refresh_styles()
        if icon is not None:
            self._apply_icon()
        if loading:
            self.set_loading(True)
        if on_click is not None:
            self.clicked.connect(on_click)

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------
    @property
    def variant(self) -> ButtonVariant:
        return self._variant

    @property
    def size(self) -> ButtonSize:
        return self._size

    def set_variant(self, variant: ButtonVariant | str) -> None:
        self._variant = ButtonVariant(variant)
        self.refresh_styles()
        self._apply_icon()

    def set_size(self, size: ButtonSize | str) -> None:
        self._size = ButtonSize(size)
        spec = _SIZE_SPECS[self._size]
        if self._icon_position == "only":
            self.setFixedSize(spec["height"], spec["height"])
        else:
            self.setMinimumHeight(spec["height"])
        self.refresh_styles()
        self._apply_icon()

    def set_accent(self, accent: str | None) -> None:
        """Override the palette accent for this instance only."""
        self._accent = accent
        self.refresh_styles()
        self._apply_icon()

    def set_align(self, align: str | None) -> None:
        """Change text/icon alignment (left, center or right)."""
        self._align = align
        self.refresh_styles()

    def set_danger(self, danger: bool) -> None:
        """Recolor a variant with the destructive tone."""
        self._danger = danger
        self.refresh_styles()
        self._apply_icon()

    def set_text_color(self, color: str | None) -> None:
        """Override the variant's text (and icon) colour for this instance."""
        self._text_color = color
        self.refresh_styles()
        self._apply_icon()

    def set_icon_spec(self, icon: QIcon | str | None) -> None:
        self._icon_spec = icon
        self._apply_icon()

    def is_loading(self) -> bool:
        return self._loading

    def set_loading(self, loading: bool) -> None:
        """Show a spinner and block input while ``loading`` is true."""
        if loading == self._loading:
            return
        self._loading = loading
        if loading:
            self._enabled_before_loading = self.isEnabled()
            self.setEnabled(False)
            self._spin_angle = 0
            self._apply_spinner()
            self._spin_timer.start()
        else:
            self._spin_timer.stop()
            self._apply_icon()
            self.setEnabled(self._enabled_before_loading)

    def refresh_styles(self) -> None:
        """Publish style properties for the global QSS matrix and re-tint the icon.

        The central template owns every palette-driven declaration via the
        ``btnVariant`` / ``btnSize`` / ``btnDanger`` properties, so a theme
        change costs one property re-publish instead of a stylesheet rebuild
        per button. Only instance-specific tweaks that the matrix cannot
        express (alignment, custom fonts/colours, or a per-instance accent)
        remain on a small per-widget override sheet.
        """
        self._publish_style_properties()
        if self._accent:
            # A per-instance accent cannot be expressed in the global matrix;
            # fall back to the legacy generated sheet for this button alone.
            self.setStyleSheet(
                Styles.get_button_qss(
                    variant=self._variant.value,
                    size=self._size.value,
                    accent=self._accent,
                    align=self._align,
                    danger=self._danger,
                    text_color=self._text_color,
                    font_size=self._font_size,
                    font_weight=self._font_weight,
                )
            )
        else:
            self._apply_style_overrides()
        self.style().unpolish(self)
        self.style().polish(self)
        self._apply_icon()

    def _publish_style_properties(self) -> None:
        self.setProperty("btnVariant", self._variant.value)
        self.setProperty("btnSize", self._size.value)
        self.setProperty("btnDanger", self._danger)

    def _apply_style_overrides(self) -> None:
        """Minimal per-widget sheet for tweaks the global matrix cannot express."""
        declarations = []
        if self._align:
            declarations.append(f"text-align: {self._align};")
        if self._font_size is not None:
            declarations.append(f"font-size: {self._font_size}px;")
        if self._font_weight is not None:
            declarations.append(f"font-weight: {self._font_weight};")
        if self._text_color:
            declarations.append(f"color: {self._text_color};")
        self.setStyleSheet(
            f"QPushButton {{ {' '.join(declarations)} }}" if declarations else ""
        )

    def _on_theme_changed(self, *_args) -> None:
        try:
            self.refresh_styles()
        except RuntimeError:
            # Qt may still deliver a queued theme signal after the C++ widget
            # has been deleted; there is nothing left to restyle.
            pass

    # ------------------------------------------------------------------
    # Icons and spinner
    # ------------------------------------------------------------------
    def _icon_pixel_size(self) -> int:
        return self._icon_size_override or _SIZE_SPECS[self._size]["icon"]

    def _icon_color(self) -> str:
        v = self._variant
        if self._text_color:
            return self._text_color
        if v is ButtonVariant.PRIMARY:
            # Destructive primaries keep the white label/icon for contrast.
            return Styles.COLOR_ON_ACCENT
        if self._danger or v is ButtonVariant.DANGER:
            return Styles.COLOR_BLUNDER
        if v is ButtonVariant.OUTLINED or v is ButtonVariant.TONAL:
            return self._accent or Styles.COLOR_ACCENT
        return Styles.COLOR_TEXT_SECONDARY

    def _apply_icon(self) -> None:
        if self._loading:
            return
        side = self._icon_pixel_size()
        gap = 0 if self._icon_position == "only" else max(3, side // 4)
        self.setIconSize(QSize(side + gap, side))
        spec = self._icon_spec
        if isinstance(spec, QIcon):
            icon = spec
        elif isinstance(spec, str) and HAS_QTAWESOME:
            icon = qta.icon(spec, color=self._icon_color())
        else:
            icon = QIcon()
        if gap and not icon.isNull():
            # Qt hardcodes a tight icon/text gap; a transparent strip on the
            # icon keeps the label readable without per-widget QSS overrides.
            pixmap = QPixmap(side + gap, side)
            pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pixmap)
            icon.paint(painter, 0, 0, side, side)
            painter.end()
            icon = QIcon(pixmap)
        self.setIcon(icon)

    def _spinner_icon(self) -> QIcon:
        side = self._icon_pixel_size()
        pixmap = QPixmap(side, side)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor(self._icon_color()))
        pen.setWidthF(max(2.0, side / 8))
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.translate(side / 2, side / 2)
        painter.rotate(self._spin_angle)
        inset = max(1.5, side / 8)
        painter.drawArc(
            QRectF(-side / 2 + inset, -side / 2 + inset, side - 2 * inset, side - 2 * inset),
            0,
            270 * 16,
        )
        painter.end()
        return QIcon(pixmap)

    def _apply_spinner(self) -> None:
        self.setIconSize(QSize(self._icon_pixel_size(), self._icon_pixel_size()))
        self.setIcon(self._spinner_icon())

    def _advance_spinner(self) -> None:
        self._spin_angle = (self._spin_angle + 30) % 360
        self._apply_spinner()

    def hideEvent(self, event) -> None:  # noqa: N802 - Qt override
        # Do not animate off-screen; resume when shown again.
        if self._loading:
            self._spin_timer.stop()
        super().hideEvent(event)

    def showEvent(self, event) -> None:  # noqa: N802 - Qt override
        super().showEvent(event)
        if self._loading and not self._spin_timer.isActive():
            self._spin_timer.start()
