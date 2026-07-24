from PyQt6.QtWidgets import QFrame, QVBoxLayout, QPushButton, QApplication
from PyQt6.QtCore import pyqtSignal, Qt, QSize, QPropertyAnimation, QEasingCurve, QTimer, pyqtProperty
from PyQt6.QtGui import QIcon
from src.gui.styles import Styles
from src.gui.theme import ThemeManager
from src.utils.path_utils import get_resource_path
import os

try:
    import qtawesome as qta
    HAS_QTAWESOME = True
except ImportError:
    HAS_QTAWESOME = False

QTAWESOME_ICONS = {
    "help.png": "fa5s.question-circle",
    "exit.png": "fa5s.sign-out-alt",
    "analyze.png": "fa5s.chess-board",
    "explorer.png": "fa5s.compass",
    "history.png": "fa5s.history",
    "stats.png": "fa5s.chart-bar",
    "settings.png": "fa5s.cog",
}

COLLAPSED_WIDTH = 60
EXPANDED_WIDTH = 200


class Sidebar(QFrame):
    page_changed = pyqtSignal(int)

    def __init__(self):
        super().__init__()
        self.setObjectName("Sidebar")
        self._collapsed = False
        self._animating = False
        self._sidebar_width = EXPANDED_WIDTH

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(6, 20, 6, 20)
        self.layout.setSpacing(6)

        nav_specs = [
            ("Analyze", "analyze.png", 0),
            ("Explorer", "explorer.png", 1),
            ("History", "history.png", 2),
            ("Stats", "stats.png", 3),
            ("Settings", "settings.png", 4),
        ]

        self._nav_buttons = []
        for text, icon_name, idx in nav_specs:
            btn = self._make_nav_button(text, icon_name, idx)
            self._nav_buttons.append(btn)
            self.layout.addWidget(btn)

        self.layout.addStretch()

        self.btn_help = self._make_nav_button("Help (F1)", "help.png", -1)
        self.btn_help.clicked.connect(self.show_help)
        self.layout.addWidget(self.btn_help)

        self.btn_collapse = QPushButton()
        self.btn_collapse.setFixedHeight(40)
        self.btn_collapse.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_collapse.clicked.connect(self.toggle_collapse)
        self.layout.addWidget(self.btn_collapse)

        self.btn_exit = self._make_nav_button("Exit", "exit.png", -1)
        self.btn_exit.clicked.connect(QApplication.instance().quit)
        self.layout.addWidget(self.btn_exit)

        self.apply_style()

        self._update_labels_and_icons()
        self.setFixedWidth(EXPANDED_WIDTH)
        self.set_active(0)

    def _get_sidebar_width(self):
        return self._sidebar_width

    def _set_sidebar_width(self, w):
        self._sidebar_width = w
        self.setFixedWidth(int(round(w)))

    sidebar_width = pyqtProperty(float, _get_sidebar_width, _set_sidebar_width)

    def _make_nav_button(self, text: str, icon_name: str, index: int) -> QPushButton:
        btn = QPushButton(text)
        btn.setFixedHeight(48)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setCheckable(index >= 0)

        if HAS_QTAWESOME and icon_name in QTAWESOME_ICONS:
            btn.setIcon(qta.icon(QTAWESOME_ICONS[icon_name], color=Styles.COLOR_TEXT_SECONDARY))
            btn.setIconSize(QSize(22, 22))
        else:
            icon_path = get_resource_path(os.path.join("assets", "icons", icon_name))
            if os.path.exists(icon_path):
                btn.setIcon(QIcon(icon_path))
                btn.setIconSize(QSize(22, 22))

        if index >= 0:
            btn.clicked.connect(lambda checked, idx=index: self.handle_click(idx))

        return btn

    def apply_style(self):
        p = ThemeManager.palette()
        self.setStyleSheet(f"""
            #Sidebar {{
                background-color: {p.surface};
                border-right: 1px solid {p.border};
            }}
            QPushButton {{
                background-color: transparent;
                border: none;
                border-radius: 8px;
                padding: 0px 12px;
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
                background-color: transparent;
                border-left: 3px solid {p.accent};
                color: {p.accent};
                font-weight: 600;
                border-radius: 0;
            }}
        """)

    def _update_labels_and_icons(self):
        nav_texts = ["Analyze", "Explorer", "History", "Stats", "Settings"]
        for btn, txt in zip(self._nav_buttons, nav_texts):
            btn.setText(f"  {txt}" if not self._collapsed else "")
        self.btn_help.setText("  Help (F1)" if not self._collapsed else "")
        self.btn_exit.setText("  Exit" if not self._collapsed else "")
        self._update_collapse_icon()

    def _update_collapse_icon(self):
        icon_char = "\u00ab" if not self._collapsed else "\u00bb"
        self.btn_collapse.setText(f"  {icon_char}" if not self._collapsed else icon_char)
        if HAS_QTAWESOME:
            self.btn_collapse.setIcon(qta.icon(
                "fa5s.chevron-left" if not self._collapsed else "fa5s.chevron-right",
                color=Styles.COLOR_TEXT_SECONDARY,
            ))
            self.btn_collapse.setIconSize(QSize(16, 16))

    def handle_click(self, index):
        if self._collapsed:
            self.set_active(index)
            self.page_changed.emit(index)
            QTimer.singleShot(200, self.toggle_collapse)
        else:
            self.set_active(index)
            self.page_changed.emit(index)

    def set_active(self, index):
        for i, btn in enumerate(self._nav_buttons):
            btn.setChecked(i == index)

    def toggle_collapse(self):
        if self._animating:
            return
        self._animating = True
        self._collapsed = not self._collapsed
        target = COLLAPSED_WIDTH if self._collapsed else EXPANDED_WIDTH

        self._update_labels_and_icons()

        self._anim = QPropertyAnimation(self, b"sidebar_width")
        self._anim.setDuration(200)
        self._anim.setStartValue(float(self.width()))
        self._anim.setEndValue(float(target))
        self._anim.setEasingCurve(QEasingCurve.Type.OutQuad)
        self._anim.finished.connect(self._on_anim_finished)
        self._anim.start()

    def _on_anim_finished(self):
        self._animating = False
        self.setFixedWidth(int(round(self._sidebar_width)))

    def show_help(self):
        from src.gui.dialogs import ShortcutHelpDialog
        dialog = ShortcutHelpDialog(self)
        dialog.exec()
