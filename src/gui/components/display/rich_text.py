# SPDX-License-Identifier: GPL-3.0-only
"""Shared rich-text and external-link labels."""

from __future__ import annotations

import html

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QWidget

from src.gui.styles import Styles
from src.gui.theme import ThemeManager
from src.gui.theme.typography import TextRole, TextTone

from .label import Label


class RichTextLabel(Label):
    """A Label variant for HTML content (bold names, inline spans, italics).

    Roles and tones still come from the global typography rules; only the text
    format changes from plain text to rich text.
    """

    def __init__(
        self,
        text: str = "",
        role: TextRole | str = TextRole.BODY,
        tone: TextTone | str = TextTone.PRIMARY,
        *,
        size: int | None = None,
        weight: int | None = None,
        wrap: bool = False,
        selectable: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            text,
            role,
            tone,
            size=size,
            weight=weight,
            wrap=wrap,
            selectable=selectable,
            parent=parent,
        )
        self.setTextFormat(Qt.TextFormat.RichText)


class LinkLabel(RichTextLabel):
    """A rich-text external link that follows the active accent colour."""

    def __init__(
        self,
        url: str = "",
        text: str = "",
        *,
        tone: TextTone | str = TextTone.ACCENT,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__("", TextRole.BODY, tone, parent=parent)
        self._url = ""
        self._link_text = ""
        self._link_tone = TextTone(tone)
        self.setOpenExternalLinks(True)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)

        manager = ThemeManager.instance()
        manager.theme_changed.connect(self._on_theme_changed)
        manager.accent_changed.connect(self._on_theme_changed)
        if url:
            self.set_link(url, text)

    def set_link(self, url: str, text: str = "") -> None:
        self._url = url or ""
        self._link_text = text or url
        self._render_link()

    def set_link_tone(self, tone: TextTone | str) -> None:
        self._link_tone = TextTone(tone)
        self.set_tone(self._link_tone)
        self._render_link()

    def _render_link(self) -> None:
        if not self._url:
            self.clear()
            return
        safe_url = html.escape(self._url, quote=True)
        safe_text = html.escape(self._link_text)
        color = Styles.get_tone_color(self._link_tone)
        self.setText(
            f'<a href="{safe_url}" style="color: {color}; '
            f'text-decoration: none;">{safe_text}</a>'
        )

    def _on_theme_changed(self, *_args) -> None:
        self._render_link()
