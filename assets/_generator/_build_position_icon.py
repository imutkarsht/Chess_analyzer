"""Generate assets/icons/build_position.png.

A 64x64 icon for the "Build Position" sidebar entry. The graphic is a
simple chess-board grid (4x4 cells) with a small plus marker in the
upper-left cell, suggesting "place a piece on a board". Lines use the
project's muted text colour so the icon reads as a regular sidebar
entry next to Analyze / History / Stats / Settings.

This is a "fake" icon (placeholder) intentionally — replace it with a
designer-provided SVG/PNG when one becomes available.
"""
import os
from PIL import Image, ImageDraw

ICON_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "icons"
)
OUT_PATH = os.path.join(ICON_DIR, "build_position.png")

# Same neutral grey used for the other sidebar icons in their fallback
# state. The icon is intentionally greyscale so the active/hover
# colouring is driven entirely by the sidebar stylesheet (which is
# how all the other sidebar icons behave).
ICON_COLOUR = (200, 200, 205, 255)
ACCENT_COLOUR = (255, 149, 0, 255)  # matches Styles.COLOR_ACCENT
GRID_COLOUR = (140, 140, 145, 255)
BG = (0, 0, 0, 0)

SIZE = 64
PADDING = 6
GRID_TOP = PADDING
GRID_LEFT = PADDING + 2
GRID_SIZE = SIZE - 2 * PADDING - 2
CELL = GRID_SIZE // 4

img = Image.new("RGBA", (SIZE, SIZE), BG)
draw = ImageDraw.Draw(img)

# 1. Outer rounded board frame
frame = (
    GRID_LEFT,
    GRID_TOP,
    GRID_LEFT + GRID_SIZE,
    GRID_TOP + GRID_SIZE,
)
draw.rounded_rectangle(
    frame, radius=4, outline=GRID_COLOUR, width=2
)

# 2. Inner grid lines (3 vertical, 3 horizontal for 4x4 cells)
for i in range(1, 4):
    x = GRID_LEFT + i * CELL
    draw.line(
        [(x, GRID_TOP + 1), (x, GRID_TOP + GRID_SIZE - 1)],
        fill=GRID_COLOUR, width=1,
    )
    y = GRID_TOP + i * CELL
    draw.line(
        [(GRID_LEFT + 1, y), (GRID_LEFT + GRID_SIZE - 1, y)],
        fill=GRID_COLOUR, width=1,
    )

# 3. A tiny accent square in the upper-left cell to suggest
#    "place a piece here". Sized so it sits well inside the cell.
square_in = 5
sx0 = GRID_LEFT + 3
sy0 = GRID_TOP + 3
draw.rectangle(
    [sx0, sy0, sx0 + square_in, sy0 + square_in],
    fill=ACCENT_COLOUR,
)

# 4. A small plus marker in the lower-right cell to suggest
#    "add more pieces".
plus_pad = 3
cx0 = GRID_LEFT + 3 * CELL + plus_pad
cy0 = GRID_TOP + 3 * CELL + plus_pad
cx1 = GRID_LEFT + 4 * CELL - plus_pad
cy1 = GRID_TOP + 4 * CELL - plus_pad
mid_x = (cx0 + cx1) // 2
mid_y = (cy0 + cy1) // 2
draw.line([(cx0, mid_y), (cx1, mid_y)], fill=ICON_COLOUR, width=2)
draw.line([(mid_x, cy0), (mid_x, cy1)], fill=ICON_COLOUR, width=2)

os.makedirs(ICON_DIR, exist_ok=True)
img.save(OUT_PATH, "PNG")
print(f"Wrote {OUT_PATH} ({SIZE}x{SIZE})")
