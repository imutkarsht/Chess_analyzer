# SPDX-License-Identifier: GPL-3.0-only
"""Single source of truth for source-hygiene patterns and legacy allowlists.

Both the whole-repository guardrail tests and ``check_changed_hygiene.py``
import these values so a documented exception cannot drift between the two.
"""

from __future__ import annotations

import re

SPDX_HEADER = "# SPDX-License-Identifier: GPL-3.0-only"

RAW_FONT_ICON = re.compile(r"fa[0-9]*[sbrlbd]\.[a-z0-9-]+")

# Content artwork and app identity assets may still construct QIcons directly.
RAW_QICON_ALLOWLIST = frozenset(
    {
        "src/gui/analysis/moves/cell.py",
        "src/gui/analysis/moves/view.py",
        "src/gui/board/promotion_dialog.py",
        "src/gui/main_window/window.py",
        "src/gui/resources.py",
        "src/gui/views/settings/board_pieces_settings.py",
    }
)

# Brand glyphs and a few Font Awesome 6-only legend glyphs remain explicit
# until they have pack-independent equivalents.
RAW_FONT_ALLOWLIST = frozenset(
    {
        "src/gui/components/layout/welcome_panel.py",
        "src/gui/views/metrics/ending_distribution_card.py",
        "src/gui/views/settings/links_settings.py",
    }
)

SETICON_ALLOWLIST = frozenset(
    {
        "src/gui/analysis/moves/cell.py",
        "src/gui/analysis/moves/view.py",
        "src/gui/main_window/window.py",
        "src/gui/views/history_view.py",
        "src/gui/views/settings/board_pieces_settings.py",
    }
)

# Purpose-built widgets that are not buttons (swatches, star rating, graph nodes).
BUTTON_COMPONENT = "src/gui/components/controls/button.py"
RAW_BUTTON_ALLOWLIST = frozenset(
    {
        "src/gui/analysis/moves/cell.py",
        "src/gui/analysis/variation/graph.py",
        "src/gui/components/controls/star_rating_widget.py",
        "src/gui/views/settings/board_pieces_settings.py",
    }
)

RAW_PUSH_TOOL_CLASSES = frozenset({"QPushButton", "QToolButton"})

# Form controls with no page-specific exceptions: only shared components may
# construct them directly.
RAW_FORM_CONTROLS = frozenset(
    {
        "QCheckBox",
        "QProgressBar",
        "QRadioButton",
        "QSlider",
        "QListWidget",
        "QComboBox",
        "QSpinBox",
        "QDoubleSpinBox",
        "QDateEdit",
        "QTabWidget",
    }
)

# Widgets that legitimately own a raw editor: the central component itself, the
# painted date field's inner editor, and the canvas rename overlay.
RAW_INPUT_ALLOWLIST = frozenset(
    {
        "src/gui/components/controls/input.py",
        "src/gui/components/controls/date_picker.py",
        "src/gui/analysis/variation/graph.py",
    }
)

RAW_INPUT_CLASSES = frozenset(
    {"QLineEdit", "QTextEdit", "QPlainTextEdit", "QSpinBox", "QDoubleSpinBox"}
)

RAW_CONTROL_CLASSES = RAW_PUSH_TOOL_CLASSES | RAW_FORM_CONTROLS | RAW_INPUT_CLASSES
