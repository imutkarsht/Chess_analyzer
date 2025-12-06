from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
                             QLineEdit, QFileDialog, QGroupBox, QFormLayout, QMessageBox)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from .styles import Styles
from ..utils.config import ConfigManager
import os

class SettingsView(QWidget):
    engine_path_changed = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.config_manager = ConfigManager()
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(40, 40, 40, 40)
        self.layout.setSpacing(30)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        # Header
        header = QLabel("Settings")
        header.setStyleSheet(f"font-size: 28px; font-weight: bold; color: {Styles.COLOR_TEXT_PRIMARY};")
        self.layout.addWidget(header)
        
        # Engine Settings
        self.engine_group = QGroupBox("Chess Engine")
        self.engine_group.setStyleSheet(f"QGroupBox {{ font-weight: bold; font-size: 16px; color: {Styles.COLOR_ACCENT}; border: 1px solid {Styles.COLOR_BORDER}; margin-top: 10px; }} QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 5px; }}")
        engine_layout = QVBoxLayout(self.engine_group)
        
        path_layout = QHBoxLayout()
        self.path_input = QLineEdit()
        self.path_input.setText(self.config_manager.get("engine_path", ""))
        self.path_input.setPlaceholderText("Path to Stockfish executable...")
        self.path_input.setStyleSheet(f"padding: 8px; border: 1px solid {Styles.COLOR_BORDER}; border-radius: 4px; background-color: {Styles.COLOR_SURFACE_LIGHT}; color: {Styles.COLOR_TEXT_PRIMARY};")
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
        
        self.layout.addWidget(self.engine_group)
        
        # API Settings
        self.api_group = QGroupBox("API Configuration")
        self.api_group.setStyleSheet(f"QGroupBox {{ font-weight: bold; font-size: 16px; color: {Styles.COLOR_ACCENT}; border: 1px solid {Styles.COLOR_BORDER}; margin-top: 10px; }} QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 5px; }}")
        api_layout = QFormLayout(self.api_group)
        api_layout.setSpacing(15)
        
        self.gemini_input = QLineEdit()
        self.gemini_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.gemini_input.setText(self.config_manager.get("gemini_api_key", ""))
        self.gemini_input.setStyleSheet(f"padding: 8px; border: 1px solid {Styles.COLOR_BORDER}; border-radius: 4px; background-color: {Styles.COLOR_SURFACE_LIGHT}; color: {Styles.COLOR_TEXT_PRIMARY};")
        
        self.lichess_token_input = QLineEdit()
        self.lichess_token_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.lichess_token_input.setText(self.config_manager.get("lichess_token", ""))
        self.lichess_token_input.setStyleSheet(f"padding: 8px; border: 1px solid {Styles.COLOR_BORDER}; border-radius: 4px; background-color: {Styles.COLOR_SURFACE_LIGHT}; color: {Styles.COLOR_TEXT_PRIMARY};")

        lbl = QLabel("Gemini API Key:")
        lbl.setStyleSheet(f"font-size: 14px; color: {Styles.COLOR_TEXT_PRIMARY};")
        
        lbl_lichess = QLabel("Lichess API Token:")
        lbl_lichess.setStyleSheet(f"font-size: 14px; color: {Styles.COLOR_TEXT_PRIMARY};")
        
        api_layout.addRow(lbl, self.gemini_input)
        api_layout.addRow(lbl_lichess, self.lichess_token_input)
        
        self.save_api_btn = QPushButton("Save API Key")
        self.save_api_btn.setStyleSheet(Styles.get_button_style())
        self.save_api_btn.clicked.connect(self.save_api_key)
        
        # Add a wrapper layout for the button to align right
        btn_wrapper = QHBoxLayout()
        btn_wrapper.addStretch()
        btn_wrapper.addWidget(self.save_api_btn)
        api_layout.addRow(btn_wrapper)
        
        self.layout.addWidget(self.api_group)

        # Username Settings
        self.username_group = QGroupBox("Player Usernames")
        self.username_group.setStyleSheet(f"QGroupBox {{ font-weight: bold; font-size: 16px; color: {Styles.COLOR_ACCENT}; border: 1px solid {Styles.COLOR_BORDER}; margin-top: 10px; }} QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 5px; }}")
        username_layout = QFormLayout(self.username_group)
        username_layout.setSpacing(15)

        self.chesscom_input = QLineEdit()
        self.chesscom_input.setText(self.config_manager.get("chesscom_username", ""))
        self.chesscom_input.setPlaceholderText("Chess.com Username")
        self.chesscom_input.setStyleSheet(f"padding: 8px; border: 1px solid {Styles.COLOR_BORDER}; border-radius: 4px; background-color: {Styles.COLOR_SURFACE_LIGHT}; color: {Styles.COLOR_TEXT_PRIMARY};")
        
        self.lichess_input = QLineEdit()
        self.lichess_input.setText(self.config_manager.get("lichess_username", ""))
        self.lichess_input.setPlaceholderText("Lichess.org Username")
        self.lichess_input.setStyleSheet(f"padding: 8px; border: 1px solid {Styles.COLOR_BORDER}; border-radius: 4px; background-color: {Styles.COLOR_SURFACE_LIGHT}; color: {Styles.COLOR_TEXT_PRIMARY};")

        lbl_chesscom = QLabel("Chess.com:")
        lbl_chesscom.setStyleSheet(f"font-size: 14px; color: {Styles.COLOR_TEXT_PRIMARY};")
        
        lbl_lichess = QLabel("Lichess.org:")
        lbl_lichess.setStyleSheet(f"font-size: 14px; color: {Styles.COLOR_TEXT_PRIMARY};")

        username_layout.addRow(lbl_chesscom, self.chesscom_input)
        username_layout.addRow(lbl_lichess, self.lichess_input)

        self.save_usernames_btn = QPushButton("Save Usernames")
        self.save_usernames_btn.setStyleSheet(Styles.get_button_style())
        self.save_usernames_btn.clicked.connect(self.save_usernames)

        # Wrapper for button
        btn_wrapper_user = QHBoxLayout()
        btn_wrapper_user.addStretch()
        btn_wrapper_user.addWidget(self.save_usernames_btn)
        username_layout.addRow(btn_wrapper_user)

        self.layout.addWidget(self.username_group)
        
        # Appearance Settings
        self.appearance_group = QGroupBox("Appearance")
        self.appearance_group.setStyleSheet(f"QGroupBox {{ font-weight: bold; font-size: 16px; color: {Styles.COLOR_ACCENT}; border: 1px solid {Styles.COLOR_BORDER}; margin-top: 10px; }} QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 5px; }}")
        appearance_layout = QVBoxLayout(self.appearance_group)
        
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
        
        self.layout.addWidget(self.appearance_group)
        
        # Data Management
        self.data_group = QGroupBox("Data Management")
        self.data_group.setStyleSheet(f"QGroupBox {{ font-weight: bold; font-size: 16px; color: {Styles.COLOR_ACCENT}; border: 1px solid {Styles.COLOR_BORDER}; margin-top: 10px; }} QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 5px; }}")
        data_layout = QHBoxLayout(self.data_group)
        
        self.clear_cache_btn = QPushButton("Clear Analysis Cache")
        self.clear_cache_btn.setStyleSheet(Styles.get_control_button_style())
        self.clear_cache_btn.clicked.connect(self.clear_cache)
        data_layout.addWidget(self.clear_cache_btn)
        
        self.clear_data_btn = QPushButton("Clear All Data")
        self.clear_data_btn.setStyleSheet(Styles.get_control_button_style())
        self.clear_data_btn.clicked.connect(self.clear_all_data)
        data_layout.addWidget(self.clear_data_btn)
        
        self.layout.addWidget(self.data_group)
        
        self.layout.addStretch()

    def refresh_styles(self):
        """Re-applies styles to all widgets."""
        group_style = f"QGroupBox {{ font-weight: bold; font-size: 16px; color: {Styles.COLOR_ACCENT}; border: 1px solid {Styles.COLOR_BORDER}; margin-top: 10px; }} QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 5px; }}"
        self.engine_group.setStyleSheet(group_style)
        self.api_group.setStyleSheet(group_style)
        self.username_group.setStyleSheet(group_style)
        self.appearance_group.setStyleSheet(group_style)
        self.data_group.setStyleSheet(group_style)
        
        self.browse_btn.setStyleSheet(Styles.get_control_button_style())
        self.save_engine_btn.setStyleSheet(Styles.get_button_style())
        self.save_api_btn.setStyleSheet(Styles.get_button_style())
        self.save_usernames_btn.setStyleSheet(Styles.get_button_style())
        self.color_btn.setStyleSheet(Styles.get_control_button_style())
        self.clear_cache_btn.setStyleSheet(Styles.get_control_button_style())
        self.clear_data_btn.setStyleSheet(Styles.get_control_button_style())

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
