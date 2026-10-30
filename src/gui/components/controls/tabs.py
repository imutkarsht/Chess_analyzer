"""Single reusable tab component for every surface in the app.

Two visual variants share one API and one stylesheet generator:

* ``TabVariant.UNDERLINE`` - plain labels with an accent underline under the
  active tab.
* ``TabVariant.SEGMENTED`` - a button-like control. With ``track=True`` the
  segments sit inside a rounded container and the active one is an elevated
  pill; with ``track=False`` each segment is its own bordered pill.

Every visual knob lives in :class:`TabAppearance`, so call sites never ship
their own tab QSS. The widget owns the bar and an optional ``QStackedWidget``:
pass a page to a tab and switching is handled for you, omit pages and it stays
a bar-only control for callers that drive their own content.
"""

from __future__ import annotations

from dataclasses import dataclass, fields, replace
from enum import StrEnum

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtGui import QFont, QIcon
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QSizePolicy,
    QStackedWidget,
    QTabBar,
    QVBoxLayout,
    QWidget,
)

from src.gui.styles import Styles

try:
    import qtawesome as qta
    HAS_QTAWESOME = True
except ImportError:
    HAS_QTAWESOME = False

_ACTIVE_STYLES = ("underline", "accent", "filled", "outline")
_MIXED_PAGE_MODES = (
    "Tabs cannot mix page-backed and bar-only tabs; pass a widget for every tab or none"
)


class TabVariant(StrEnum):
    """The two supported tab looks."""

    UNDERLINE = "underline"
    SEGMENTED = "segmented"


@dataclass(frozen=True)
class TabAppearance:
    """Every visual property of a :class:`Tabs` bar.

    ``padding`` follows CSS order: ``(top, right, bottom, left)``. ``accent``
    overrides the palette accent for the underline/outline state only, which
    lets one surface brand its tabs without touching the global theme.
    """

    variant: TabVariant = TabVariant.UNDERLINE
    spacing: int = 24
    padding: tuple[int, int, int, int] = (8, 18, 10, 18)
    font_size: int = 15
    font_weight: int = 600
    radius: int = 8
    track: bool = False
    track_padding: int = 4
    active_style: str = "underline"
    indicator_size: int = 3
    expand: bool = False
    icon_size: int = 16
    accent: str | None = None

    def __post_init__(self) -> None:
        if len(self.padding) != 4:
            raise ValueError("padding must be (top, right, bottom, left)")
        if any(value < 0 for value in self.padding):
            raise ValueError("padding values must be non-negative")
        if self.active_style not in _ACTIVE_STYLES:
            raise ValueError(f"active_style must be one of {_ACTIVE_STYLES}")

    @classmethod
    def for_variant(cls, variant: TabVariant) -> TabAppearance:
        """Design defaults for a variant, before caller overrides."""
        if variant is TabVariant.SEGMENTED:
            return cls(
                variant=variant,
                spacing=2,
                padding=(8, 16, 8, 16),
                font_size=14,
                track=True,
                expand=True,
            )
        return cls(variant=TabVariant.UNDERLINE)


class Tabs(QWidget):
    """Tab bar with two looks plus optional page switching.

    ``variant`` picks the design; keyword arguments override individual
    :class:`TabAppearance` fields::

        Tabs(TabVariant.UNDERLINE)
        Tabs(TabVariant.SEGMENTED, track=False, active_style="outline")
        Tabs(TabVariant.SEGMENTED, accent="#4CACEB", font_size=12)

    Pass a widget to :meth:`add_tab` to let the component switch pages, or add
    every tab without a widget to keep it a bar-only control.
    """

    current_changed = pyqtSignal(int)

    _FIELD_NAMES = frozenset(field.name for field in fields(TabAppearance))

    def __init__(
        self,
        variant: TabVariant | str | None = None,
        *,
        appearance: TabAppearance | None = None,
        parent: QWidget | None = None,
        **overrides: object,
    ) -> None:
        super().__init__(parent)
        self._appearance = self._resolve(variant, appearance, overrides)
        self._icons: list[QIcon | str | None] = []
        # ``None`` until the first tab declares whether this bar owns pages.
        self._has_pages: bool | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._track = QFrame()
        self._track.setObjectName("TabTrack")
        self._track.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._track_layout = QHBoxLayout(self._track)
        self._track_layout.setSpacing(0)

        self.bar = QTabBar()
        self.bar.setDrawBase(False)
        self.bar.setUsesScrollButtons(False)
        self.bar.setElideMode(Qt.TextElideMode.ElideNone)
        self.bar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.bar.currentChanged.connect(self._on_bar_changed)
        self._track_layout.addWidget(self.bar)
        self._track_layout.addStretch(1)

        root.addWidget(self._track)

        self.pages = QStackedWidget()
        self.pages.setVisible(False)
        self.pages.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        root.addWidget(self.pages, 1)

        self._sync_layout()
        self.refresh_styles()
        # A bar-only control must not inherit the parent's leftover height; the
        # policy flips to Expanding once pages are attached.
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    @property
    def appearance(self) -> TabAppearance:
        """The resolved look, including variant defaults and overrides."""
        return self._appearance

    def add_tab(
        self,
        label: str,
        widget: QWidget | None = None,
        icon: QIcon | str | None = None,
    ) -> int:
        """Append a tab, optionally binding a page, and return its index.

        ``icon`` accepts a ready ``QIcon`` or a qtawesome name; names are
        recoloured automatically for the active and inactive states.
        """
        self._check_page_mode(widget)
        index = self.bar.count()
        self._icons.append(icon)
        self.bar.addTab(self._icon(index), label)
        self._attach_page(index, widget)
        return index

    def remove_tab(self, index: int) -> None:
        """Remove a tab and its page without deleting the page widget."""
        if not 0 <= index < self.bar.count():
            raise IndexError(index)
        if self._has_pages:
            page = self.pages.widget(index)
            if page is not None:
                self.pages.removeWidget(page)
        self._icons.pop(index)
        self.bar.removeTab(index)
        if self.bar.count() == 0:
            self._has_pages = None

    def count(self) -> int:
        return self.bar.count()

    def current_index(self) -> int:
        return self.bar.currentIndex()

    def set_current_index(self, index: int) -> None:
        self.bar.setCurrentIndex(index)

    def tab_text(self, index: int) -> str:
        return self.bar.tabText(index)

    def set_tab_text(self, index: int, text: str) -> None:
        self.bar.setTabText(index, text)

    def page(self, index: int) -> QWidget | None:
        """The page bound to ``index``, or ``None`` for a bar-only bar."""
        return self.pages.widget(index) if self._has_pages else None

    def set_appearance(self, appearance: TabAppearance) -> None:
        """Apply a new look at runtime; tabs, pages and selection survive."""
        self._appearance = appearance
        self._sync_layout()
        self.refresh_styles()

    def refresh_styles(self) -> None:
        """Regenerate the stylesheet from the current theme and appearance."""
        a = self._appearance
        self.setStyleSheet(
            Styles.get_tabs_style(
                variant=a.variant.value,
                spacing=a.spacing,
                padding=a.padding,
                font_size=a.font_size,
                font_weight=a.font_weight,
                radius=a.radius,
                track=a.track,
                track_padding=a.track_padding,
                active_style=a.active_style,
                indicator_size=a.indicator_size,
                accent=a.accent,
            )
        )
        self._refresh_icons()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    @classmethod
    def _resolve(
        cls,
        variant: TabVariant | str | None,
        appearance: TabAppearance | None,
        overrides: dict[str, object],
    ) -> TabAppearance:
        requested = TabVariant(variant) if variant is not None else None
        if appearance is not None:
            if requested is not None and requested is not appearance.variant:
                raise ValueError("variant conflicts with appearance.variant")
            base = appearance
        else:
            base = TabAppearance.for_variant(requested or TabVariant.UNDERLINE)

        updates: dict[str, object] = {}
        for name, value in overrides.items():
            if name not in cls._FIELD_NAMES:
                raise TypeError(f"Unknown tab appearance option: {name!r}")
            if name == "variant":
                raise TypeError("Pass variant positionally")
            updates[name] = value
        return replace(base, **updates) if updates else base

    def _sync_layout(self) -> None:
        a = self._appearance
        margin = a.track_padding if a.track else 0
        self._track_layout.setContentsMargins(margin, margin, margin, margin)
        # Expanding shares the track evenly; otherwise the bar hugs its labels.
        self._track_layout.setStretch(0, 1 if a.expand else 0)
        self._track_layout.setStretch(1, 0 if a.expand else 1)
        self.bar.setExpanding(a.expand)
        self.bar.setIconSize(QSize(a.icon_size, a.icon_size))
        # QTabBar sizes tabs from the widget font, not from a ``::tab`` rule in
        # the stylesheet; without this the bold label can overflow its tab and
        # the underline ends up narrower or lopsided.
        font = self.bar.font()
        font.setPixelSize(a.font_size)
        font.setWeight(QFont.Weight(a.font_weight))
        self.bar.setFont(font)

    def _check_page_mode(self, widget: QWidget | None) -> None:
        """Reject mixing page-backed and bar-only tabs before mutating state."""
        if widget is None and self._has_pages:
            raise ValueError(_MIXED_PAGE_MODES)
        if widget is not None and self._has_pages is False:
            raise ValueError(_MIXED_PAGE_MODES)

    def _attach_page(self, index: int, widget: QWidget | None) -> None:
        if widget is None:
            self._has_pages = False
            return
        self._has_pages = True
        self.pages.addWidget(widget)
        self.pages.setVisible(True)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        current = self.bar.currentIndex()
        if 0 <= current < self.pages.count():
            self.pages.setCurrentIndex(current)
        else:
            self.pages.setCurrentIndex(index)

    def _icon(self, index: int) -> QIcon:
        spec = self._icons[index]
        if isinstance(spec, str):
            if not HAS_QTAWESOME:
                return QIcon()
            a = self._appearance
            if index != self.bar.currentIndex():
                color = Styles.COLOR_TEXT_SECONDARY
            elif a.active_style == "accent":
                color = (
                    Styles.COLOR_ON_ACCENT
                    if a.variant is TabVariant.SEGMENTED
                    else (a.accent or Styles.COLOR_ACCENT)
                )
            else:
                color = Styles.COLOR_TEXT_PRIMARY
            return qta.icon(spec, color=color)
        if isinstance(spec, QIcon):
            return spec
        return QIcon()

    def _refresh_icons(self) -> None:
        for index in range(self.bar.count()):
            if self._icons[index] is not None:
                self.bar.setTabIcon(index, self._icon(index))

    def _on_bar_changed(self, index: int) -> None:
        if self._has_pages and 0 <= index < self.pages.count():
            self.pages.setCurrentIndex(index)
        self._refresh_icons()
        self.current_changed.emit(index)
