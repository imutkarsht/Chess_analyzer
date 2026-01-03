"""
Update Notification Dialog - Shows when a new version is available.
"""
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QTextEdit, QFrame, QWidget)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtCore import QUrl
from ..styles import Styles
import re

try:
    import qtawesome as qta
    HAS_QTAWESOME = True
except ImportError:
    HAS_QTAWESOME = False


class UpdateNotificationDialog(QDialog):
    """Dialog to notify user of available update."""
    
    def __init__(self, update_info, parent=None):
        super().__init__(parent)
        self.update_info = update_info
        self.setWindowTitle("Update Available")
        self.setFixedSize(480, 380)
        self.setStyleSheet(f"QDialog {{ background-color: {Styles.COLOR_BACKGROUND}; }}")
        
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Header section with accent background
        header_widget = QWidget()
        header_widget.setStyleSheet(f"""
            QWidget {{
                background-color: {Styles.COLOR_SURFACE};
                border-bottom: 1px solid {Styles.COLOR_BORDER};
            }}
        """)
        header_layout = QVBoxLayout(header_widget)
        header_layout.setContentsMargins(24, 20, 24, 20)
        header_layout.setSpacing(12)
        
        # Title row
        title_row = QHBoxLayout()
        title_row.setSpacing(10)
        
        if HAS_QTAWESOME:
            icon_label = QLabel()
            icon_label.setPixmap(qta.icon('fa5s.arrow-circle-up', color=Styles.COLOR_ACCENT).pixmap(28, 28))
            title_row.addWidget(icon_label)
        
        title = QLabel("Update Available")
        title.setStyleSheet(f"""
            font-size: 18px;
            font-weight: bold;
            color: {Styles.COLOR_TEXT_PRIMARY};
        """)
        title_row.addWidget(title)
        title_row.addStretch()
        header_layout.addLayout(title_row)
        
        # Version badges
        version_row = QHBoxLayout()
        version_row.setSpacing(12)
        
        current_badge = self._create_version_badge(f"v{self.update_info.current}", "Current", Styles.COLOR_TEXT_MUTED)
        version_row.addWidget(current_badge)
        
        # Arrow
        if HAS_QTAWESOME:
            arrow = QLabel()
            arrow.setPixmap(qta.icon('fa5s.arrow-right', color=Styles.COLOR_TEXT_MUTED).pixmap(16, 16))
            version_row.addWidget(arrow)
        else:
            arrow = QLabel("→")
            arrow.setStyleSheet(f"color: {Styles.COLOR_TEXT_MUTED};")
            version_row.addWidget(arrow)
        
        latest_badge = self._create_version_badge(f"v{self.update_info.latest}", "Latest", Styles.COLOR_ACCENT)
        version_row.addWidget(latest_badge)
        
        version_row.addStretch()
        header_layout.addLayout(version_row)
        
        layout.addWidget(header_widget)
        
        # Content section
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(24, 16, 24, 16)
        content_layout.setSpacing(12)
        
        # Changelog
        if self.update_info.changelog:
            changelog_label = QLabel("What's New")
            changelog_label.setStyleSheet(f"""
                color: {Styles.COLOR_TEXT_PRIMARY};
                font-size: 13px;
                font-weight: 600;
            """)
            content_layout.addWidget(changelog_label)
            
            # Convert markdown to plain text (simplified)
            changelog_clean = self._clean_markdown(self.update_info.changelog)
            
            changelog_text = QTextEdit()
            changelog_text.setPlainText(changelog_clean[:600] + ("..." if len(changelog_clean) > 600 else ""))
            changelog_text.setReadOnly(True)
            changelog_text.setStyleSheet(f"""
                QTextEdit {{
                    background-color: {Styles.COLOR_SURFACE_LIGHT};
                    color: {Styles.COLOR_TEXT_SECONDARY};
                    border: 1px solid {Styles.COLOR_BORDER};
                    border-radius: 6px;
                    padding: 10px;
                    font-size: 12px;
                    line-height: 1.4;
                }}
            """)
            content_layout.addWidget(changelog_text)
        
        layout.addWidget(content_widget, 1)
        
        # Button section
        btn_widget = QWidget()
        btn_widget.setStyleSheet(f"""
            QWidget {{
                background-color: {Styles.COLOR_SURFACE};
                border-top: 1px solid {Styles.COLOR_BORDER};
            }}
        """)
        btn_layout = QHBoxLayout(btn_widget)
        btn_layout.setContentsMargins(24, 16, 24, 16)
        btn_layout.setSpacing(12)
        
        # Remind Later button
        btn_later = QPushButton("  Remind Later")
        if HAS_QTAWESOME:
            btn_later.setIcon(qta.icon('fa5s.clock', color=Styles.COLOR_TEXT_SECONDARY))
        btn_later.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {Styles.COLOR_TEXT_SECONDARY};
                border: 1px solid {Styles.COLOR_BORDER};
                padding: 10px 18px;
                border-radius: 6px;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: {Styles.COLOR_SURFACE_LIGHT};
                color: {Styles.COLOR_TEXT_PRIMARY};
            }}
        """)
        btn_later.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_later.clicked.connect(self.reject)
        btn_layout.addWidget(btn_later)
        
        btn_layout.addStretch()
        
        # Download button
        btn_download = QPushButton("  Download Update")
        if HAS_QTAWESOME:
            btn_download.setIcon(qta.icon('fa5s.download', color="#ffffff"))
        btn_download.setStyleSheet(f"""
            QPushButton {{
                background-color: {Styles.COLOR_ACCENT};
                color: white;
                border: none;
                padding: 10px 22px;
                border-radius: 6px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {Styles.COLOR_ACCENT_HOVER};
            }}
        """)
        btn_download.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_download.clicked.connect(self.open_download)
        btn_layout.addWidget(btn_download)
        
        layout.addWidget(btn_widget)
    
    def _create_version_badge(self, version, label, color):
        """Create a version badge widget."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        
        label_text = QLabel(label)
        label_text.setStyleSheet(f"""
            color: {Styles.COLOR_TEXT_MUTED};
            font-size: 10px;
            text-transform: uppercase;
            letter-spacing: 1px;
        """)
        layout.addWidget(label_text)
        
        version_text = QLabel(version)
        version_text.setStyleSheet(f"""
            color: {color};
            font-size: 16px;
            font-weight: bold;
        """)
        layout.addWidget(version_text)
        
        return widget
    
    def _clean_markdown(self, text):
        """Convert markdown to cleaner plain text."""
        # Remove bold/italic markers
        text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
        text = re.sub(r'\*(.+?)\*', r'\1', text)
        # Convert headers to simple text with newlines
        text = re.sub(r'^###\s+(.+)$', r'\n\1:', text, flags=re.MULTILINE)
        text = re.sub(r'^##\s+(.+)$', r'\n\1:', text, flags=re.MULTILINE)
        text = re.sub(r'^#\s+(.+)$', r'\n\1:', text, flags=re.MULTILINE)
        # Convert list items
        text = re.sub(r'^\*\s+', '• ', text, flags=re.MULTILINE)
        text = re.sub(r'^-\s+', '• ', text, flags=re.MULTILINE)
        # Clean extra whitespace
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()
    
    def open_download(self):
        """Open the download URL in browser."""
        url = self.update_info.download_url or self.update_info.html_url
        if url:
            QDesktopServices.openUrl(QUrl(url))
        self.accept()
