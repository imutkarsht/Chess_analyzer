from src.gui.theme import ThemeManager
from src.gui.theme.palette import BOARD_THEMES


class _StylesMeta(type):
    @property
    def COLOR_BACKGROUND(cls): return ThemeManager.palette().background
    @property
    def COLOR_SURFACE(cls): return ThemeManager.palette().surface
    @property
    def COLOR_SURFACE_LIGHT(cls): return ThemeManager.palette().surface_light
    @property
    def COLOR_SURFACE_CARD(cls): return ThemeManager.palette().surface_card
    @property
    def COLOR_TEXT_PRIMARY(cls): return ThemeManager.palette().text_primary
    @property
    def COLOR_TEXT_SECONDARY(cls): return ThemeManager.palette().text_secondary
    @property
    def COLOR_TEXT_MUTED(cls): return ThemeManager.palette().text_muted
    @property
    def COLOR_ACCENT(cls): return ThemeManager.palette().accent
    @property
    def COLOR_ACCENT_HOVER(cls): return ThemeManager.palette().accent_hover
    @property
    def COLOR_ACCENT_SUBTLE(cls): return ThemeManager.palette().accent_subtle
    @property
    def COLOR_BORDER(cls): return ThemeManager.palette().border
    @property
    def COLOR_BORDER_LIGHT(cls): return ThemeManager.palette().border_light
    @property
    def COLOR_HIGHLIGHT(cls): return ThemeManager.palette().highlight
    @property
    def COLOR_PIECE_WHITE(cls): return ThemeManager.palette().piece_white
    @property
    def COLOR_PIECE_BLACK(cls): return ThemeManager.palette().piece_black
    @property
    def COLOR_BOARD_HIGHLIGHT(cls): return ThemeManager.palette().board_highlight

    @property
    def COLOR_BRILLIANT(cls): return ThemeManager.get_class_color("Brilliant")
    @property
    def COLOR_GREAT(cls): return ThemeManager.get_class_color("Great")
    @property
    def COLOR_BEST(cls): return ThemeManager.get_class_color("Best")
    @property
    def COLOR_EXCELLENT(cls): return ThemeManager.get_class_color("Excellent")
    @property
    def COLOR_GOOD(cls): return ThemeManager.get_class_color("Good")
    @property
    def COLOR_INACCURACY(cls): return ThemeManager.get_class_color("Inaccuracy")
    @property
    def COLOR_MISTAKE(cls): return ThemeManager.get_class_color("Mistake")
    @property
    def COLOR_BLUNDER(cls): return ThemeManager.get_class_color("Blunder")
    @property
    def COLOR_MISS(cls): return ThemeManager.get_class_color("Miss")
    @property
    def COLOR_BOOK(cls): return ThemeManager.get_class_color("Book")

    # Result colors for win/draw/loss bars
    @property
    def COLOR_RESULT_WIN(cls): return "#4FA859"
    @property
    def COLOR_RESULT_DRAW(cls): return "#8E9AA6"
    @property
    def COLOR_RESULT_LOSS(cls): return "#2F3640"

    # Engine status colors
    @property
    def COLOR_ENGINE_READY(cls): return "#27ae60"
    @property
    def COLOR_ENGINE_BUSY(cls): return "#e67e22"

    @property
    def BOARD_THEMES(cls): return BOARD_THEMES


class Styles(metaclass=_StylesMeta):

    @classmethod
    def get_board_colors(cls, theme_name="Green"):
        return ThemeManager.get_board_colors(theme_name)

    @classmethod
    def set_accent_color(cls, color_hex):
        ThemeManager.set_accent(color_hex)

    @classmethod
    def get_class_color(cls, classification: str) -> str:
        return ThemeManager.get_class_color(classification)

    @classmethod
    def get_accuracy_color(cls, accuracy: float) -> str:
        """Map accuracy percentage (0-100) to smooth color gradient:
        0% = red (#D02030) -> 50% = yellow (#F1C40F) -> 75% = light green (#2ECC71) -> 100% = dark green (#00D4AA).
        """
        acc = max(0.0, min(100.0, float(accuracy)))
        if acc <= 50.0:
            # Interpolate Red (#D02030) -> Yellow (#F1C40F)
            t = acc / 50.0
            r = int(0xD0 + (0xF1 - 0xD0) * t)
            g = int(0x20 + (0xC4 - 0x20) * t)
            b = int(0x30 + (0x0F - 0x30) * t)
        elif acc <= 75.0:
            # Interpolate Yellow (#F1C40F) -> Light Green (#2ECC71)
            t = (acc - 50.0) / 25.0
            r = int(0xF1 + (0x2E - 0xF1) * t)
            g = int(0xC4 + (0xCC - 0xC4) * t)
            b = int(0x0F + (0x71 - 0x0F) * t)
        else:
            # Interpolate Light Green (#2ECC71) -> Dark Green (#00D4AA)
            t = (acc - 75.0) / 25.0
            r = int(0x2E + (0x00 - 0x2E) * t)
            g = int(0xCC + (0xD4 - 0xCC) * t)
            b = int(0x71 + (0xAA - 0x71) * t)
        return f"#{r:02X}{g:02X}{b:02X}"

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
    
    CAPTURED_PIECES_STYLE = """
        QLabel {
            font-size: 16px;
            font-weight: bold;
            padding: 2px;
        }
    """

    @classmethod
    def get_captured_pieces_style(cls):
        p = ThemeManager.palette()
        return f"""
            QFrame {{
                background-color: {p.surface};
                border: 1px solid {p.border};
                border-radius: 8px;
                padding: 5px;
            }}
            {cls.CAPTURED_PIECES_STYLE}
        """

    @classmethod
    def get_piece_chip_style(cls, fg, bg):
        return f"""
            color: {fg}; background-color: {bg};
            font-size: 26px; padding: 2px 6px; border-radius: 4px;
        """

    @classmethod
    def get_advantage_chip_style(cls):
        p = ThemeManager.palette()
        return f"""
            color: {p.text_primary};
            background-color: {p.surface_light};
            font-weight: bold; font-size: 16px;
            padding: 4px 8px; border-radius: 4px;
            margin-right: 4px;
        """

    @classmethod
    def get_digital_clock_style(cls, bg, fg, border):
        return f"""
            QLabel {{
                color: {fg};
                background-color: {bg};
                font-family: 'Courier New', 'Monospace', monospace;
                font-size: 18px;
                font-weight: bold;
                padding: 4px 10px;
                border-radius: 6px;
                border: 1px solid {border};
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
        p = ThemeManager.palette()
        return f"""
            QPushButton {{
                background-color: #2D4A6B;
                color: white;
                border: 1px solid #3D5A7B;
                border-radius: 6px;
                padding: 8px 14px;
                font-size: 14px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: #3A5F85;
                border: 1px solid #4A7095;
            }}
            QPushButton:pressed {{
                background-color: #254060;
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
    def get_header_bar_style(cls):
        p = ThemeManager.palette()
        return f"""
            QWidget {{
                background-color: {p.surface};
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
    def get_background_style(cls):
        p = ThemeManager.palette()
        return f"background-color: {p.background};"

    @classmethod
    def get_surface_style(cls):
        p = ThemeManager.palette()
        return f"background-color: {p.surface};"

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
        return """
            QLineEdit {
                background-color: #3d1a1a;
                color: #FFFFFF;
                border: 1px solid #e74c3c;
                border-radius: 6px;
                padding: 2px 8px;
                font-size: 12px;
                font-weight: 600;
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

    @classmethod
    def get_ratio_bar_segment_style(cls, color, top_left=False, top_right=False, bottom_left=False, bottom_right=False):
        radii = []
        if top_left: radii.append("4px")
        else: radii.append("0px")
        if top_right: radii.append("4px")
        else: radii.append("0px")
        if bottom_right: radii.append("4px")
        else: radii.append("0px")
        if bottom_left: radii.append("4px")
        else: radii.append("0px")
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
    def get_engine_status_style(cls, color):
        return f"""
            font-size: 11px;
            color: {color};
            padding: 2px 0px;
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
    def get_splitter_style(cls):
        p = ThemeManager.palette()
        return f"""
            QSplitter {{ background-color: {p.background}; }}
            QSplitter::handle {{ background-color: {p.border}; }}
        """

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
    def get_frame_style(cls, border_radius=12, hover_accent=True, object_name=None):
        p = ThemeManager.palette()
        selector = f"QFrame#{object_name}" if object_name else "QFrame"
        hover_style = f"""
            {selector}:hover {{
                border: 1px solid {p.accent};
            }}
        """ if hover_accent else ""
        
        return f"""
            {selector} {{
                background-color: {p.surface};
                border: 1px solid {p.border};
                border-radius: {border_radius}px;
            }}
            {hover_style}
        """
    
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
    def get_dialog_surface_style(cls):
        p = ThemeManager.palette()
        return f"""
            background-color: {p.surface};
            border: 1px solid {p.border};
            border-radius: 12px;
        """
    
    @classmethod
    def get_analysis_lines_style(cls):
        p = ThemeManager.palette()
        return f"""
            QFrame {{
                background-color: {p.surface};
                border: 1px solid {p.border};
                border-radius: 12px;
                padding: 10px;
            }}
            QWidget#AnalysisRow {{
                background-color: {p.surface_light};
                border-radius: 8px;
                border: 1px solid {p.border};
            }}
            QWidget#AnalysisRow:hover {{
                background-color: {p.surface_light};
                border: 1px solid {p.accent};
            }}
            QLabel {{
                border: none;
                background: transparent;
            }}
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
    def get_tab_style(cls):
        p = ThemeManager.palette()
        return f"""
            QTabWidget {{
                background-color: {p.background};
            }}
            QTabWidget::pane {{
                border: none;
                background-color: transparent;
            }}
            QTabBar {{
                qproperty-drawBase: 0;
            }}
            QTabBar::tab {{
                background-color: {p.surface};
                color: {p.text_secondary};
                padding: 7px 18px;
                font-weight: 600;
                font-size: 12px;
                border: 1px solid {p.border};
                border-radius: 8px;
                margin-right: 6px;
            }}
            QTabBar::tab:selected {{
                background-color: {p.surface_light};
                color: {p.text_primary};
                border-color: {p.accent};
            }}
            QTabBar::tab:hover:!selected {{
                background-color: {p.surface_light};
                color: {p.text_primary};
                border-color: {p.border_light};
            }}
        """

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
    def get_move_list_table_style(cls):
        p = ThemeManager.palette()
        return f"""
            QTableWidget {{
                background-color: {p.surface};
                border: 1px solid {p.border};
                border-radius: 8px;
                gridline-color: transparent;
                font-size: 13px;
            }}
            QTableWidget::item {{
                padding: 4px 6px;
                border: none;
                border-bottom: 1px solid {p.surface_light};
            }}
            QTableWidget::item:hover {{
                background-color: {p.surface_light};
                border-radius: 4px;
            }}
            QTableWidget::item:selected {{
                background-color: {p.highlight};
                color: {p.text_primary};
                border-radius: 4px;
            }}
            QHeaderView::section {{
                background-color: {p.surface_light};
                color: {p.text_primary};
                padding: 8px 6px;
                border: none;
                border-bottom: 2px solid {p.accent};
                font-weight: 700;
                font-size: 13px;
            }}
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
                background-color: {cls.COLOR_BLUNDER};
                color: #FFFFFF;
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

    @classmethod
    def get_group_box_style(cls):
        p = ThemeManager.palette()
        return f"""
            QGroupBox {{
                font-size: 16px;
                font-weight: bold;
                color: {p.text_primary};
                border: 1px solid {p.border};
                border-radius: 8px;
                margin-top: 20px;
                padding: 20px 15px 15px 15px;
                background-color: {p.surface};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 15px;
                padding: 0 5px;
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

    @classmethod
    def get_transparent_label_style(cls):
        return "border: none; background: transparent;"
