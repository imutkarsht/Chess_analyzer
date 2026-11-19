# SPDX-License-Identifier: GPL-3.0-only
"""Small SVG element helpers shared by board and preview renderers."""

from __future__ import annotations

import xml.etree.ElementTree as ET


def add_svg_rect(
    parent: ET.Element,
    x: int | float,
    y: int | float,
    width: int | float,
    height: int | float,
    fill: str,
    *,
    opacity: str | None = None,
) -> None:
    attributes = {
        "x": str(x),
        "y": str(y),
        "width": str(width),
        "height": str(height),
        "fill": fill,
    }
    if opacity is not None:
        attributes["opacity"] = opacity
    ET.SubElement(parent, "rect", attributes)


def add_svg_use(
    parent: ET.Element,
    href: str,
    x: int | float,
    y: int | float,
) -> None:
    ET.SubElement(
        parent,
        "use",
        {
            "href": href,
            "xlink:href": href,
            "transform": f"translate({x}, {y})",
        },
    )
