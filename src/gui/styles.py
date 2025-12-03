from PyQt6.QtGui import QColor

class Styles:
    # Color Palette
    COLOR_BACKGROUND = "#1E1E1E"
    COLOR_SURFACE = "#252526"
    COLOR_SURFACE_LIGHT = "#333333"
    COLOR_TEXT_PRIMARY = "#D4D4D4"
    COLOR_TEXT_SECONDARY = "#AAAAAA"
    COLOR_ACCENT = "#007ACC"
    COLOR_ACCENT_HOVER = "#0098FF"
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
    
    # QSS Stylesheet
    DARK_THEME = f"""
        QMainWindow, QWidget {{
            background-color: {COLOR_BACKGROUND};
            color: {COLOR_TEXT_PRIMARY};
            font-family: 'Segoe UI', 'Roboto', sans-serif;
            font-size: 14px;
        }}
        
        QFrame, QSplitter::handle {{
            background-color: {COLOR_SURFACE};
        }}
        
        QSplitter::handle {{
            width: 2px;
            background-color: {COLOR_BORDER};
        }}
        
        /* Tables */
        QTableWidget {{
            background-color: {COLOR_SURFACE};
            gridline-color: {COLOR_BORDER};
            border: none;
            selection-background-color: {COLOR_ACCENT};
            selection-color: white;
        }}
        
        QTableWidget::item {{
            color: {COLOR_TEXT_PRIMARY};
            padding: 5px;
        }}
        
        QHeaderView::section {{
            background-color: {COLOR_SURFACE_LIGHT};
            color: {COLOR_TEXT_PRIMARY};
            padding: 2px;
            border: 1px solid {COLOR_BORDER};
            font-size: 12px;
        }}
        
        /* Lists */
        QListWidget {{
            background-color: {COLOR_SURFACE};
            border: 1px solid {COLOR_BORDER};
            border-radius: 4px;
        }}
        
        QListWidget::item:selected {{
            background-color: {COLOR_ACCENT};
            color: white;
        }}
        
        /* Labels */
        QLabel {{
            color: {COLOR_TEXT_PRIMARY};
        }}
        
        /* Menu Bar */
        QMenuBar {{
            background-color: {COLOR_SURFACE};
            color: {COLOR_TEXT_PRIMARY};
        }}
        
        QMenuBar::item:selected {{
            background-color: {COLOR_ACCENT};
        }}
        
        QMenu {{
            background-color: {COLOR_SURFACE};
            color: {COLOR_TEXT_PRIMARY};
            border: 1px solid {COLOR_BORDER};
        }}
        
        QMenu::item:selected {{
            background-color: {COLOR_ACCENT};
        }}
    """
    
    CAPTURED_PIECES_STYLE = f"""
        QLabel {{
            font-size: 16px;
            font-weight: bold;
            padding: 2px;
        }}
    """
    
    CONTROL_BUTTON_STYLE = f"""
        QPushButton {{
            background-color: {COLOR_SURFACE_LIGHT};
            color: {COLOR_TEXT_PRIMARY};
            border: 1px solid {COLOR_BORDER};
            border-radius: 4px;
            padding: 5px 10px;
            font-size: 16px;
        }}
        QPushButton:hover {{
            background-color: {COLOR_BORDER};
        }}
        QPushButton:pressed {{
            background-color: {COLOR_ACCENT};
        }}
    """
    
    BUTTON_STYLE = f"""
        QPushButton {{
            background-color: {COLOR_ACCENT};
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 4px;
            font-weight: bold;
            font-size: 14px;
        }}
        QPushButton:hover {{
            background-color: {COLOR_ACCENT_HOVER};
        }}
        QPushButton:pressed {{
            background-color: {COLOR_ACCENT};
        }}
        QPushButton:disabled {{
            background-color: {COLOR_SURFACE_LIGHT};
            color: {COLOR_TEXT_SECONDARY};
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