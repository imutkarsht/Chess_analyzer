
class Styles:
    # Color Palette
    COLOR_BACKGROUND = "#1A1A1D"
    COLOR_SURFACE = "#252529"
    COLOR_SURFACE_LIGHT = "#2E2E33"
    COLOR_SURFACE_CARD = "#2A2A2E"  # Slightly elevated cards
    COLOR_TEXT_PRIMARY = "#E4E4E7"
    COLOR_TEXT_SECONDARY = "#9CA3AF"
    COLOR_TEXT_MUTED = "#6B7280"  # For move numbers, less important info
    
    # Dynamic Accent
    COLOR_ACCENT = "#FF9500"  # Default Orange
    COLOR_ACCENT_HOVER = "#FFB340"
    COLOR_ACCENT_SUBTLE = "#3D2B14"  # For subtle accent backgrounds
    
    COLOR_BORDER = "#3E3E45"
    COLOR_BORDER_LIGHT = "#4A4A52"  # For hover states
    COLOR_HIGHLIGHT = "#3A3A40"  # For current move row
    
    # Piece Colors
    COLOR_PIECE_WHITE = "#F0F0F0"
    COLOR_PIECE_BLACK = "#111111"
    
    # Move Classification Colors (Refined for visual appeal)
    COLOR_BRILLIANT = "#00D4AA"  # Brighter teal
    COLOR_GREAT = "#4CACEB"  # Vibrant blue
    COLOR_BEST = "#8BC34A"  # Consistent green
    COLOR_EXCELLENT = "#8BC34A"
    COLOR_GOOD = "#7CB342"  # Slightly different green
    COLOR_INACCURACY = "#FFD54F"  # Warm yellow
    COLOR_MISTAKE = "#F39C12"  # Warmer amber
    COLOR_BLUNDER = "#E74C3C"  # Softer but vibrant red
    COLOR_MISS = "#E67E22"  # Distinct orange
    COLOR_BOOK = "#B8956E"  # Warm book brown

    # Board Themes
    BOARD_THEMES = {
        "Green": {"dark": "#769656", "light": "#EEEED2"},
        "Blue": {"dark": "#4B7399", "light": "#E0E0E0"},
        "Brown": {"dark": "#B58863", "light": "#F0D9B5"},
        "Gray": {"dark": "#888888", "light": "#E0E0E0"},
        "Purple": {"dark": "#9b59b6", "light": "#ecf0f1"},
        "Teal": {"dark": "#1abc9c", "light": "#ffffff"},
        "Cherry": {"dark": "#c0392b", "light": "#ecf0f1"},
        "Neon": {"dark": "dynamic", "light": "#E0E0E0"} # Uses current accent
    }

    @classmethod
    def get_board_colors(cls, theme_name="Green"):
        theme = cls.BOARD_THEMES.get(theme_name, cls.BOARD_THEMES["Green"])
        
        dark = theme["dark"]
        light = theme["light"]
        
        if dark == "dynamic":
            dark = cls.COLOR_ACCENT
            
        return {"dark": dark, "light": light}

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
                font-family: 'Segoe UI', 'Inter', 'Roboto', sans-serif;
                font-size: 14px;
            }}
            
            QFrame, QSplitter::handle {{
                background-color: {cls.COLOR_SURFACE};
            }}
            
            QSplitter::handle {{
                width: 3px;
                background-color: {cls.COLOR_BORDER};
            }}
            QSplitter::handle:hover {{
                background-color: {cls.COLOR_ACCENT};
            }}
            
            /* Tables */
            QTableWidget {{
                background-color: {cls.COLOR_SURFACE};
                gridline-color: transparent;
                border: 1px solid {cls.COLOR_BORDER};
                border-radius: 8px;
                selection-background-color: {cls.COLOR_HIGHLIGHT};
                selection-color: {cls.COLOR_TEXT_PRIMARY};
            }}
            
            QTableWidget::item {{
                color: {cls.COLOR_TEXT_PRIMARY};
                padding: 10px 8px;
                border-bottom: 1px solid {cls.COLOR_SURFACE_LIGHT};
            }}
            
            QTableWidget::item:hover {{
                background-color: {cls.COLOR_SURFACE_LIGHT};
            }}
            
            QTableWidget::item:selected {{
                background-color: {cls.COLOR_HIGHLIGHT};
                border-left: 3px solid {cls.COLOR_ACCENT};
            }}
            
            QHeaderView::section {{
                background-color: {cls.COLOR_SURFACE_LIGHT};
                color: {cls.COLOR_TEXT_PRIMARY};
                padding: 8px;
                border: none;
                border-bottom: 2px solid {cls.COLOR_ACCENT};
                font-weight: 600;
                font-size: 13px;
            }}
            
            /* Lists */
            QListWidget {{
                background-color: {cls.COLOR_SURFACE};
                border: 1px solid {cls.COLOR_BORDER};
                border-radius: 8px;
                padding: 6px;
            }}
            
            QListWidget::item {{
                padding: 10px 12px;
                border-radius: 6px;
                margin: 2px 0;
            }}
            
            QListWidget::item:hover {{
                background-color: {cls.COLOR_SURFACE_LIGHT};
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
                width: 8px;
                margin: 4px 2px;
            }}
            QScrollBar::handle:vertical {{
                background: {cls.COLOR_BORDER};
                min-height: 30px;
                border-radius: 4px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {cls.COLOR_BORDER_LIGHT};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            
            /* Horizontal Scrollbar */
            QScrollBar:horizontal {{
                border: none;
                background: {cls.COLOR_BACKGROUND};
                height: 8px;
                margin: 2px 4px;
            }}
            QScrollBar::handle:horizontal {{
                background: {cls.COLOR_BORDER};
                min-width: 30px;
                border-radius: 4px;
            }}
            QScrollBar::handle:horizontal:hover {{
                background: {cls.COLOR_BORDER_LIGHT};
            }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
                width: 0px;
            }}
            
            /* Tooltips */
            QToolTip {{
                background-color: {cls.COLOR_SURFACE_LIGHT};
                color: {cls.COLOR_TEXT_PRIMARY};
                border: 1px solid {cls.COLOR_BORDER};
                border-radius: 4px;
                padding: 6px 10px;
                font-size: 13px;
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
                border-radius: 6px;
                padding: 8px 14px;
                font-size: 15px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: {cls.COLOR_SURFACE_CARD};
                border: 1px solid {cls.COLOR_BORDER_LIGHT};
            }}
            QPushButton:pressed {{
                background-color: {cls.COLOR_ACCENT_SUBTLE};
                border: 1px solid {cls.COLOR_ACCENT};
            }}
        """

    @classmethod
    def get_export_button_style(cls):
        return f"""
            QPushButton {{
                background-color: #2D5A27; /* Dark Green */
                color: white;
                border: 1px solid {cls.COLOR_BORDER};
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
        return f"""
            QPushButton {{
                background-color: {cls.COLOR_ACCENT};
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 6px;
                font-weight: 600;
                font-size: 14px;
            }}
            QPushButton:hover {{
                background-color: {cls.COLOR_ACCENT_HOVER};
            }}
            QPushButton:pressed {{
                background-color: {cls.COLOR_ACCENT};
                padding: 11px 20px 9px 20px;
            }}
            QPushButton:disabled {{
                background-color: {cls.COLOR_SURFACE_LIGHT};
                color: {cls.COLOR_TEXT_MUTED};
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
                border-radius: 10px;
                padding: 12px 16px;
                text-align: left;
                font-size: 14px;
                font-weight: 500;
                color: {cls.COLOR_TEXT_SECONDARY};
            }}
            QPushButton:hover {{
                background-color: {cls.COLOR_SURFACE_LIGHT};
                color: {cls.COLOR_TEXT_PRIMARY};
            }}
            QPushButton:checked {{
                background-color: {cls.COLOR_ACCENT};
                color: white;
                font-weight: 600;
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

    # ============== Consolidated Style Helpers ==============
    
    @classmethod
    def get_input_style(cls):
        """Standard input field style for QLineEdit."""
        return f"""
            padding: 10px;
            border: 1px solid {cls.COLOR_BORDER};
            border-radius: 4px;
            background-color: {cls.COLOR_SURFACE_LIGHT};
            color: {cls.COLOR_TEXT_PRIMARY};
        """
    
    @classmethod
    def get_label_style(cls, size=14, color=None, bold=False):
        """Standard label style with configurable size and color."""
        if color is None:
            color = cls.COLOR_TEXT_PRIMARY
        weight = "bold" if bold else "normal"
        return f"font-size: {size}px; color: {color}; font-weight: {weight};"
    
    @classmethod
    def get_secondary_label_style(cls, size=13):
        """Secondary/muted label style with transparent background."""
        return f"""
            font-size: {size}px; 
            color: {cls.COLOR_TEXT_SECONDARY}; 
            background-color: transparent;
            border: none;
            padding: 4px 0px;
        """
    
    @classmethod
    def get_frame_style(cls, border_radius=12, hover_accent=True):
        """Card/frame style with optional hover effect."""
        hover_style = f"""
            QFrame:hover {{
                border: 1px solid {cls.COLOR_ACCENT};
            }}
        """ if hover_accent else ""
        
        return f"""
            QFrame {{
                background-color: {cls.COLOR_SURFACE};
                border: 1px solid {cls.COLOR_BORDER};
                border-radius: {border_radius}px;
            }}
            {hover_style}
        """
    
    @classmethod
    def get_card_style(cls, border_radius=12):
        """Dashboard card style with hover effect."""
        return f"""
            QFrame {{
                background-color: {cls.COLOR_SURFACE};
                border: 1px solid {cls.COLOR_BORDER};
                border-radius: {border_radius}px;
            }}
            QFrame:hover {{
                border: 1px solid {cls.COLOR_ACCENT};
                background-color: {cls.COLOR_SURFACE_LIGHT};
            }}
        """
    
    @classmethod
    def get_combobox_style(cls):
        """Standard combobox/dropdown style."""
        return f"""
            QComboBox {{
                padding: 8px 12px;
                border: 1px solid {cls.COLOR_BORDER};
                border-radius: 6px;
                background-color: {cls.COLOR_SURFACE_LIGHT};
                color: {cls.COLOR_TEXT_PRIMARY};
                min-width: 150px;
            }}
            QComboBox:hover {{
                border: 1px solid {cls.COLOR_ACCENT};
            }}
            QComboBox::drop-down {{
                border: none;
                padding-right: 10px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {cls.COLOR_SURFACE};
                color: {cls.COLOR_TEXT_PRIMARY};
                selection-background-color: {cls.COLOR_ACCENT};
                selection-color: white;
                border: 1px solid {cls.COLOR_BORDER};
            }}
        """
    
    @classmethod
    def get_group_box_style(cls):
        """Standard QGroupBox style for settings sections."""
        return f"""
            QGroupBox {{
                font-size: 16px;
                font-weight: bold;
                color: {cls.COLOR_TEXT_PRIMARY};
                border: 1px solid {cls.COLOR_BORDER};
                border-radius: 8px;
                margin-top: 20px;
                padding: 20px 15px 15px 15px;
                background-color: {cls.COLOR_SURFACE};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 15px;
                padding: 0 5px;
                background-color: {cls.COLOR_SURFACE};
            }}
        """
    
    @classmethod
    def get_text_edit_style(cls):
        """Standard QTextEdit style."""
        return f"""
            QTextEdit {{
                background-color: {cls.COLOR_SURFACE_LIGHT};
                border: 1px solid {cls.COLOR_BORDER};
                border-radius: 8px;
                padding: 10px;
                color: {cls.COLOR_TEXT_PRIMARY};
            }}
        """
    
    @classmethod
    def get_progress_bar_style(cls):
        """Standard progress bar style."""
        return f"""
            QProgressBar {{
                border: 2px solid {cls.COLOR_BORDER};
                border-radius: 5px;
                background-color: {cls.COLOR_SURFACE};
            }}
            QProgressBar::chunk {{
                background-color: {cls.COLOR_ACCENT};
            }}
        """
    
    @classmethod
    def get_transparent_label_style(cls):
        """Label with transparent background (for use in styled frames)."""
        return "border: none; background: transparent;"