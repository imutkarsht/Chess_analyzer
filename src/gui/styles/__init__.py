# SPDX-License-Identifier: GPL-3.0-only
"""Public styling facade: one ``Styles`` class composed from QSS mixins.

Call sites continue to import ``Styles`` from ``src.gui.styles``; the package
layout is an implementation detail.
"""

from __future__ import annotations

from src.gui.styles._base import _StylesMeta
from src.gui.styles._buttons import _ButtonMixin
from src.gui.styles._controls import _ControlsMixin
from src.gui.styles._feedback import _FeedbackMixin
from src.gui.styles._inputs import _InputMixin
from src.gui.styles._navigation import _NavigationMixin
from src.gui.styles._pages import _PagesMixin
from src.gui.styles._progress import _ProgressMixin
from src.gui.styles._surfaces import _SurfaceMixin
from src.gui.styles._tables import _TableMixin
from src.gui.styles._tokens import _TokensMixin
from src.gui.styles._typography import _TypographyMixin


class Styles(
    _TokensMixin,
    _TypographyMixin,
    _ButtonMixin,
    _InputMixin,
    _SurfaceMixin,
    _TableMixin,
    _NavigationMixin,
    _ControlsMixin,
    _ProgressMixin,
    _FeedbackMixin,
    _PagesMixin,
    metaclass=_StylesMeta,
):
    """Single entry point for theme-derived QSS strings."""


__all__ = ["Styles"]
