# SPDX-License-Identifier: GPL-3.0-only
"""Qt-free colour math shared by the palette and style layers."""

from __future__ import annotations


def channels(color: str) -> tuple[int, int, int]:
    """Parse a six-digit hex colour into RGB channels."""
    value = color.lstrip("#")
    if len(value) == 3:
        value = "".join(channel * 2 for channel in value)
    if len(value) != 6:
        raise ValueError(f"Unsupported colour: {color!r}")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def blend_hex(color_a: str, color_b: str, ratio: float) -> str:
    """Linear blend between two hex colours (ratio 0..1)."""
    ratio = max(0.0, min(1.0, ratio))
    first = channels(color_a)
    second = channels(color_b)
    return "#" + "".join(
        f"{round(first[index] + (second[index] - first[index]) * ratio):02X}"
        for index in range(3)
    )


def relative_luminance(color: str) -> float:
    def channel(value: int) -> float:
        value = value / 255.0
        return value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4

    red, green, blue = channels(color)
    return 0.2126 * channel(red) + 0.7152 * channel(green) + 0.0722 * channel(blue)


def contrast_ratio(foreground: str, background: str) -> float:
    first = relative_luminance(foreground)
    second = relative_luminance(background)
    return (max(first, second) + 0.05) / (min(first, second) + 0.05)


def readable_color(color: str, background: str, minimum: float = 4.5) -> str:
    """Blend ``color`` toward the opposite end of the surface until readable."""
    if contrast_ratio(color, background) >= minimum:
        return color
    target = "#FFFFFF" if relative_luminance(background) < 0.5 else "#000000"
    for step in range(1, 11):
        candidate = blend_hex(color, target, step / 10)
        if contrast_ratio(candidate, background) >= minimum:
            return candidate
    return target


def on_color(background: str) -> str:
    """Pick black or white ink for text placed on ``background``."""
    white = contrast_ratio("#FFFFFF", background)
    black = contrast_ratio("#000000", background)
    return "#FFFFFF" if white >= black else "#000000"


def rgba(color: str, alpha: float) -> str:
    red, green, blue = channels(color)
    return f"rgba({red}, {green}, {blue}, {max(0.0, min(1.0, alpha)):.2f})"


__all__ = [
    "blend_hex",
    "channels",
    "contrast_ratio",
    "on_color",
    "readable_color",
    "relative_luminance",
    "rgba",
]
