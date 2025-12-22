
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
                background-color: #2D4059; /* Dark Blue */
                color: white;
                border: 1px solid {cls.COLOR_BORDER};
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 14px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #3A5375;
            }}
            QPushButton:pressed {{
                background-color: #1F2D3F;
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
    def get_secondary_label_style(cls, size=12):
        """Secondary/muted label style."""
        return f"font-size: {size}px; color: {cls.COLOR_TEXT_SECONDARY};"
    
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