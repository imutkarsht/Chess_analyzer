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
    def get_control_button_style(cls):
        p = ThemeManager.palette()
        return f"""
            QPushButton {{
                background-color: {p.surface_light};
                color: {p.text_primary};
                border: 1px solid {p.border};
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 13px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: {p.surface};
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
    def get_label_style(cls, size=14, color=None, bold=False):
        p = ThemeManager.palette()
        if color is None:
            color = p.text_primary
        weight = "bold" if bold else "normal"
        return f"font-size: {size}px; color: {color}; font-weight: {weight};"
    
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
    def get_frame_style(cls, border_radius=12, hover_accent=True):
        p = ThemeManager.palette()
        hover_style = f"""
            QFrame:hover {{
                border: 1px solid {p.accent};
            }}
        """ if hover_accent else ""
        
        return f"""
            QFrame {{
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
                border: 1px solid {p.border};
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
                background-color: {p.background};
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
    def get_transparent_label_style(cls):
        return "border: none; background: transparent;"
