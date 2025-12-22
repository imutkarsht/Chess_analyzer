from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
                             QLineEdit, QFileDialog, QGroupBox, QFormLayout, QMessageBox,
                             QScrollArea, QFrame, QComboBox, QGridLayout)
from PyQt6.QtGui import QColor, QDesktopServices
from PyQt6.QtCore import Qt, pyqtSignal, QUrl
from .styles import Styles
from ..utils.config import ConfigManager
import os

class SettingsView(QWidget):
    engine_path_changed = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.config_manager = ConfigManager()
        
        # Main layout for the widget itself (contains scroll area)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Scroll Area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setStyleSheet(f"background-color: {Styles.COLOR_BACKGROUND}; border: none;")
        
        # Container for content inside scroll area
        self.content_container = QWidget()
        self.content_container.setStyleSheet(f"background-color: {Styles.COLOR_BACKGROUND};")
        
        # Use Grid Layout for 2-column design
        self.container_layout = QGridLayout(self.content_container)
        self.container_layout.setContentsMargins(40, 40, 40, 40)
        self.container_layout.setSpacing(25)
        self.container_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        self.scroll_area.setWidget(self.content_container)
        main_layout.addWidget(self.scroll_area)
        
        # Use centralized group box style
        self.group_style = Styles.get_group_box_style()

        # --- LEFT COLUMN (Column 0) ---

        # 1. Engine Settings
        self.engine_group = QGroupBox("Chess Engine")
        self.engine_group.setStyleSheet(self.group_style)
        engine_layout = QVBoxLayout(self.engine_group)
        engine_layout.setContentsMargins(20, 25, 20, 20)
        
        path_layout = QHBoxLayout()
        self.path_input = QLineEdit()
        self.path_input.setText(self.config_manager.get("engine_path", ""))
        self.path_input.setPlaceholderText("Path to Stockfish executable...")
        self.path_input.setStyleSheet(Styles.get_input_style())
        path_layout.addWidget(self.path_input)
        
        self.browse_btn = QPushButton("Browse")
        self.browse_btn.setStyleSheet(Styles.get_control_button_style())
        self.browse_btn.clicked.connect(self.browse_engine)
        path_layout.addWidget(self.browse_btn)
        
        engine_layout.addLayout(path_layout)
        
        self.save_engine_btn = QPushButton("Save Engine Path")
        self.save_engine_btn.setStyleSheet(Styles.get_button_style())
        self.save_engine_btn.clicked.connect(self.save_engine_path)
        engine_layout.addWidget(self.save_engine_btn, alignment=Qt.AlignmentFlag.AlignRight)
        
        self.container_layout.addWidget(self.engine_group, 0, 0)
        
        # 2. API Settings
        self.api_group = QGroupBox("API Configuration")
        self.api_group.setStyleSheet(self.group_style)
        api_layout = QFormLayout(self.api_group)
        api_layout.setContentsMargins(20, 25, 20, 20)
        api_layout.setSpacing(15)
        
        self.gemini_input = QLineEdit()
        self.gemini_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.gemini_input.setText(self.config_manager.get("gemini_api_key", ""))
        self.gemini_input.setStyleSheet(Styles.get_input_style())
        
        self.lichess_token_input = QLineEdit()
        self.lichess_token_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.lichess_token_input.setText(self.config_manager.get("lichess_token", ""))
        self.lichess_token_input.setStyleSheet(Styles.get_input_style())

        lbl = QLabel("Gemini API Key:")
        lbl.setStyleSheet(Styles.get_secondary_label_style())
        
        lbl_lichess = QLabel("Lichess API Token:")
        lbl_lichess.setStyleSheet(Styles.get_secondary_label_style())
        
        api_layout.addRow(lbl, self.gemini_input)
        api_layout.addRow(lbl_lichess, self.lichess_token_input)
        
        self.save_api_btn = QPushButton("Save API Key")
        self.save_api_btn.setStyleSheet(Styles.get_button_style())
        self.save_api_btn.clicked.connect(self.save_api_key)
        
        btn_wrapper = QHBoxLayout()
        btn_wrapper.addStretch()
        btn_wrapper.addWidget(self.save_api_btn)
        api_layout.addRow(btn_wrapper)
        
        self.container_layout.addWidget(self.api_group, 1, 0)

        # 3. Username Settings
        self.username_group = QGroupBox("Player Usernames")
        self.username_group.setStyleSheet(self.group_style)
        username_layout = QFormLayout(self.username_group)
        username_layout.setContentsMargins(20, 25, 20, 20)
        username_layout.setSpacing(15)

        self.chesscom_input = QLineEdit()
        self.chesscom_input.setText(self.config_manager.get("chesscom_username", ""))
        self.chesscom_input.setPlaceholderText("Chess.com Username")
        self.chesscom_input.setStyleSheet(Styles.get_input_style())
        
        self.lichess_input = QLineEdit()
        self.lichess_input.setText(self.config_manager.get("lichess_username", ""))
        self.lichess_input.setPlaceholderText("Lichess.org Username")
        self.lichess_input.setStyleSheet(Styles.get_input_style())

        lbl_chesscom = QLabel("Chess.com:")
        lbl_chesscom.setStyleSheet(Styles.get_secondary_label_style())
        
        lbl_lichess = QLabel("Lichess.org:")
        lbl_lichess.setStyleSheet(Styles.get_secondary_label_style())

        username_layout.addRow(lbl_chesscom, self.chesscom_input)
        username_layout.addRow(lbl_lichess, self.lichess_input)

        self.save_usernames_btn = QPushButton("Save Usernames")
        self.save_usernames_btn.setStyleSheet(Styles.get_button_style())
        self.save_usernames_btn.clicked.connect(self.save_usernames)

        btn_wrapper_user = QHBoxLayout()
        btn_wrapper_user.addStretch()
        btn_wrapper_user.addWidget(self.save_usernames_btn)
        username_layout.addRow(btn_wrapper_user)

        self.container_layout.addWidget(self.username_group, 2, 0) # Bottom of left column
        
        # --- RIGHT COLUMN (Column 1) ---
        
        # 4. Appearance Settings
        self.appearance_group = QGroupBox("Appearance")
        self.appearance_group.setStyleSheet(self.group_style)
        appearance_layout = QVBoxLayout(self.appearance_group)
        appearance_layout.setContentsMargins(20, 25, 20, 20)
        
        # Board Theme Selector (Single Instance)
        theme_layout = QHBoxLayout()
        theme_lbl = QLabel("Board Theme:")
        theme_lbl.setStyleSheet(f"font-size: 14px; color: {Styles.COLOR_TEXT_PRIMARY};")
        theme_layout.addWidget(theme_lbl)
        
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(list(Styles.BOARD_THEMES.keys()))
        current_theme = self.config_manager.get("board_theme", "Green")
        self.theme_combo.setCurrentText(current_theme)
        self.theme_combo.setStyleSheet(f"""
            QComboBox {{
                padding: 5px;
                background-color: {Styles.COLOR_SURFACE_LIGHT};
                color: {Styles.COLOR_TEXT_PRIMARY};
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 4px;
            }}
            QComboBox::drop-down {{
                border: none;
            }}
        """)
        self.theme_combo.currentTextChanged.connect(self.change_board_theme)
        theme_layout.addWidget(self.theme_combo)
        
        theme_layout.addStretch()
        appearance_layout.addLayout(theme_layout)

        # Piece Style Selector
        from .piece_themes import get_piece_theme_names
        piece_layout = QHBoxLayout()
        piece_lbl = QLabel("Piece Style:")
        piece_lbl.setStyleSheet(f"font-size: 14px; color: {Styles.COLOR_TEXT_PRIMARY};")
        piece_layout.addWidget(piece_lbl)
        
        self.piece_combo = QComboBox()
        self.piece_combo.addItems(get_piece_theme_names())
        current_piece_theme = self.config_manager.get("piece_theme", "Standard")
        self.piece_combo.setCurrentText(current_piece_theme)
        self.piece_combo.setStyleSheet(f"""
            QComboBox {{
                padding: 5px;
                background-color: {Styles.COLOR_SURFACE_LIGHT};
                color: {Styles.COLOR_TEXT_PRIMARY};
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 4px;
            }}
            QComboBox::drop-down {{
                border: none;
            }}
        """)
        self.piece_combo.currentTextChanged.connect(self.change_piece_theme)
        piece_layout.addWidget(self.piece_combo)
        
        piece_layout.addStretch()
        appearance_layout.addLayout(piece_layout)


        # Accent Color
        color_layout = QHBoxLayout()
        color_lbl = QLabel("Accent Color:")
        color_lbl.setStyleSheet(f"font-size: 14px; color: {Styles.COLOR_TEXT_PRIMARY};")
        color_layout.addWidget(color_lbl)
        
        self.color_btn = QPushButton("Change Color")
        self.color_btn.setStyleSheet(Styles.get_control_button_style())
        self.color_btn.clicked.connect(self.change_accent_color)
        color_layout.addWidget(self.color_btn)
        
        color_layout.addStretch()
        appearance_layout.addLayout(color_layout)
        
        self.container_layout.addWidget(self.appearance_group, 0, 1) # Top of right column
        
        # 5. Data Management
        self.data_group = QGroupBox("Data Management")
        self.data_group.setStyleSheet(self.group_style)
        data_layout = QGridLayout(self.data_group)
        data_layout.setContentsMargins(20, 25, 20, 20)
        
        self.clear_cache_btn = QPushButton("Clear Cache")
        self.clear_cache_btn.setStyleSheet(Styles.get_control_button_style())
        self.clear_cache_btn.clicked.connect(self.clear_cache)
        data_layout.addWidget(self.clear_cache_btn, 0, 0)
        
        self.clear_data_btn = QPushButton("Reset All Data")
        self.clear_data_btn.setStyleSheet(Styles.get_control_button_style())
        self.clear_data_btn.clicked.connect(self.clear_all_data)
        data_layout.addWidget(self.clear_data_btn, 0, 1)
        
        self.container_layout.addWidget(self.data_group, 1, 1)

        # 6. Official Website Section
        self.website_group = QGroupBox("Official Website")
        self.website_group.setStyleSheet(self.group_style)
        website_layout = QHBoxLayout(self.website_group)
        website_layout.setContentsMargins(20, 25, 20, 20)

        self.website_btn = QPushButton("Visit Website")
        self.website_btn.setStyleSheet(Styles.get_control_button_style())
        self.website_btn.clicked.connect(self.open_website)
        website_layout.addWidget(self.website_btn)

        self.feedback_btn = QPushButton("Feedback")
        self.feedback_btn.setStyleSheet(Styles.get_control_button_style())
        self.feedback_btn.clicked.connect(self.open_feedback)
        website_layout.addWidget(self.feedback_btn)

        self.container_layout.addWidget(self.website_group, 2, 1)
        
        # Column stretch
        self.container_layout.setColumnStretch(0, 1)
        self.container_layout.setColumnStretch(1, 1)

        # Add vertical spacer to push everything up if needed, though AlignTop handles it
        # self.container_layout.setRowStretch(3, 1)


    def refresh_styles(self):
        """Re-applies styles to all widgets."""
        self.group_style = f"""
            QGroupBox {{ 
                font-weight: bold; 
                font-size: 16px; 
                color: {Styles.COLOR_TEXT_PRIMARY}; 
                border: 1px solid {Styles.COLOR_BORDER}; 
                border-radius: 8px; 
                margin-top: 10px; 
                background-color: {Styles.COLOR_SURFACE};
            }} 
            QGroupBox::title {{ 
                subcontrol-origin: margin; 
                left: 15px; 
                padding: 0 5px; 
            }}
        """
        self.engine_group.setStyleSheet(self.group_style)
        self.api_group.setStyleSheet(self.group_style)
        self.username_group.setStyleSheet(self.group_style)
        self.appearance_group.setStyleSheet(self.group_style)
        self.data_group.setStyleSheet(self.group_style)
        self.website_group.setStyleSheet(self.group_style)
        
        self.browse_btn.setStyleSheet(Styles.get_control_button_style())
        self.save_engine_btn.setStyleSheet(Styles.get_button_style())
        self.save_api_btn.setStyleSheet(Styles.get_button_style())
        self.save_usernames_btn.setStyleSheet(Styles.get_button_style())
        self.color_btn.setStyleSheet(Styles.get_control_button_style())
        self.clear_cache_btn.setStyleSheet(Styles.get_control_button_style())
        self.clear_data_btn.setStyleSheet(Styles.get_control_button_style())
        self.website_btn.setStyleSheet(Styles.get_control_button_style())
        self.feedback_btn.setStyleSheet(Styles.get_control_button_style())

    def change_accent_color(self):
        from PyQt6.QtWidgets import QColorDialog
        color = QColorDialog.getColor(initial=QColor(Styles.COLOR_ACCENT), parent=self, title="Select Accent Color")
        
        if color.isValid():
            # Update Styles
            Styles.set_accent_color(color.name())
            
            # Save to config (optional, but good practice)
            self.config_manager.set("accent_color", color.name())
            
            # Trigger global refresh
            # We need to access the main window to refresh
            window = self.window()
            if hasattr(window, "refresh_theme"):
                window.refresh_theme()

    def _update_config_and_refresh(self, key, value):
        """Common helper for config updates that require theme refresh."""
        self.config_manager.set(key, value)
        window = self.window()
        if hasattr(window, "refresh_theme"):
            window.refresh_theme()

    def change_board_theme(self, theme_name):
        self._update_config_and_refresh("board_theme", theme_name)

    def change_piece_theme(self, theme_name):
        self._update_config_and_refresh("piece_theme", theme_name)

    def browse_engine(self):
        filter_str = "Executables (*.exe);;All Files (*)" if os.name == 'nt' else "All Files (*)"
        path, _ = QFileDialog.getOpenFileName(self, "Select Stockfish Binary", "", filter_str)
        if path:
            self.path_input.setText(path)

    def save_engine_path(self):
        path = self.path_input.text()
        if path:
            self.config_manager.set("engine_path", path)
            self.engine_path_changed.emit(path)
            QMessageBox.information(self, "Saved", "Engine path saved successfully.")
        else:
            QMessageBox.warning(self, "Error", "Please enter a valid path.")

    def save_api_key(self):
        key = self.gemini_input.text()
        lichess_token = self.lichess_token_input.text()
        self.config_manager.set("gemini_api_key", key)
        self.config_manager.set("lichess_token", lichess_token)
        QMessageBox.information(self, "Saved", "API Keys saved successfully.")

    def save_usernames(self):
        chesscom = self.chesscom_input.text()
        lichess = self.lichess_input.text()
        self.config_manager.set("chesscom_username", chesscom)
        self.config_manager.set("lichess_username", lichess)
        QMessageBox.information(self, "Saved", "Usernames saved successfully.")

    def clear_cache(self):
        reply = QMessageBox.question(self, "Confirm", "Are you sure you want to clear the analysis cache? This will not delete your game history.",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            from ..backend.cache import AnalysisCache
            cache = AnalysisCache()
            cache.clear_cache()
            QMessageBox.information(self, "Success", "Analysis cache cleared.")

    def clear_all_data(self):
        reply = QMessageBox.question(self, "Confirm", "Are you sure you want to clear ALL data? This includes game history and analysis cache. This action cannot be undone.",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            from ..backend.cache import AnalysisCache
            from ..backend.game_history import GameHistoryManager
            
            cache = AnalysisCache()
            cache.clear_cache()
            
            history = GameHistoryManager()
            history.clear_history()
            
            # Also clear current games list in MainWindow if possible
            window = self.window()
            if hasattr(window, "games"):
                window.games = []
                if hasattr(window, "history_view"):
                    window.history_view.load_history()
                if hasattr(window, "metrics_view"):
                    window.metrics_view.refresh([])
            
            QMessageBox.information(self, "Success", "All data cleared.")

    def open_website(self):
        QDesktopServices.openUrl(QUrl("https://chess-analyzer-ut.vercel.app/"))

    def open_feedback(self):
        QDesktopServices.openUrl(QUrl("https://chess-analyzer-ut.vercel.app/feedback"))
