import os
import sys
import subprocess
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QProgressBar, QApplication,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPixmap, QFont

from src.utils.logger import logger
from src.utils.path_utils import get_resource_path
from src.backend.analysis.engine import resolve_engine_path
from src.backend.engine.downloader import (
    get_official_releases,
    get_expected_asset_name,
    get_download_url,
    download_and_extract,
)
from src.gui.styles import Styles

PAGE_BG = f"background-color: {Styles.COLOR_BACKGROUND};"


def build_gatekeeper_page(wizard) -> QWidget:
    page = QWidget()
    page.setStyleSheet(PAGE_BG)
    layout = QVBoxLayout(page)
    layout.setContentsMargins(60, 60, 60, 40)
    layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

    wizard.gatekeeper_label = QLabel()
    wizard.gatekeeper_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    wizard.gatekeeper_label.setStyleSheet("font-size: 18px; background: transparent;")
    layout.addWidget(wizard.gatekeeper_label)

    wizard.gatekeeper_detail = QLabel()
    wizard.gatekeeper_detail.setAlignment(Qt.AlignmentFlag.AlignCenter)
    wizard.gatekeeper_detail.setStyleSheet(
        f"font-size: 13px; color: {Styles.COLOR_TEXT_SECONDARY}; margin-top: 12px; background: transparent;"
    )
    layout.addWidget(wizard.gatekeeper_detail)

    wizard.gatekeeper_timer = QTimer(wizard)
    wizard.gatekeeper_timer.setSingleShot(True)
    wizard.gatekeeper_timer.timeout.connect(lambda: wizard._show_page(1))
    return page


def build_welcome_page(wizard) -> QWidget:
    page = QWidget()
    page.setStyleSheet(PAGE_BG)
    layout = QVBoxLayout(page)
    layout.setContentsMargins(60, 40, 60, 40)
    layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.setSpacing(16)

    logo_path = get_resource_path(os.path.join("assets", "images", "logo.png"))
    if os.path.exists(logo_path):
        logo_label = QLabel()
        pixmap = QPixmap(logo_path).scaled(
            100, 100,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        logo_label.setPixmap(pixmap)
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_label.setStyleSheet("background: transparent; border: none;")
        layout.addWidget(logo_label)

    title = QLabel("Chess Analyzer Pro")
    title.setAlignment(Qt.AlignmentFlag.AlignCenter)
    title.setFont(QFont("", 20, QFont.Weight.Bold))
    title.setStyleSheet("background: transparent;")
    layout.addWidget(title)

    subtitle = QLabel(
        "Analyze your games, find your weaknesses, and improve faster.\n"
        "Let's get you set up in 2 minutes."
    )
    subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
    subtitle.setWordWrap(True)
    subtitle.setStyleSheet(
        f"font-size: 14px; color: {Styles.COLOR_TEXT_SECONDARY}; background: transparent;"
    )
    layout.addWidget(subtitle)

    layout.addStretch()

    get_started = QPushButton("Get Started")
    get_started.setStyleSheet(f"""
        QPushButton {{
            background-color: {Styles.COLOR_ACCENT};
            color: white;
            border: none;
            border-radius: 8px;
            padding: 12px 40px;
            font-size: 15px;
            font-weight: bold;
        }}
        QPushButton:hover {{ background-color: {Styles.COLOR_ACCENT_HOVER}; }}
    """)
    get_started.clicked.connect(lambda: wizard._go_to(2))
    layout.addWidget(get_started, alignment=Qt.AlignmentFlag.AlignCenter)

    return page


def build_profile_page(wizard) -> QWidget:
    page = QWidget()
    page.setStyleSheet(PAGE_BG)
    layout = QVBoxLayout(page)
    layout.setContentsMargins(60, 40, 60, 40)
    layout.setSpacing(6)

    heading = QLabel("Link your accounts")
    heading.setFont(QFont("", 16, QFont.Weight.Bold))
    heading.setStyleSheet("background: transparent;")
    layout.addWidget(heading)

    helper = QLabel(
        "Optional. Connect accounts to auto-fetch your games right inside the app."
    )
    helper.setWordWrap(True)
    helper.setStyleSheet(
        f"font-size: 13px; color: {Styles.COLOR_TEXT_SECONDARY}; margin-bottom: 12px; background: transparent;"
    )
    layout.addWidget(helper)

    lbl = QLabel("Chess.com username")
    lbl.setStyleSheet("background: transparent;")
    layout.addWidget(lbl)
    wizard.chesscom_input = QLineEdit()
    wizard.chesscom_input.setPlaceholderText("e.g. magnuscarlsen")
    wizard.chesscom_input.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    layout.addWidget(wizard.chesscom_input)
    hint = QLabel("Shows your Chess.com games for quick loading")
    hint.setStyleSheet(
        f"font-size: 12px; color: {Styles.COLOR_TEXT_MUTED}; background: transparent;"
    )
    layout.addWidget(hint)

    lbl = QLabel("Lichess username")
    lbl.setStyleSheet("background: transparent;")
    layout.addWidget(lbl)
    wizard.lichess_input = QLineEdit()
    wizard.lichess_input.setPlaceholderText("e.g. drnykterstein")
    wizard.lichess_input.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    layout.addWidget(wizard.lichess_input)
    hint = QLabel("Shows your Lichess games for quick loading")
    hint.setStyleSheet(
        f"font-size: 12px; color: {Styles.COLOR_TEXT_MUTED}; background: transparent;"
    )
    layout.addWidget(hint)

    lbl = QLabel("Lichess API token (optional)")
    lbl.setStyleSheet("background: transparent; margin-top: 8px;")
    layout.addWidget(lbl)
    wizard.lichess_token_input = QLineEdit()
    wizard.lichess_token_input.setPlaceholderText("lip_...")
    wizard.lichess_token_input.setEchoMode(QLineEdit.EchoMode.Password)
    wizard.lichess_token_input.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    layout.addWidget(wizard.lichess_token_input)
    hint = QLabel(
        "Get one at lichess.org/account/oauth/token. Required to fetch your games."
    )
    hint.setStyleSheet(
        f"font-size: 12px; color: {Styles.COLOR_TEXT_MUTED}; background: transparent;"
    )
    layout.addWidget(hint)

    layout.addStretch()
    page._on_show = lambda: wizard.chesscom_input.setFocus()
    return page


def build_stockfish_page(wizard) -> QWidget:
    page = QWidget()
    page.setStyleSheet(PAGE_BG)
    layout = QVBoxLayout(page)
    layout.setContentsMargins(60, 40, 60, 40)
    layout.setSpacing(12)

    heading = QLabel("Chess Engine")
    heading.setFont(QFont("", 16, QFont.Weight.Bold))
    heading.setStyleSheet("background: transparent;")
    layout.addWidget(heading)

    helper = QLabel(
        "Stockfish powers all analysis. We will find or download it for you."
    )
    helper.setWordWrap(True)
    helper.setStyleSheet(
        f"font-size: 13px; color: {Styles.COLOR_TEXT_SECONDARY}; margin-bottom: 8px; background: transparent;"
    )
    layout.addWidget(helper)

    wizard.sf_status = QLabel("")
    wizard.sf_status.setWordWrap(True)
    wizard.sf_status.setStyleSheet("font-size: 14px; background: transparent;")
    layout.addWidget(wizard.sf_status)

    wizard.sf_download_btn = QPushButton("Download Stockfish")
    wizard.sf_download_btn.setStyleSheet(f"""
        QPushButton {{
            background-color: {Styles.COLOR_ACCENT};
            color: white;
            border: none;
            border-radius: 8px;
            padding: 10px 24px;
            font-size: 14px;
            font-weight: bold;
        }}
        QPushButton:hover {{ background-color: {Styles.COLOR_ACCENT_HOVER}; }}
    """)
    wizard.sf_download_btn.clicked.connect(wizard._download_stockfish)
    wizard.sf_download_btn.setVisible(False)
    layout.addWidget(wizard.sf_download_btn)

    wizard.sf_progress = QProgressBar()
    wizard.sf_progress.setStyleSheet(Styles.get_progress_bar_style())
    wizard.sf_progress.setVisible(False)
    layout.addWidget(wizard.sf_progress)

    layout.addStretch()
    page._on_show = wizard._detect_stockfish
    return page


def build_llm_page(wizard) -> QWidget:
    page = QWidget()
    page.setStyleSheet(PAGE_BG)
    layout = QVBoxLayout(page)
    layout.setContentsMargins(60, 40, 60, 40)
    layout.setSpacing(6)

    heading = QLabel("AI Coach (optional)")
    heading.setFont(QFont("", 16, QFont.Weight.Bold))
    heading.setStyleSheet("background: transparent;")
    layout.addWidget(heading)

    helper = QLabel(
        "Connect Groq for AI-powered game summaries and personalized coaching tips."
    )
    helper.setWordWrap(True)
    helper.setStyleSheet(
        f"font-size: 13px; color: {Styles.COLOR_TEXT_SECONDARY}; margin-bottom: 16px; background: transparent;"
    )
    layout.addWidget(helper)

    provider_row = QHBoxLayout()
    lbl = QLabel("Provider:")
    lbl.setStyleSheet("background: transparent;")
    provider_row.addWidget(lbl)
    provider_label = QLabel("Groq")
    provider_label.setStyleSheet(
        f"font-size: 14px; font-weight: bold; color: {Styles.COLOR_ACCENT}; background: transparent;"
    )
    provider_row.addWidget(provider_label)
    provider_row.addStretch()
    layout.addLayout(provider_row)

    lbl = QLabel("API Key")
    lbl.setStyleSheet("background: transparent;")
    layout.addWidget(lbl)
    wizard.llm_key_input = QLineEdit()
    wizard.llm_key_input.setPlaceholderText("gsk_...")
    wizard.llm_key_input.setEchoMode(QLineEdit.EchoMode.Password)
    layout.addWidget(wizard.llm_key_input)

    key_hint = QLabel("Get a free key at console.groq.com")
    key_hint.setStyleSheet(
        f"font-size: 12px; color: {Styles.COLOR_TEXT_MUTED}; background: transparent;"
    )
    layout.addWidget(key_hint)

    wizard.llm_test_btn = QPushButton("Test Connection")
    wizard.llm_test_btn.setStyleSheet(Styles.get_control_button_style())
    wizard.llm_test_btn.clicked.connect(wizard._test_llm)
    layout.addWidget(wizard.llm_test_btn)

    wizard.llm_test_result = QLabel("")
    wizard.llm_test_result.setStyleSheet(
        "font-size: 13px; margin-top: 4px; background: transparent;"
    )
    layout.addWidget(wizard.llm_test_result)

    layout.addStretch()
    return page


def build_done_page(wizard) -> QWidget:
    page = QWidget()
    page.setStyleSheet(PAGE_BG)
    layout = QVBoxLayout(page)
    layout.setContentsMargins(60, 40, 60, 40)
    layout.setSpacing(8)

    heading = QLabel("You're all set!")
    heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
    heading.setFont(QFont("", 20, QFont.Weight.Bold))
    heading.setStyleSheet("background: transparent;")
    layout.addWidget(heading)

    wizard.summary_label = QLabel("")
    wizard.summary_label.setWordWrap(True)
    wizard.summary_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    wizard.summary_label.setStyleSheet(
        f"font-size: 14px; color: {Styles.COLOR_TEXT_SECONDARY}; margin: 16px 0; background: transparent;"
    )
    layout.addWidget(wizard.summary_label)

    ready = QLabel("Ready to analyze your games!")
    ready.setAlignment(Qt.AlignmentFlag.AlignCenter)
    ready.setStyleSheet(
        f"font-size: 15px; color: {Styles.COLOR_ACCENT}; font-weight: bold; background: transparent;"
    )
    layout.addWidget(ready)

    layout.addStretch()

    wizard.done_btn = QPushButton("Finish")
    wizard.done_btn.setStyleSheet(f"""
        QPushButton {{
            background-color: {Styles.COLOR_ACCENT};
            color: white;
            border: none;
            border-radius: 8px;
            padding: 12px 40px;
            font-size: 15px;
            font-weight: bold;
        }}
        QPushButton:hover {{ background-color: {Styles.COLOR_ACCENT_HOVER}; }}
    """)
    wizard.done_btn.clicked.connect(wizard._on_finish)
    layout.addWidget(wizard.done_btn, alignment=Qt.AlignmentFlag.AlignCenter)

    return page
