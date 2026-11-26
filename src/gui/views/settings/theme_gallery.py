# SPDX-License-Identifier: GPL-3.0-only
"""Visual theme gallery for Appearance settings."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractButton,
    QButtonGroup,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
)

from src.gui.components import Label, TextRole, ThemeCard
from src.gui.theme import DARK, LIGHT, ThemeManager, ThemePalette

_SYSTEM_THEME = "system"
_BASE_THEME_IDS = ("light", "dark")
# Built-in order for the Themes section. Future bundles slot in here without
# touching the gallery, and third-party bundles follow alphabetically.
_THEME_ORDER = (
    "dracula",
    "oled",
    "parchment",
    "nord",
    "sage",
    "ember",
    "high_contrast",
)
_CARD_WIDTH = 200
_CARD_SPACING = 16
_MAX_COLUMNS = 5

_SYSTEM_DESCRIPTION = (
    "Automatically follows your operating system's light or dark appearance."
)


def _accent_preview() -> str:
    return ThemeManager.accent()


def _bundle_mode_label(bundle) -> str:
    return bundle.mode_label or str(bundle.mode).title()


def _bundle_description(bundle) -> str:
    if bundle.description:
        return bundle.description
    return f"{bundle.display_name} theme with a {bundle.mode} palette."


class _ThemeSection(QWidget):
    """A titled group of fixed-width cards that wrap from four to one."""

    def __init__(self, title: str, cards: list[ThemeCard], parent=None) -> None:
        super().__init__(parent)
        self._cards = list(cards)
        self._columns = 0
        self._last_width = 0

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(10)
        outer.addWidget(Label(title, role=TextRole.SUBHEADING))

        self._cards_host = QWidget(self)
        self._rows_layout = QVBoxLayout(self._cards_host)
        self._rows_layout.setContentsMargins(0, 0, 0, 0)
        self._rows_layout.setSpacing(12)
        outer.addWidget(self._cards_host)

        self.set_columns(_MAX_COLUMNS)

    @property
    def cards(self) -> list[ThemeCard]:
        return list(self._cards)

    @property
    def column_count(self) -> int:
        return self._columns

    @staticmethod
    def columns_for_width(width: int) -> int:
        columns = (width + _CARD_SPACING) // (_CARD_WIDTH + _CARD_SPACING)
        return max(1, min(_MAX_COLUMNS, columns))

    def set_columns(self, columns: int) -> None:
        columns = max(1, min(_MAX_COLUMNS, columns))
        if columns == self._columns and self._rows_layout.count():
            return
        self._columns = columns
        self._reflow()

    def _clear_rows(self) -> None:
        while self._rows_layout.count():
            item = self._rows_layout.takeAt(0)
            row = item.widget()
            if row is None:
                continue
            row_layout = row.layout()
            if row_layout is not None:
                while row_layout.count():
                    child = row_layout.takeAt(0).widget()
                    if child is not None:
                        child.setParent(self._cards_host)
            row.setParent(None)
            row.deleteLater()

    def _reflow(self) -> None:
        self._clear_rows()

        width = self.width() if self.width() > 0 else _CARD_WIDTH
        card_width = _CARD_WIDTH
        if self._columns == 1:
            card_width = min(_CARD_WIDTH, max(120, width))

        for start in range(0, len(self._cards), self._columns):
            row = QWidget(self._cards_host)
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(_CARD_SPACING)
            for card in self._cards[start : start + self._columns]:
                card.setFixedWidth(card_width)
                row_layout.addWidget(card, 0, Qt.AlignmentFlag.AlignTop)
            row_layout.addStretch(1)
            self._rows_layout.addWidget(row)

        self.updateGeometry()

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt override
        super().resizeEvent(event)
        width = self.width()
        if width <= 0:
            return
        columns = self.columns_for_width(width)
        single_column_resize = columns == 1 and width != self._last_width
        if columns != self._columns or single_column_resize:
            self.set_columns(columns)
        self._last_width = width


class ThemeGallery(QWidget):
    """Curated, data-driven theme picker for the Appearance card."""

    theme_selected = pyqtSignal(str)

    def __init__(self, config_manager, parent=None) -> None:
        super().__init__(parent)
        self.config_manager = config_manager
        self.cards: dict[str, ThemeCard] = {}
        self.sections: dict[str, _ThemeSection] = {}
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._group.buttonClicked.connect(self._on_card_clicked)
        self._build_gallery()

        manager = ThemeManager.instance()
        manager.theme_changed.connect(self._on_theme_changed)
        manager.accent_changed.connect(self._on_accent_changed)

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------
    def _build_gallery(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(18)

        bundles = ThemeManager.registered_bundles()
        system_card = self._make_card(
            _SYSTEM_THEME,
            "System",
            "Follows OS",
            _SYSTEM_DESCRIPTION,
        )
        base_cards = [
            self._make_bundle_card(bundles[bundle_id])
            for bundle_id in _BASE_THEME_IDS
            if bundle_id in bundles
        ]
        theme_cards = [
            self._make_bundle_card(bundles[bundle_id])
            for bundle_id in self._ordered_theme_ids(bundles)
        ]

        layout.addWidget(self._add_section("Automatic", [system_card]))
        layout.addWidget(self._add_section("Base", base_cards))
        layout.addWidget(self._add_section("Themes", theme_cards))
        self._sync_selection(self.config_manager.get("theme_mode", _SYSTEM_THEME))

    @staticmethod
    def _ordered_theme_ids(bundles: dict) -> list[str]:
        ordered = [bundle_id for bundle_id in _THEME_ORDER if bundle_id in bundles]
        extras = sorted(
            (
                bundle_id
                for bundle_id in bundles
                if bundle_id not in _THEME_ORDER
                and bundle_id not in _BASE_THEME_IDS
            ),
            key=lambda bundle_id: bundles[bundle_id].display_name.lower(),
        )
        return ordered + extras

    def _add_section(self, title: str, cards: list[ThemeCard]) -> _ThemeSection:
        section = _ThemeSection(title, cards, self)
        self.sections[title] = section
        return section

    def _make_bundle_card(self, bundle) -> ThemeCard:
        return self._make_card(
            bundle.id,
            bundle.display_name,
            _bundle_mode_label(bundle),
            _bundle_description(bundle),
        )

    def _make_card(
        self,
        value: str,
        title: str,
        mode_label: str,
        description: str,
    ) -> ThemeCard:
        card = ThemeCard(
            value,
            title,
            mode_label,
            description,
            self._preview_colors(value),
            self,
        )
        self.cards[value] = card
        self._group.addButton(card)
        return card

    # ------------------------------------------------------------------
    # Preview colours
    # ------------------------------------------------------------------
    def _preview_colors(self, mode: str) -> list[str]:
        if mode == _SYSTEM_THEME:
            accent = _accent_preview()
            light = LIGHT.with_accent(accent)
            dark = DARK.with_accent(accent)
            # Alternate the two base appearances, then close with the accent
            # so the System card communicates "follows OS" at a glance.
            return [
                light.background,
                dark.background,
                light.surface,
                dark.surface,
                accent,
            ]

        palette: ThemePalette | None = ThemeManager.preview_palette(mode)
        if palette is None:
            return []
        return [palette.background, palette.surface, palette.accent]

    def refresh_previews(self) -> None:
        for value, card in self.cards.items():
            card.set_swatches(self._preview_colors(value))

    # ------------------------------------------------------------------
    # Selection
    # ------------------------------------------------------------------
    @property
    def selected_mode(self) -> str:
        for value, card in self.cards.items():
            if card.isChecked():
                return value
        return _SYSTEM_THEME

    def _on_card_clicked(self, button: QAbstractButton) -> None:
        if not isinstance(button, ThemeCard):
            return
        mode = button.value
        current = str(self.config_manager.get("theme_mode", _SYSTEM_THEME))
        if mode != current:
            self.config_manager.set("theme_mode", mode)
            ThemeManager.set_theme_mode(mode)
        self._sync_selection(mode)
        self.theme_selected.emit(mode)

    def _sync_selection(self, mode: str | None = None) -> None:
        mode = str(mode or self.config_manager.get("theme_mode", _SYSTEM_THEME))
        if mode not in self.cards:
            mode = _SYSTEM_THEME

        self._group.setExclusive(False)
        for value, card in self.cards.items():
            card.setChecked(value == mode)
        self._group.setExclusive(True)

    # ------------------------------------------------------------------
    # Live updates
    # ------------------------------------------------------------------
    def _on_theme_changed(self, *_args) -> None:
        self._sync_selection(ThemeManager.theme_mode())
        self.refresh_previews()

    def _on_accent_changed(self, *_args) -> None:
        self.refresh_previews()

    def reload_from_config(self) -> None:
        self._sync_selection(self.config_manager.get("theme_mode", _SYSTEM_THEME))
        self.refresh_previews()

    def refresh_styles(self) -> None:
        self.refresh_previews()
        for card in self.cards.values():
            card.refresh_styles()


__all__ = ["ThemeGallery"]
