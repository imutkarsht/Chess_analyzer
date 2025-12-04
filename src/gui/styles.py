from PyQt6.QtGui import QColor

class Styles:
    # Color Palette
    COLOR_BACKGROUND = "#1E1E1E"
    COLOR_SURFACE = "#252526"
    COLOR_SURFACE_LIGHT = "#333333"
    COLOR_TEXT_PRIMARY = "#D4D4D4"
    COLOR_TEXT_SECONDARY = "#AAAAAA"
    
    # Dynamic Accent
    COLOR_ACCENT = "#FF9500" # Default Orange
    COLOR_ACCENT_HOVER = "#FFAA33"
    
    COLOR_BORDER = "#3E3E42"
    COLOR_HIGHLIGHT = "#3A3A3C" # For current move row
    
    # Piece Colors
    COLOR_PIECE_WHITE = "#F0F0F0"
    COLOR_PIECE_BLACK = "#111111"
    
    # Move Classification Colors
    COLOR_BRILLIANT = "#1BACA6"
    COLOR_GREAT = "#5B8BB0"
    COLOR_BEST = "#96BC4B"
    COLOR_EXCELLENT = "#96BC4B"
    COLOR_GOOD = "#96BC4B"
    COLOR_INACCURACY = "#F0C15C"
    COLOR_MISTAKE = "#E6912C"
    COLOR_BLUNDER = "#CC3333"
    COLOR_MISS = "#E6912C"
    COLOR_BOOK = "#A88865"

    @classmethod
    def set_accent_color(cls, color_hex):
        cls.COLOR_ACCENT = color_hex
        cls.COLOR_ACCENT_HOVER = color_hex 

    @classmethod
    def get_theme(cls):
        return f"""
            QMainWindow, QWidget {{
                background-color: {cls.COLOR_BACKGROUND};
                color: {cls.COLOR_TEXT_PRIMARY};
                font-family: 'Segoe UI', 'Roboto', sans-serif;
                font-size: 14px;
            }}
            
            QFrame, QSplitter::handle {{
                background-color: {cls.COLOR_SURFACE};
            }}
            
            QSplitter::handle {{
                width: 2px;
                background-color: {cls.COLOR_BORDER};
            }}
            
            /* Tables */
            QTableWidget {{
                background-color: {cls.COLOR_SURFACE};
                gridline-color: {cls.COLOR_BORDER};
                border: 1px solid {cls.COLOR_BORDER};
                border-radius: 6px;
                selection-background-color: {cls.COLOR_ACCENT};
                selection-color: white;
            }}
            
            QTableWidget::item {{
                color: {cls.COLOR_TEXT_PRIMARY};
                padding: 8px;
            }}
            
            QHeaderView::section {{
                background-color: {cls.COLOR_SURFACE_LIGHT};
                color: {cls.COLOR_TEXT_PRIMARY};
                padding: 6px;
                border: none;
                border-bottom: 2px solid {cls.COLOR_BORDER};
                font-weight: bold;
            }}
            
            /* Lists */
            QListWidget {{
                background-color: {cls.COLOR_SURFACE};
                border: 1px solid {cls.COLOR_BORDER};
                border-radius: 6px;
                padding: 5px;
            }}
            
            QListWidget::item {{
                padding: 8px;
                border-radius: 4px;
            }}

            QListWidget::item:selected {{
                background-color: {cls.COLOR_ACCENT};
                color: white;
            }}
            
            /* Labels */
            QLabel {{
                color: {cls.COLOR_TEXT_PRIMARY};
            }}
            
            /* Scrollbars */
            QScrollBar:vertical {{
                border: none;
                background: {cls.COLOR_BACKGROUND};
                width: 10px;
                margin: 0px;
            }}
            QScrollBar::handle:vertical {{
                background: {cls.COLOR_SURFACE_LIGHT};
                min-height: 20px;
                border-radius: 5px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
        """
    
    CAPTURED_PIECES_STYLE = f"""
        QLabel {{
            font-size: 16px;
            font-weight: bold;
            padding: 2px;
        }}
    """
    
    @classmethod
    def get_control_button_style(cls):
        return f"""
            QPushButton {{
                background-color: {cls.COLOR_SURFACE_LIGHT};
                color: {cls.COLOR_TEXT_PRIMARY};
                border: 1px solid {cls.COLOR_BORDER};
                border-radius: 4px;
                padding: 5px 10px;
                font-size: 16px;
            }}
            QPushButton:hover {{
                background-color: {cls.COLOR_BORDER};
            }}
            QPushButton:pressed {{
                background-color: {cls.COLOR_ACCENT};
            }}
        """
    
    @classmethod
    def get_button_style(cls):
        return f"""
            QPushButton {{
                background-color: {cls.COLOR_ACCENT};
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
                font-size: 14px;
            }}
            QPushButton:hover {{
                background-color: {cls.COLOR_ACCENT_HOVER};
            }}
            QPushButton:pressed {{
                background-color: {cls.COLOR_ACCENT};
            }}
            QPushButton:disabled {{
                background-color: {cls.COLOR_SURFACE_LIGHT};
                color: {cls.COLOR_TEXT_SECONDARY};
            }}
        """
    
    @classmethod
    def get_sidebar_style(cls):
        return f"""
            QWidget {{
                background-color: {cls.COLOR_SURFACE};
                border-right: 1px solid {cls.COLOR_BORDER};
            }}
            QPushButton {{
                background-color: transparent;
                border: none;
                border-radius: 8px;
                padding: 10px;
                text-align: left;
                padding-left: 15px;
            }}
            QPushButton:hover {{
                background-color: {cls.COLOR_SURFACE_LIGHT};
            }}
            QPushButton:checked {{
                background-color: {cls.COLOR_ACCENT};
                color: white;
            }}
        """

    @staticmethod
    def get_class_color(classification: str) -> str:
        mapping = {
            "Brilliant": Styles.COLOR_BRILLIANT,
            "Great": Styles.COLOR_GREAT,
            "Best": Styles.COLOR_BEST,
            "Excellent": Styles.COLOR_EXCELLENT,
            "Good": Styles.COLOR_GOOD,
            "Book": Styles.COLOR_BOOK,
            "Inaccuracy": Styles.COLOR_INACCURACY,
            "Mistake": Styles.COLOR_MISTAKE,
            "Blunder": Styles.COLOR_BLUNDER,
            "Miss": Styles.COLOR_MISS,
        }
        return mapping.get(classification, Styles.COLOR_TEXT_PRIMARY)