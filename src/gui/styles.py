from src.gui.theme import ThemeManager
from src.gui.theme.palette import BOARD_THEMES

# Text/icons drawn on top of a filled accent surface. White reads on every
# accent the app allows, in both light and dark mode.
ON_ACCENT = "#FFFFFF"


class _StylesMeta(type):
    # ═══════════════════════════════════════════════════════════════
    #  CORE PALETTE
    # ═══════════════════════════════════════════════════════════════
    @property
    def COLOR_BACKGROUND(cls):
        return ThemeManager.palette().background

    @property
    def COLOR_SURFACE(cls):
        return ThemeManager.palette().surface

    @property
    def COLOR_SURFACE_LIGHT(cls):
        return ThemeManager.palette().surface_light

    @property
    def COLOR_SURFACE_CARD(cls):
        return ThemeManager.palette().surface_card

    @property
    def COLOR_TEXT_PRIMARY(cls):
        return ThemeManager.palette().text_primary

    @property
    def COLOR_TEXT_SECONDARY(cls):
        return ThemeManager.palette().text_secondary

    @property
    def COLOR_TEXT_MUTED(cls):
        return ThemeManager.palette().text_muted

    @property
    def COLOR_ACCENT(cls):
        return ThemeManager.palette().accent

    @property
    def COLOR_ACCENT_HOVER(cls):
        return ThemeManager.palette().accent_hover

    @property
    def COLOR_ACCENT_SUBTLE(cls):
        return ThemeManager.palette().accent_subtle

    @property
    def COLOR_ON_ACCENT(cls):
        return ON_ACCENT

    @property
    def COLOR_BORDER(cls):
        return ThemeManager.palette().border

    @property
    def COLOR_BORDER_LIGHT(cls):
        return ThemeManager.palette().border_light

    @property
    def COLOR_HIGHLIGHT(cls):
        return ThemeManager.palette().highlight

    @property
    def COLOR_PIECE_WHITE(cls):
        return ThemeManager.palette().piece_white

    @property
    def COLOR_PIECE_BLACK(cls):
        return ThemeManager.palette().piece_black

    @property
    def COLOR_BOARD_HIGHLIGHT(cls):
        return ThemeManager.palette().board_highlight

    @property
    def COLOR_BRANCH_1(cls):
        return ThemeManager.palette().branch_colors[0]

    @property
    def COLOR_BRANCH_2(cls):
        return ThemeManager.palette().branch_colors[1]

    @property
    def COLOR_BRANCH_3(cls):
        return ThemeManager.palette().branch_colors[2]

    @property
    def COLOR_BRANCH_4(cls):
        return ThemeManager.palette().branch_colors[3]

    @classmethod
    def get_branch_color(cls, index: int) -> str:
        colors = ThemeManager.palette().branch_colors
        return colors[index % len(colors)]

    # ═══════════════════════════════════════════════════════════════
    #  MOVE CLASSIFICATION COLORS
    # ═══════════════════════════════════════════════════════════════
    @property
    def COLOR_BRILLIANT(cls):
        return ThemeManager.get_class_color("Brilliant")

    @property
    def COLOR_GREAT(cls):
        return ThemeManager.get_class_color("Great")

    @property
    def COLOR_BEST(cls):
        return ThemeManager.get_class_color("Best")

    @property
    def COLOR_EXCELLENT(cls):
        return ThemeManager.get_class_color("Excellent")

    @property
    def COLOR_GOOD(cls):
        return ThemeManager.get_class_color("Good")

    @property
    def COLOR_INACCURACY(cls):
        return ThemeManager.get_class_color("Inaccuracy")

    @property
    def COLOR_MISTAKE(cls):
        return ThemeManager.get_class_color("Mistake")

    @property
    def COLOR_BLUNDER(cls):
        return ThemeManager.get_class_color("Blunder")

    @property
    def COLOR_MISS(cls):
        return ThemeManager.get_class_color("Miss")

    @property
    def COLOR_BOOK(cls):
        return ThemeManager.get_class_color("Book")

    # ═══════════════════════════════════════════════════════════════
    #  SEMANTIC COLORS
    # ═══════════════════════════════════════════════════════════════
    @property
    def COLOR_RESULT_WIN(cls):
        return "#4FA859"

    @property
    def COLOR_RESULT_DRAW(cls):
        return "#8E9AA6"

    @property
    def COLOR_RESULT_LOSS(cls):
        return "#2F3640"

    @property
    def COLOR_ENGINE_READY(cls):
        return "#27ae60"

    @property
    def COLOR_ENGINE_BUSY(cls):
        return "#e67e22"

    # ═══════════════════════════════════════════════════════════════
    #  BOARD THEMES
    # ═══════════════════════════════════════════════════════════════
    @property
    def BOARD_THEMES(cls):
        return BOARD_THEMES


class Styles(metaclass=_StylesMeta):
    # ═══════════════════════════════════════════════════════════════
    #  GLOBAL THEME
    # ═══════════════════════════════════════════════════════════════
    @classmethod
    def get_theme(cls):
        p = ThemeManager.palette()
        return f"""
            QMainWindow, QWidget {{
                background-color: {p.background};
                color: {p.text_primary};
                font-family: 'SF Pro', 'Inter', 'Segoe UI', 'Roboto', sans-serif;
                font-size: 14px;
            }}

            QFrame, QSplitter::handle {{
                background-color: {p.surface};
            }}

            QSplitter::handle {{
                width: 3px;
                background-color: {p.border};
            }}
            QSplitter::handle:hover {{
                background-color: {p.accent};
            }}

            QTableWidget {{
                background-color: {p.surface};
                gridline-color: transparent;
                border: 1px solid {p.border};
                border-radius: 8px;
                selection-background-color: {p.highlight};
                selection-color: {p.text_primary};
            }}

            QTableWidget::item {{
                color: {p.text_primary};
                padding: 10px 8px;
                border-bottom: 1px solid {p.surface_light};
            }}

            QTableWidget::item:hover {{
                background-color: {p.surface_light};
            }}

            QTableWidget::item:selected {{
                background-color: {p.highlight};
                border-left: 3px solid {p.accent};
            }}

            QHeaderView::section {{
                background-color: {p.surface_light};
                color: {p.text_primary};
                padding: 8px;
                border: none;
                border-bottom: 2px solid {p.accent};
                font-weight: 600;
                font-size: 13px;
            }}

            QListWidget {{
                background-color: {p.surface};
                border: 1px solid {p.border};
                border-radius: 8px;
                padding: 6px;
            }}

            QListWidget::item {{
                padding: 10px 12px;
                border-radius: 6px;
                margin: 2px 0;
            }}

            QListWidget::item:hover {{
                background-color: {p.surface_light};
            }}

            QListWidget::item:selected {{
                background-color: {p.accent};
                color: white;
            }}

            QLabel {{
                color: {p.text_primary};
                background: transparent;
            }}

            QScrollBar:vertical {{
                border: none;
                background: {p.background};
                width: 8px;
                margin: 4px 2px;
            }}
            QScrollBar::handle:vertical {{
                background: {p.border};
                min-height: 30px;
                border-radius: 4px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {p.border_light};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}

            QScrollBar:horizontal {{
                border: none;
                background: {p.background};
                height: 8px;
                margin: 2px 4px;
            }}
            QScrollBar::handle:horizontal {{
                background: {p.border};
                min-width: 30px;
                border-radius: 4px;
            }}
            QScrollBar::handle:horizontal:hover {{
                background: {p.border_light};
            }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
                width: 0px;
            }}

            QToolTip {{
                background-color: {p.surface_light};
                color: {p.text_primary};
                border: 1px solid {p.border};
                border-radius: 4px;
                padding: 6px 10px;
                font-size: 13px;
            }}
        """

    # ═══════════════════════════════════════════════════════════════
    #  BUTTONS
    # ═══════════════════════════════════════════════════════════════
    _BUTTON_SIZES = {
        "sm": {"font": 12, "pad_v": 4, "pad_h": 10, "radius": 6, "weight": 600},
        "md": {"font": 13, "pad_v": 8, "pad_h": 16, "radius": 6, "weight": 600},
        "lg": {"font": 14, "pad_v": 10, "pad_h": 22, "radius": 8, "weight": 600},
    }

    @classmethod
    def get_button_qss(
        cls,
        *,
        variant: str = "primary",
        size: str = "md",
        accent: str | None = None,
        align: str | None = None,
    ) -> str:
        """Stylesheet for :class:`src.gui.components.button.Button`.

        One generator for every button in the app, so hover/pressed/checked/
        disabled states stay identical everywhere and follow the live palette.
        """
        p = ThemeManager.palette()
        acc = accent or p.accent
        danger = cls.COLOR_BLUNDER
        on_acc = cls.COLOR_ON_ACCENT
        spec = cls._BUTTON_SIZES.get(size, cls._BUTTON_SIZES["md"])

        if variant == "primary":
            bg, fg, border = acc, on_acc, acc
            hover = (p.accent_hover, on_acc, p.accent_hover)
            pressed = (acc, on_acc, acc)
            checked = (p.accent_hover, on_acc, p.accent_hover)
            disabled_bg = p.border
        elif variant == "filled":
            bg, fg, border = p.surface_light, p.text_primary, p.border
            hover = (p.surface, p.text_primary, acc)
            pressed = (p.accent_subtle, p.text_primary, acc)
            checked = (p.accent_subtle, p.text_primary, acc)
            disabled_bg = p.surface_light
        elif variant == "outlined":
            bg, fg, border = "transparent", acc, acc
            hover = (acc, on_acc, acc)
            pressed = (acc, on_acc, acc)
            checked = (acc, on_acc, acc)
            disabled_bg = "transparent"
        elif variant == "hollow":
            bg, fg, border = "transparent", p.text_primary, p.border
            hover = (p.surface_light, p.text_primary, acc)
            pressed = (p.accent_subtle, p.text_primary, acc)
            checked = (p.accent_subtle, p.text_primary, acc)
            disabled_bg = "transparent"
        elif variant == "ghost":
            bg, fg, border = "transparent", p.text_secondary, "transparent"
            hover = (p.surface_light, p.text_primary, "transparent")
            pressed = (p.accent_subtle, p.text_primary, "transparent")
            checked = (p.accent_subtle, p.text_primary, "transparent")
            disabled_bg = "transparent"
        elif variant == "danger":
            bg, fg, border = "transparent", danger, danger
            hover = (danger, on_acc, danger)
            pressed = (danger, on_acc, danger)
            checked = (danger, on_acc, danger)
            disabled_bg = "transparent"
        else:  # link
            bg, fg, border = "transparent", p.text_secondary, "transparent"
            hover = ("transparent", acc, "transparent")
            pressed = ("transparent", acc, "transparent")
            checked = ("transparent", acc, "transparent")
            disabled_bg = "transparent"

        align_rule = f"text-align: {align};" if align else ""
        return f"""
            QPushButton {{
                background-color: {bg};
                color: {fg};
                border: 1px solid {border};
                border-radius: {spec['radius']}px;
                padding: {spec['pad_v']}px {spec['pad_h']}px;
                font-size: {spec['font']}px;
                font-weight: {spec['weight']};
                {align_rule}
            }}
            QPushButton:hover {{
                background-color: {hover[0]};
                color: {hover[1]};
                border-color: {hover[2]};
            }}
            QPushButton:pressed {{
                background-color: {pressed[0]};
                color: {pressed[1]};
                border-color: {pressed[2]};
            }}
            QPushButton:checked {{
                background-color: {checked[0]};
                color: {checked[1]};
                border-color: {checked[2]};
            }}
            QPushButton:disabled {{
                background-color: {disabled_bg};
                color: {p.text_muted};
                border-color: {p.border if variant in ("filled", "hollow") else "transparent"};
            }}
        """

    @classmethod
    def get_button_style(cls):
        p = ThemeManager.palette()
        return f"""
            QPushButton {{
                background-color: {p.accent};
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 6px;
                font-weight: 600;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: {p.accent_hover};
            }}
            QPushButton:pressed {{
                background-color: {p.accent};
            }}
            QPushButton:disabled {{
                background-color: {p.border};
                color: {p.text_muted};
            }}
        """

    @classmethod
    def get_danger_button_style(cls):
        p = ThemeManager.palette()
        return f"""
            QPushButton {{
                background-color: #D02030;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 6px;
                font-weight: 600;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: #B01020;
            }}
            QPushButton:pressed {{
                background-color: #900010;
            }}
            QPushButton:disabled {{
                background-color: {p.border};
                color: {p.text_muted};
            }}
        """

    @classmethod
    def get_outline_button_style(cls):
        p = ThemeManager.palette()
        return f"""
            QPushButton {{
                background-color: {p.surface_light};
                color: {p.text_primary};
                border: 1px solid {p.accent};
                border-radius: 8px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {p.accent};
                color: #FFFFFF;
            }}
        """

    @classmethod
    def get_icon_button_style(cls):
        p = ThemeManager.palette()
        return f"""
            QPushButton {{
                background: {p.surface_light};
                border: 2px solid {p.border};
                border-radius: 8px;
            }}
            QPushButton:hover {{
                background: {p.accent};
                border-color: {p.accent};
            }}
        """

    @classmethod
    def get_board_game_header_style(cls):
        p = ThemeManager.palette()
        return f"""
            QFrame#BoardGameHeader {{
                background: transparent;
                border: none;
                border-bottom: 1px solid {p.border};
            }}
            QFrame#BoardGameHeader QLabel {{
                background: transparent;
                border: none;
            }}
        """

    @classmethod
    def get_board_controls_style(cls):
        p = ThemeManager.palette()
        return f"""
            QWidget#BoardControls {{
                background: transparent;
                border: none;
                border-top: 1px solid {p.border};
            }}
        """

    @classmethod
    def get_nav_icon_button_style(cls):
        p = ThemeManager.palette()
        return f"""
            QToolButton {{
                background: transparent;
                color: {p.text_primary};
                border: none;
                border-radius: 5px;
                padding: 0px;
            }}
            QToolButton:hover {{
                background-color: {p.surface};
                color: {p.accent};
            }}
            QToolButton:pressed {{
                background-color: {p.accent_subtle};
            }}
            QToolButton:disabled {{
                color: {p.text_muted};
            }}
        """

    # ═══════════════════════════════════════════════════════════════
    #  VARIATION BRANCH GRAPH
    # ═══════════════════════════════════════════════════════════════
    @classmethod
    def get_variation_action_button_style(cls):
        p = ThemeManager.palette()
        return f"""
            QPushButton {{
                background-color: {p.surface_card};
                color: {p.text_primary};
                border: 1px solid {p.border};
                border-radius: 6px;
                padding: 0px;
            }}
            QPushButton:hover {{
                background-color: {p.accent_subtle};
                border-color: {p.accent};
            }}
            QPushButton:pressed {{
                background-color: {p.accent_subtle};
            }}
            QPushButton:disabled {{
                background-color: {p.surface_light};
                border-color: {p.border};
            }}
        """

    @classmethod
    def get_variation_graph_style(cls):
        p = ThemeManager.palette()
        return f"""
            QFrame#VariationGraph {{
                background-color: {p.surface_light};
                border: 1px solid {p.border};
                border-radius: 8px;
            }}
            QFrame#VariationGraph QLabel {{
                background: transparent;
                border: none;
            }}
            QScrollArea {{
                background: transparent;
                border: none;
            }}
        """

    @classmethod
    def get_variation_node_style(cls, color, active=False, ghost=False):
        p = ThemeManager.palette()
        if ghost:
            background = p.surface
            border = f"1px dashed {color}"
            text = p.text_muted
        elif active:
            background = p.accent_subtle
            border = f"2px solid {color}"
            text = p.text_primary
        else:
            background = p.surface_card
            border = f"1px solid {color}"
            text = p.text_primary
        return f"""
            QPushButton {{
                background-color: {background};
                color: {text};
                border: {border};
                border-radius: 6px;
                font-size: 11px;
                font-weight: 600;
                padding: 0px 4px;
            }}
            QPushButton:hover {{
                background-color: {p.accent_subtle};
            }}
        """

    @classmethod
    def get_variation_branch_chip_style(cls, color, active=False):
        p = ThemeManager.palette()
        background = p.accent_subtle if active else p.surface_card
        return f"""
            QFrame#BranchChip {{
                background-color: {background};
                border: 1px solid {color};
                border-radius: 6px;
            }}
            QFrame#BranchChip QLabel {{
                color: {p.text_primary if active else p.text_secondary};
                background: transparent;
                border: none;
                font-size: 10px;
                font-weight: 600;
            }}
            QFrame#BranchChip QToolButton {{
                color: {p.text_muted};
                background: transparent;
                border: none;
                font-size: 11px;
                padding: 0px;
            }}
            QFrame#BranchChip QToolButton:hover {{
                color: {p.text_primary};
            }}
        """

    @classmethod
    def get_variation_badge_style(cls):
        p = ThemeManager.palette()
        return f"""
            QToolButton {{
                background-color: {p.accent_subtle};
                color: {p.accent};
                border: 1px solid {p.accent};
                border-radius: 5px;
                font-size: 10px;
                font-weight: 700;
                padding: 0px;
            }}
            QToolButton:hover {{
                background-color: {p.accent};
                color: #FFFFFF;
            }}
        """

    @classmethod
    def get_delete_button_style(cls):
        p = ThemeManager.palette()
        return f"""
            QPushButton {{
                background-color: transparent;
                border: none;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: {p.surface_light};
                border: 1px solid {cls.COLOR_BLUNDER};
            }}
        """

    @classmethod
    def get_toggle_button_style(cls, active=False):
        p = ThemeManager.palette()
        bg = p.accent if active else p.surface_light
        text_color = "#FFFFFF" if active else p.text_primary
        border_color = p.accent if active else p.border
        weight = "700" if active else "500"
        return f"""
            QPushButton {{
                background-color: {bg};
                color: {text_color} !important;
                border: 1px solid {border_color};
                border-radius: 5px;
                padding: 0 10px;
                font-size: 12px;
                font-weight: {weight};
            }}
        """

    @classmethod
    def get_page_btn_style(cls, enabled=True):
        p = ThemeManager.palette()
        bg = p.surface_light if enabled else "transparent"
        text = p.text_primary if enabled else p.text_muted
        return f"""
            QPushButton {{
                background-color: {bg};
                color: {text};
                border: 1px solid {p.border};
                border-radius: 6px;
                padding: 0 12px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {p.accent};
                color: {p.text_primary};
                border-color: {p.accent};
            }}
            QPushButton:disabled {{
                opacity: 0.4;
            }}
        """

    @classmethod
    def get_page_num_btn_style(cls, active=False):
        p = ThemeManager.palette()
        bg = p.accent if active else p.surface_light
        text = "#FFFFFF" if active else p.text_primary
        border = p.accent if active else p.border
        weight = "700" if active else "400"
        return f"""
            QPushButton {{
                background-color: {bg};
                color: {text} !important;
                border: 1px solid {border};
                border-radius: 6px;
                padding: 0px !important;
                font-size: 12px;
                font-weight: {weight};
                text-align: center !important;
            }}
            QPushButton:hover {{
                background-color: {p.accent};
                border-color: {p.accent};
                color: #FFFFFF !important;
            }}
        """

    @classmethod
    def get_card_action_button_style(cls, primary=False):
        p = ThemeManager.palette()
        bg = p.accent if primary else p.surface_light
        color = "#FFFFFF" if primary else p.text_primary
        border = p.accent if primary else p.border
        hover_bg = p.accent_hover if primary else p.surface
        return f"""
            QPushButton {{
                background-color: {bg};
                color: {color} !important;
                border: 1px solid {border};
                border-radius: 4px;
                padding: 3px 8px;
                font-size: 11px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {hover_bg};
                color: #FFFFFF !important;
                border-color: {p.accent};
            }}
            QPushButton:pressed {{
                background-color: {p.accent};
            }}
        """

    @classmethod
    def get_card_action_icon_button_style(cls, status: str = "not_started"):
        p = ThemeManager.palette()
        hover_border = cls.COLOR_ENGINE_BUSY if status == "paused" else p.accent
        return f"""
            QPushButton {{
                background-color: transparent;
                border: 1px solid transparent;
                border-radius: 4px;
                padding: 0px;
            }}
            QPushButton:hover {{
                background-color: {p.surface_light};
                border: 1px solid {hover_border};
            }}
            QPushButton:pressed {{
                background-color: {p.surface};
            }}
        """

    @classmethod
    def get_control_button_style(cls, danger=False):
        p = ThemeManager.palette()
        color = p.text_primary
        hover_color = p.text_primary
        if danger:
            color = cls.COLOR_BLUNDER
            hover_color = cls.COLOR_BLUNDER
        return f"""
            QPushButton {{
                background-color: {p.surface_light};
                color: {color};
                border: 1px solid {p.border};
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 13px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: {p.surface};
                color: {hover_color};
                border: 1px solid {p.accent};
            }}
            QPushButton:pressed {{
                background-color: {p.accent_subtle};
                border: 1px solid {p.accent};
            }}
            QPushButton:disabled {{
                background-color: {p.surface_light};
                color: {p.text_muted};
                border-color: {p.border};
            }}
        """

    @classmethod
    def get_nav_button_style(cls):
        p = ThemeManager.palette()
        return f"""
            QPushButton {{
                background-color: {p.surface_light};
                color: {p.text_primary};
                border: 1px solid {p.border};
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 16px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {p.surface};
                border: 1px solid {p.accent};
            }}
            QPushButton:pressed {{
                background-color: {p.accent};
                color: white;
            }}
            QPushButton:disabled {{
                color: {p.text_muted};
                background-color: {p.surface_light};
            }}
        """

    @classmethod
    def get_export_button_style(cls):
        p = ThemeManager.palette()
        return f"""
            QPushButton {{
                background-color: #2D5A27;
                color: white;
                border: 1px solid {p.border};
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 14px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #387030;
            }}
            QPushButton:pressed {{
                background-color: #1E3C1A;
            }}
        """

    @classmethod
    def get_import_button_style(cls):
        return """
            QPushButton {
                background-color: #2D4A6B;
                color: white;
                border: 1px solid #3D5A7B;
                border-radius: 6px;
                padding: 8px 14px;
                font-size: 14px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #3A5F85;
                border: 1px solid #4A7095;
            }
            QPushButton:pressed {
                background-color: #254060;
            }
        """

    @classmethod
    def get_action_button_style(cls):
        p = ThemeManager.palette()
        return f"""
            QPushButton {{
                background-color: {p.surface};
                color: {p.text_secondary};
                border: 1px solid {p.border};
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {p.surface_light};
                border-color: {p.accent};
                color: {p.text_primary};
            }}
        """

    @classmethod
    def get_book_toggle_style(cls):
        p = ThemeManager.palette()
        return f"""
            QPushButton {{
                background: transparent;
                border: none;
                text-align: left;
                font-size: 14px;
                font-weight: bold;
                color: {p.text_primary};
                padding: 2px 0px;
            }}
            QPushButton:hover {{
                color: {p.accent};
            }}
        """

    # ═══════════════════════════════════════════════════════════════
    #  INPUTS / TEXT FIELDS
    # ═══════════════════════════════════════════════════════════════
    @classmethod
    def get_line_edit_style(cls):
        p = ThemeManager.palette()
        return f"""
            QLineEdit {{
                background-color: {p.surface};
                color: {p.text_primary};
                border: 1px solid {p.border};
                border-radius: 6px;
                padding: 2px 8px;
                font-size: 12px;
            }}
            QLineEdit:focus {{
                border-color: {p.accent};
            }}
        """

    @classmethod
    def get_filter_input_style(cls):
        p = ThemeManager.palette()
        return f"""
            QLineEdit {{
                padding: 6px 10px;
                border: 1px solid {p.border};
                border-radius: 6px;
                background-color: {p.surface_light};
                color: {p.text_primary};
                font-size: 13px;
            }}
            QLineEdit:focus {{
                border: 1px solid {p.accent};
            }}
        """

    @classmethod
    def get_line_edit_error_style(cls):
        return f"""
            QLineEdit {{
                background-color: #3d1a1a;
                color: #FFFFFF;
                border: 1px solid {cls.COLOR_BLUNDER};
                border-radius: 6px;
                padding: 2px 8px;
                font-size: 12px;
                font-weight: 600;
            }}
        """

    @classmethod
    def get_panel_input_style(cls):
        p = ThemeManager.palette()
        return f"""
            QLineEdit {{
                background-color: {p.surface};
                border: 1px solid {p.border};
                border-radius: 6px;
                padding: 0 12px;
                color: {p.text_primary};
                font-size: 13px;
                height: 36px;
            }}
            QLineEdit:focus {{
                border: 1px solid {p.accent};
            }}
        """

    @classmethod
    def get_focus_ring_style(cls):
        p = ThemeManager.palette()
        return f"""
            QLineEdit {{
                padding: 10px;
                border: 1px solid {p.border};
                border-radius: 4px;
                background-color: {p.surface_light};
                color: {p.text_primary};
            }}
            QLineEdit:focus {{
                border: 2px solid {p.accent};
                padding: 9px;
            }}
            QComboBox {{
                padding: 8px 12px;
                border: 1px solid {p.border};
                border-radius: 6px;
                background-color: {p.surface_light};
                color: {p.text_primary};
            }}
            QComboBox:focus {{
                border: 2px solid {p.accent};
            }}
            QPushButton:focus {{
                outline: 2px solid {p.accent};
            }}
            QTextEdit:focus {{
                border: 2px solid {p.accent};
            }}
            QListWidget:focus {{
                border: 2px solid {p.accent};
            }}
        """

    @classmethod
    def get_input_style(cls):
        p = ThemeManager.palette()
        return f"""
            padding: 10px;
            border: 1px solid {p.border};
            border-radius: 4px;
            background-color: {p.surface_light};
            color: {p.text_primary};
        """

    @classmethod
    def get_combobox_style(cls):
        p = ThemeManager.palette()
        return f"""
            QComboBox {{
                padding: 8px 12px;
                border: 1px solid {p.border};
                border-radius: 6px;
                background-color: {p.surface_light};
                color: {p.text_primary};
                min-width: 150px;
            }}
            QComboBox:hover {{
                border: 1px solid {p.accent};
            }}
            QComboBox::drop-down {{
                border: none;
                padding-right: 10px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {p.surface};
                color: {p.text_primary};
                selection-background-color: {p.accent};
                selection-color: white;
                border: none;
                outline: 0px;
                padding: 4px;
            }}
            QComboBox QAbstractItemView::item {{
                min-height: 26px;
                padding: 4px 8px;
                border-radius: 4px;
            }}
        """

    @classmethod
    def get_text_edit_style(cls):
        p = ThemeManager.palette()
        return f"""
            QTextEdit {{
                background-color: {p.surface_light};
                border: 1px solid {p.border};
                border-radius: 8px;
                padding: 10px;
                color: {p.text_primary};
            }}
        """

    @classmethod
    def get_flat_text_edit_style(cls, size=13):
        """
        Frameless, transparent read-only text area.

        Used for prose that lives inside an existing card (the Coach body): it
        must not draw a second surface, and it scrolls with a slim bar so the
        card can keep a fixed height whatever the text length.
        """
        p = ThemeManager.palette()
        return f"""
            QTextEdit {{
                background-color: transparent;
                border: none;
                padding: 0px;
                color: {p.text_secondary};
                font-size: {size}px;
            }}
            QScrollBar:vertical {{
                background-color: transparent;
                width: 8px;
                margin: 0px;
                border-radius: 4px;
            }}
            QScrollBar::handle:vertical {{
                background-color: {p.border};
                min-height: 24px;
                border-radius: 4px;
            }}
            QScrollBar::handle:vertical:hover {{
                background-color: {p.border_light};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background-color: transparent;
            }}
        """

    # ═══════════════════════════════════════════════════════════════
    #  LABELS
    # ═══════════════════════════════════════════════════════════════
    @classmethod
    def get_label_style(cls, size=14, color=None, bold=False, weight=None):
        p = ThemeManager.palette()
        if color is None:
            color = p.text_primary
        if weight is not None:
            w = str(weight)
        else:
            w = "bold" if bold else "normal"
        return f"font-size: {size}px; color: {color}; font-weight: {w};"

    @classmethod
    def get_secondary_label_style(cls, size=13):
        p = ThemeManager.palette()
        return f"""
            font-size: {size}px;
            color: {p.text_secondary};
            background-color: transparent;
            border: none;
            padding: 4px 0px;
        """

    @classmethod
    def get_badge_style(cls, size=11):
        p = ThemeManager.palette()
        return f"""
            QLabel {{
                color: {p.text_muted};
                font-size: {size}px;
                font-family: monospace;
                font-weight: 600;
                background-color: {p.surface};
                border: 1px solid {p.border};
                border-radius: 6px;
                padding: 2px 6px;
            }}
        """

    @classmethod
    def get_eval_badge_style(cls, bg_color, text_color):
        return f"""
            QLabel {{
                background-color: {bg_color};
                color: {text_color};
                border-radius: 6px;
                padding: 3px 8px;
                font-weight: bold;
                font-family: monospace;
                font-size: 12px;
            }}
        """

    @classmethod
    def get_result_badge_style(cls, color, font_size=12, padding="2px 8px", border_radius=4):
        p = ThemeManager.palette()
        return f"""
            QLabel {{
                color: {color};
                font-weight: bold;
                font-size: {font_size}px;
                padding: {padding};
                background-color: {p.surface_light};
                border: 1px solid {p.border};
                border-radius: {border_radius}px;
            }}
        """

    @classmethod
    def get_card_title_style(cls):
        p = ThemeManager.palette()
        return f"""
            color: {p.text_secondary};
            font-size: 12px;
            font-weight: 600;
            letter-spacing: 0.5px;
            text-transform: uppercase;
            background: transparent;
            border: none;
        """

    @classmethod
    def get_validation_label_style(cls):
        return """
            font-size: 12px;
            font-weight: bold;
            background: transparent;
            margin-top: 2px;
        """

    @classmethod
    def get_form_label_style(cls):
        p = ThemeManager.palette()
        return f"font-size: 13px; font-weight: 600; color: {p.text_primary};"

    @classmethod
    def get_transparent_label_style(cls):
        return "border: none; background: transparent;"

    # ═══════════════════════════════════════════════════════════════
    #  CARDS / FRAMES / DIALOG SURFACES
    # ═══════════════════════════════════════════════════════════════
    @classmethod
    def get_card_style(cls, border_radius=12):
        p = ThemeManager.palette()
        return f"""
            QFrame {{
                background-color: {p.surface};
                border: 1px solid {p.border};
                border-radius: {border_radius}px;
            }}
            QFrame:hover {{
                border: 1px solid {p.accent};
                background-color: {p.surface_light};
            }}
        """

    @classmethod
    def get_frame_style(cls, border_radius=12, hover_accent=True, object_name=None):
        p = ThemeManager.palette()
        selector = f"QFrame#{object_name}" if object_name else "QFrame"
        hover_style = (
            f"""
            {selector}:hover {{
                border: 1px solid {p.accent};
            }}
        """
            if hover_accent
            else ""
        )

        return f"""
            {selector} {{
                background-color: {p.surface};
                border: 1px solid {p.border};
                border-radius: {border_radius}px;
            }}
            {hover_style}
        """

    @classmethod
    def get_dialog_surface_style(cls):
        p = ThemeManager.palette()
        return f"""
            background-color: {p.surface};
            border: 1px solid {p.border};
            border-radius: 12px;
        """

    # ═══════════════════════════════════════════════════════════════
    #  TABLES
    # ═══════════════════════════════════════════════════════════════
    @classmethod
    def get_explorer_table_style(cls):
        p = ThemeManager.palette()
        return f"""
            QTableWidget {{
                background-color: {p.surface};
                border: 1px solid {p.border};
                border-radius: 8px;
                gridline-color: transparent;
                font-size: 14px;
            }}
            QTableWidget::item {{
                padding: 4px 8px;
                border-bottom: 1px solid {p.surface_light};
            }}
            QTableWidget::item:hover {{
                background-color: {p.surface_light};
            }}
            QTableWidget::item:selected {{
                background-color: {p.highlight};
                color: {p.text_primary};
                border-left: 3px solid {p.accent};
            }}
            QHeaderView::section {{
                background-color: {p.surface_light};
                color: {p.text_secondary};
                padding: 6px;
                border: none;
                border-bottom: 2px solid {p.accent};
                font-weight: 600;
                font-size: 13px;
            }}
        """

    @classmethod
    def get_move_list_card_style(cls):
        p = ThemeManager.palette()
        return f"""
            QFrame#MoveListCard {{
                background-color: {p.surface};
                border: 1px solid {p.border};
                border-radius: 12px;
            }}
        """

    @classmethod
    def get_move_list_table_style(cls):
        p = ThemeManager.palette()
        return f"""
            QTableWidget {{
                background: transparent;
                border: none;
                gridline-color: transparent;
                font-size: 13px;
                selection-background-color: transparent;
            }}
            QTableWidget QWidget#qt_scrollarea_viewport {{
                background: transparent;
            }}
            QTableWidget::item {{
                padding: 0px 0px 0px 10px;
                border: none;
                border-bottom: 1px solid {p.surface_light};
            }}
            QTableWidget::item:hover {{
                background: transparent;
            }}
            QTableWidget::item:selected {{
                background: transparent;
                color: {p.text_primary};
            }}
            QHeaderView {{
                background: transparent;
            }}
            QHeaderView::section {{
                background: transparent;
                color: {p.text_secondary};
                padding: 8px 10px 8px 12px;
                border: none;
                border-bottom: 1px solid {p.border};
                font-weight: 600;
                font-size: 11px;
            }}
            QScrollBar:vertical {{
                background: transparent;
                width: 8px;
                margin: 4px 2px 4px 0px;
                border: none;
            }}
            QScrollBar::handle:vertical {{
                background: {p.border};
                min-height: 20px;
                border-radius: 4px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {p.border_light};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
                background: none;
            }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background: none;
            }}
        """

    # ═══════════════════════════════════════════════════════════════
    #  TABS
    # ═══════════════════════════════════════════════════════════════
    @classmethod
    def get_tabs_style(
        cls,
        *,
        variant: str = "underline",
        spacing: int = 24,
        padding: tuple[int, int, int, int] = (8, 18, 10, 18),
        font_size: int = 15,
        font_weight: int = 600,
        radius: int = 8,
        track: bool = False,
        track_padding: int = 4,
        active_style: str = "filled",
        indicator_size: int = 3,
        accent: str | None = None,
    ) -> str:
        """Stylesheet for ``src.gui.components.tabs.Tabs``.

        One generator backs both looks: ``underline`` draws an accent bar under
        the active label, ``segmented`` renders button-like segments that either
        sit in a rounded ``#TabTrack`` container or float as detached pills.
        Rules are scoped to ``#TabTrack`` so a nested tab bar inside a page can
        never inherit an outer bar's look.

        The underline uses the palette accent unless ``accent`` is passed;
        ``active_style="accent"`` also tints the active label, while the default
        ``"underline"`` keeps it in the primary text color.
        """
        p = ThemeManager.palette()
        top, right, bottom, left = padding
        font = f"font-size: {font_size}px; font-weight: {font_weight};"

        if variant == "underline":
            indicator = accent or p.accent
            selected_text = indicator if active_style == "accent" else p.text_primary
            return f"""
                #TabTrack {{
                    background: transparent;
                    border: none;
                }}
                #TabTrack QTabBar {{
                    background: transparent;
                }}
                #TabTrack QTabBar::tab {{
                    background: transparent;
                    color: {p.text_secondary};
                    padding: {top}px {right}px {bottom}px {left}px;
                    margin-right: {spacing}px;
                    border: none;
                    border-bottom: {indicator_size}px solid transparent;
                    border-radius: 0;
                    {font}
                }}
                #TabTrack QTabBar::tab:last {{
                    margin-right: 0;
                }}
                #TabTrack QTabBar::tab:selected {{
                    color: {selected_text};
                    border-bottom: {indicator_size}px solid {indicator};
                }}
                #TabTrack QTabBar::tab:hover:!selected {{
                    color: {p.text_primary};
                }}
                #TabTrack QTabBar::tab:disabled {{
                    color: {p.text_muted};
                }}
            """

        track_rule = """
            #TabTrack {
                background: transparent;
                border: none;
            }
        """
        if track:
            # The active pill is inset by the track padding, so the container
            # radius has to grow by that amount or the corners look pinched.
            track_rule = f"""
                #TabTrack {{
                    background-color: {p.surface};
                    border: 1px solid {p.border};
                    border-radius: {radius + track_padding}px;
                }}
            """
            base_background = "transparent"
            base_border = "1px solid transparent"
        else:
            base_background = p.surface
            base_border = f"1px solid {p.border}"

        selected_border = (accent or p.accent) if active_style == "outline" else p.border_light
        selected_background = p.surface_light
        selected_text = p.text_primary
        if active_style == "accent":
            selected_background = accent or p.accent
            selected_border = selected_background
            selected_text = ON_ACCENT
        return f"""
            {track_rule}
            #TabTrack QTabBar {{
                background: transparent;
            }}
            #TabTrack QTabBar::tab {{
                background-color: {base_background};
                color: {p.text_secondary};
                padding: {top}px {right}px {bottom}px {left}px;
                margin-right: {spacing}px;
                border: {base_border};
                border-radius: {radius}px;
                {font}
            }}
            #TabTrack QTabBar::tab:last {{
                margin-right: 0;
            }}
            #TabTrack QTabBar::tab:selected {{
                background-color: {selected_background};
                color: {selected_text};
                border-color: {selected_border};
            }}
            #TabTrack QTabBar::tab:hover:!selected {{
                background-color: {p.surface_light};
                color: {p.text_primary};
            }}
            #TabTrack QTabBar::tab:disabled {{
                color: {p.text_muted};
            }}
        """

    # ═══════════════════════════════════════════════════════════════
    #  CHECKBOXES / RADIO BUTTONS / GROUPBOX
    # ═══════════════════════════════════════════════════════════════
    @classmethod
    def get_checkbox_style(cls, tick_path):
        p = ThemeManager.palette()
        return f"""
            QCheckBox {{
                color: {p.text_primary};
                font-weight: 600;
                font-size: 12px;
                background-color: {p.surface};
                border: 1px solid {p.border};
                border-radius: 8px;
                padding: 6px 12px;
                spacing: 8px;
            }}
            QCheckBox:hover {{
                background-color: {p.surface_light};
                border-color: {p.border_light};
            }}
            QCheckBox::indicator {{
                width: 16px;
                height: 16px;
                border: 1px solid {p.border};
                border-radius: 4px;
                background-color: {p.surface_light};
            }}
            QCheckBox::indicator:hover {{
                border-color: {p.accent};
            }}
            QCheckBox::indicator:checked {{
                background-color: {p.accent};
                border-color: {p.accent};
                image: url('{tick_path}');
            }}
        """

    @classmethod
    def get_settings_link_button_style(cls):
        p = ThemeManager.palette()
        return f"""
            QPushButton {{
                background: transparent;
                border: none;
                padding: 5px 2px;
                text-align: left;
                color: {p.text_secondary};
                font-size: 13px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                color: {p.accent};
            }}
        """

    @classmethod
    def get_board_swatch_button_style(cls):
        p = ThemeManager.palette()
        return f"""
            QPushButton {{
                background: transparent;
                border: 1px solid {p.border};
                border-radius: 8px;
                padding: 2px;
            }}
            QPushButton:hover {{
                border-color: {p.text_muted};
            }}
            QPushButton:checked {{
                border: 2px solid {p.accent};
            }}
        """

    @classmethod
    def get_theme_card_button_style(cls):
        p = ThemeManager.palette()
        return f"""
            QToolButton {{
                background-color: {p.surface_card};
                color: {p.text_primary};
                border: 1px solid {p.border};
                border-radius: 10px;
                padding: 6px;
                font-size: 11px;
                font-weight: 600;
            }}
            QToolButton:hover {{
                border-color: {p.text_muted};
            }}
            QToolButton:checked {{
                border: 2px solid {p.accent};
            }}
        """

    @classmethod
    def get_settings_checkbox_style(cls, tick_path):
        """Borderless checkbox style for settings rows.

        Checked and unchecked states share the same box (size, radius, border)
        so toggles read as one control in every card.
        """
        p = ThemeManager.palette()
        return f"""
            QCheckBox {{
                color: {p.text_primary};
                font-weight: 500;
                font-size: 13px;
                background: transparent;
                border: none;
                padding: 0px;
                spacing: 8px;
            }}
            QCheckBox:hover {{
                color: {p.text_primary};
            }}
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                border: 1px solid {p.border_light};
                border-radius: 4px;
                background-color: {p.surface};
            }}
            QCheckBox::indicator:hover {{
                border-color: {p.accent};
            }}
            QCheckBox::indicator:checked {{
                background-color: {p.accent};
                border-color: {p.accent};
                image: url('{tick_path}');
            }}
            QCheckBox::indicator:checked:hover {{
                background-color: {p.accent_hover};
                border-color: {p.accent_hover};
            }}
            QCheckBox::indicator:disabled {{
                border-color: {p.border};
                background-color: {p.surface_light};
            }}
        """

    @classmethod
    def get_radio_group_style(cls):
        p = ThemeManager.palette()
        return f"""
            QRadioButton {{
                color: {p.text_primary};
                font-size: 13px;
                spacing: 8px;
                padding: 4px 0;
            }}
            QRadioButton::indicator {{
                width: 18px;
                height: 18px;
                border: 1px solid {p.border};
                border-radius: 10px;
                background: {p.surface_light};
            }}
            QRadioButton::indicator:checked {{
                background: {p.accent};
                border-color: {p.accent};
            }}
            QRadioButton::indicator:hover {{
                border-color: {p.accent};
            }}
        """

    @classmethod
    def get_group_box_style(cls):
        p = ThemeManager.palette()
        return f"""
            QGroupBox {{
                font-size: 17px;
                font-weight: 600;
                color: {p.text_primary};
                border: none;
                border-radius: 0;
                margin-top: 18px;
                padding: 6px 0 0 0;
                background-color: transparent;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 0px;
                padding: 0 0 6px 0;
                color: {p.text_primary};
            }}
            QGroupBox QLabel {{
                color: {p.text_primary};
                background: transparent;
                border: none;
            }}
            QGroupBox QLabel#hint_label {{
                color: {p.text_secondary};
            }}
        """

    # ═══════════════════════════════════════════════════════════════
    #  PROGRESS BARS
    # ═══════════════════════════════════════════════════════════════
    @classmethod
    def get_progress_bar_style(cls):
        p = ThemeManager.palette()
        return f"""
            QProgressBar {{
                border: 2px solid {p.border};
                border-radius: 5px;
                background-color: {p.surface};
                text-align: center;
                color: {p.text_primary};
                font-size: 12px;
                font-weight: bold;
                min-height: 22px;
            }}
            QProgressBar::chunk {{
                background-color: {p.accent};
                border-radius: 3px;
            }}
        """

    @classmethod
    def get_think_time_bar_style(cls, colour, track, ratio):
        return f"""
            QLabel {{
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 {colour},
                    stop:{ratio:.4f} {colour},
                    stop:{ratio:.4f} {track},
                    stop:1 {track}
                );
                border: none;
                border-radius: 1px;
            }}
        """

    # ═══════════════════════════════════════════════════════════════
    #  LAYOUT / DIVIDERS / SIDEBAR
    # ═══════════════════════════════════════════════════════════════
    @classmethod
    def get_header_bar_style(cls):
        p = ThemeManager.palette()
        return f"""
            QWidget {{
                background-color: {p.surface};
                border-bottom: 1px solid {p.border};
            }}
        """

    @classmethod
    def get_header_bar_ext_style(cls, bg_color=None):
        p = ThemeManager.palette()
        bg = bg_color or p.surface
        return f"""
            QFrame {{
                background-color: {bg};
                border-bottom: 1px solid {p.border};
            }}
        """

    @classmethod
    def get_pagination_bar_style(cls):
        p = ThemeManager.palette()
        return f"""
            QWidget {{
                background-color: {p.surface};
                border-top: 1px solid {p.border};
            }}
        """

    @classmethod
    def get_scroll_area_style(cls):
        p = ThemeManager.palette()
        return f"""
            QScrollArea {{
                background-color: {p.surface};
                border: 1px solid {p.border};
                border-radius: 8px;
            }}
            QScrollBar:vertical {{
                background-color: {p.background};
                width: 10px;
                margin: 0px 0px 0px 0px;
                border-radius: 5px;
            }}
            QScrollBar::handle:vertical {{
                background-color: {p.border_light};
                min-height: 20px;
                border-radius: 5px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
        """

    @classmethod
    def get_transparent_scroll_area_style(cls):
        p = ThemeManager.palette()
        return f"""
            QScrollArea {{
                background-color: transparent;
                border: none;
            }}
            QScrollBar:vertical {{
                background-color: transparent;
                width: 8px;
                margin: 0px;
                border-radius: 4px;
            }}
            QScrollBar::handle:vertical {{
                background-color: {p.border};
                min-height: 24px;
                border-radius: 4px;
            }}
            QScrollBar::handle:vertical:hover {{
                background-color: {p.border_light};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
        """

    @classmethod
    def get_splitter_style(cls):
        p = ThemeManager.palette()
        return f"""
            QSplitter {{ background-color: {p.background}; }}
            QSplitter::handle {{ background-color: {p.border}; }}
        """

    @classmethod
    def get_divider_style(cls):
        p = ThemeManager.palette()
        return f"""
            QFrame {{
                background-color: {p.border};
                max-height: 1px;
                border: none;
            }}
        """

    @classmethod
    def get_background_style(cls):
        p = ThemeManager.palette()
        return f"background-color: {p.background};"

    @classmethod
    def get_surface_style(cls):
        p = ThemeManager.palette()
        return f"background-color: {p.surface};"

    @classmethod
    def get_empty_state_cta_style(cls, drag_active: bool = False):
        """Landing hero card; the accent border doubles as the drop-target cue."""
        p = ThemeManager.palette()
        border = p.accent if drag_active else p.border
        return f"""
            QFrame#EmptyStateCTA {{
                background-color: {p.surface_light};
                border: 1px solid {border};
                border-radius: 8px;
            }}
        """

    @classmethod
    def get_hero_hint_style(cls, drag_active: bool = False):
        p = ThemeManager.palette()
        color = p.accent if drag_active else p.text_secondary
        weight = "600" if drag_active else "500"
        return (
            f"font-size: 12px; font-weight: {weight}; color: {color}; "
            "background: transparent;"
        )

    @classmethod
    def get_keycap_style(cls):
        p = ThemeManager.palette()
        return (
            f"font-size: 11px; font-weight: 600; color: {p.text_muted}; "
            f"background-color: {p.surface}; border: 1px solid {p.border}; "
            "border-radius: 9px; padding: 2px 8px;"
        )

    @classmethod
    def get_sidebar_style(cls):
        p = ThemeManager.palette()
        return f"""
            #Sidebar {{
                background-color: {p.surface};
                border-right: 1px solid {p.border};
            }}
            QPushButton {{
                background-color: transparent;
                border: none;
                border-radius: 10px;
                padding: 12px 16px;
                text-align: left;
                font-size: 14px;
                font-weight: 500;
                color: {p.text_secondary};
            }}
            QPushButton:hover {{
                background-color: {p.surface_light};
                color: {p.text_primary};
            }}
            QPushButton:checked {{
                background-color: {p.accent};
                color: white;
                font-weight: 600;
            }}
        """

    @classmethod
    def get_menu_style(cls):
        p = ThemeManager.palette()
        return f"""
            QMenu {{
                background-color: {p.surface_card};
                border: 1px solid {p.border};
                border-radius: 8px;
                padding: 6px;
            }}
            QMenu::item {{
                padding: 8px 16px;
                border-radius: 6px;
                color: {p.text_primary};
            }}
            QMenu::item:selected {{
                background-color: {p.surface_light};
            }}
        """

    @classmethod
    def get_list_widget_style(cls):
        p = ThemeManager.palette()
        return f"""
            QListWidget {{
                background-color: {p.background};
                border: none;
                outline: none;
            }}
            QListWidget::item {{
                background-color: {p.background};
                border: none;
                border-bottom: 1px solid {p.surface_light};
                padding: 0px;
                margin: 0px;
            }}
            QListWidget::item:hover {{
                background-color: {p.surface};
            }}
        """

    @classmethod
    def get_book_row_style(cls):
        p = ThemeManager.palette()
        return f"""
            QWidget {{
                border-bottom: 1px solid {p.border};
            }}
            QWidget:hover {{
                background-color: {p.surface_light};
            }}
        """

    # ═══════════════════════════════════════════════════════════════
    #  ANALYSIS PAGE
    # ═══════════════════════════════════════════════════════════════
    CAPTURED_PIECES_STYLE = """
        QLabel {
            font-size: 16px;
            font-weight: bold;
            padding: 2px;
        }
    """

    @classmethod
    def get_captured_pieces_style(cls):
        return f"""
            QFrame {{
                background: transparent;
                border: none;
                padding: 0px;
            }}
            {cls.CAPTURED_PIECES_STYLE}
        """

    @classmethod
    def get_piece_chip_style(cls, fg, bg, compact=True):
        font_size = 22 if compact else 26
        padding = "1px 5px" if compact else "1px 6px"
        return f"""
            color: {fg}; background-color: {bg};
            font-size: {font_size}px; padding: {padding}; border-radius: 4px;
        """

    @classmethod
    def get_advantage_chip_style(cls, compact=True):
        p = ThemeManager.palette()
        font_size = 14 if compact else 15
        return f"""
            color: {p.text_primary};
            background-color: {p.surface_light};
            font-weight: bold; font-size: {font_size}px;
            padding: 3px 7px; border-radius: 4px;
            margin-right: 4px;
        """

    @classmethod
    def get_digital_clock_style(cls, bg, fg, border, compact=True):
        font_size = 16 if compact else 18
        padding = "3px 8px" if compact else "4px 10px"
        radius = 6 if compact else 7
        return f"""
            QLabel {{
                color: {fg};
                background-color: {bg};
                font-family: 'Courier New', 'Monospace', monospace;
                font-size: {font_size}px;
                font-weight: bold;
                padding: {padding};
                border-radius: {radius}px;
                border: 1px solid {border};
            }}
        """

    @classmethod
    def get_engine_lines_style(cls):
        p = ThemeManager.palette()
        return f"""
            QFrame#EngineLinesPanel {{
                background-color: {p.surface};
                border: 1px solid {p.border};
                border-radius: 10px;
            }}
            QWidget#EngineLineRow {{
                background-color: transparent;
                border: none;
                border-radius: 6px;
            }}
            QWidget#EngineLineRow:hover {{
                background-color: {p.surface_light};
            }}
            QWidget#EngineLineRow QLabel {{
                border: none;
                background: transparent;
            }}
            QLabel#EngineLinesEmpty {{
                color: {p.text_muted};
                font-size: 12px;
            }}
        """

    @staticmethod
    def _blend_hex(color_a, color_b, ratio):
        """Linear blend between two ``#RRGGBB`` colours (ratio 0..1)."""
        ratio = max(0.0, min(1.0, ratio))
        a = color_a.lstrip("#")
        b = color_b.lstrip("#")
        if len(a) != 6 or len(b) != 6:
            return color_a
        channels = [
            round(int(a[index : index + 2], 16) * (1 - ratio) + int(b[index : index + 2], 16) * ratio)
            for index in (0, 2, 4)
        ]
        return "#" + "".join(f"{channel:02X}" for channel in channels)

    @classmethod
    def _contrast_text(cls, background):
        """Pick the palette's light or dark ink for a blended badge background."""
        p = ThemeManager.palette()
        value = background.lstrip("#")
        if len(value) != 6:
            return p.text_primary
        red, green, blue = (int(value[index : index + 2], 16) for index in (0, 2, 4))
        luminance = 0.2126 * red + 0.7152 * green + 0.0722 * blue
        return p.piece_black if luminance > 140 else p.piece_white

    @classmethod
    def get_engine_score_badge_style(cls, line):
        """Score pill for a White-perspective ``EngineLine``."""
        p = ThemeManager.palette()
        if line.mate is not None:
            if line.mate > 0:
                return cls.get_eval_badge_style(p.piece_white, p.piece_black)
            return cls.get_eval_badge_style(p.piece_black, p.piece_white)
        if line.cp is None or line.cp == 0:
            return cls.get_eval_badge_style(p.surface_light, p.text_primary)

        intensity = min(1.0, abs(line.cp) / 300.0)
        if line.cp > 0:
            background = cls._blend_hex(p.surface_light, p.piece_white, 0.12 + 0.55 * intensity)
        else:
            background = cls._blend_hex(p.surface_light, p.piece_black, 0.12 + 0.60 * intensity)
        return cls.get_eval_badge_style(background, cls._contrast_text(background))

    @classmethod
    def get_engine_status_style(cls, color):
        return f"""
            font-size: 11px;
            color: {color};
            padding: 2px 0px;
        """

    # ═══════════════════════════════════════════════════════════════
    #  HISTORY / GAME LIST PAGE
    # ═══════════════════════════════════════════════════════════════
    @classmethod
    def get_game_card_style(cls, border_radius=10, compact=False):
        p = ThemeManager.palette()
        hover_bg = f"background-color: {p.surface};" if compact else ""
        card_padding = "10px 14px" if compact else "8px 14px"
        return f"""
            QFrame#GameCard {{
                background-color: {p.surface_card};
                border: 1px solid {p.border};
                border-radius: {border_radius}px;
                padding: {card_padding};
            }}
            QFrame#GameCard:hover {{
                {hover_bg}
                border-color: {p.accent};
            }}
            QFrame#GameCard QLabel {{
                background: transparent;
                border: none;
            }}
        """

    # ═══════════════════════════════════════════════════════════════
    #  STATS / METRICS PAGE
    # ═══════════════════════════════════════════════════════════════
    @classmethod
    def get_ratio_bar_segment_style(
        cls, color, top_left=False, top_right=False, bottom_left=False, bottom_right=False
    ):
        radii = [
            "4px" if top_left else "0px",
            "4px" if top_right else "0px",
            "4px" if bottom_right else "0px",
            "4px" if bottom_left else "0px",
        ]
        radius = " ".join(radii)
        return f"""
            QLabel {{
                background-color: {color};
                color: #FFFFFF;
                font-size: 9px;
                font-weight: bold;
                border: none;
                border-radius: {radius};
            }}
        """

    @classmethod
    def get_accuracy_color(cls, accuracy: float) -> str:
        acc = max(0.0, min(100.0, float(accuracy)))
        if acc <= 50.0:
            t = acc / 50.0
            r = int(0xD0 + (0xF1 - 0xD0) * t)
            g = int(0x20 + (0xC4 - 0x20) * t)
            b = int(0x30 + (0x0F - 0x30) * t)
        elif acc <= 75.0:
            t = (acc - 50.0) / 25.0
            r = int(0xF1 + (0x2E - 0xF1) * t)
            g = int(0xC4 + (0xCC - 0xC4) * t)
            b = int(0x0F + (0x71 - 0x0F) * t)
        else:
            t = (acc - 75.0) / 25.0
            r = int(0x2E + (0x00 - 0x2E) * t)
            g = int(0xCC + (0xD4 - 0xCC) * t)
            b = int(0x71 + (0xAA - 0x71) * t)
        return f"#{r:02X}{g:02X}{b:02X}"

    # ═══════════════════════════════════════════════════════════════
    #  SETTINGS PAGE
    # ═══════════════════════════════════════════════════════════════
    @classmethod
    def get_settings_default_button_style(cls):
        p = ThemeManager.palette()
        return f"""
            QPushButton {{
                background-color: {p.surface_light};
                color: {p.text_primary};
                border: 1px solid {p.border};
                padding: 8px 16px;
                border-radius: 6px;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: {p.surface};
                border-color: {p.accent};
            }}
        """

    @classmethod
    def get_settings_danger_button_style(cls):
        p = ThemeManager.palette()
        return f"""
            QPushButton {{
                background-color: {p.background};
                color: {cls.COLOR_BLUNDER};
                border: 1px solid {cls.COLOR_BLUNDER};
                padding: 8px 16px;
                border-radius: 6px;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: {p.surface_light};
                color: {cls.COLOR_BLUNDER};
                border: 1px solid {cls.COLOR_BLUNDER};
            }}
        """

    @classmethod
    def get_settings_square_icon_style(cls):
        p = ThemeManager.palette()
        return f"""
            QPushButton {{
                background-color: {p.surface_light};
                color: {p.text_primary};
                border: 1px solid {p.border};
                border-radius: 6px;
                font-size: 16px; font-weight: bold;
                min-width: 28px; max-width: 28px;
                min-height: 28px; max-height: 28px;
            }}
            QPushButton:hover {{
                background-color: {p.surface};
                color: {p.text_primary};
                border-color: {p.accent};
            }}
        """

    # ═══════════════════════════════════════════════════════════════
    #  UTILITY
    # ═══════════════════════════════════════════════════════════════
    @classmethod
    def set_accent_color(cls, color_hex):
        ThemeManager.set_accent(color_hex)

    @classmethod
    def get_class_color(cls, classification: str) -> str:
        return ThemeManager.get_class_color(classification)

    @classmethod
    def get_board_colors(cls, theme_name="Green"):
        return ThemeManager.get_board_colors(theme_name)
