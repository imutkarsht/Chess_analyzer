import os

from PyQt6.QtCore import (
    QPropertyAnimation,
    Qt,
    pyqtProperty,
    pyqtSignal,
)
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication, QFrame, QVBoxLayout

from src.gui.components.controls.button import Button, ButtonVariant
from src.gui.styles import Styles
from src.gui.theme import ThemeManager
from src.gui.theme.motion import MotionDuration, MotionEasing
from src.utils.config import ConfigManager
from src.utils.path_utils import get_resource_path

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

    def __init__(self, config_manager=None):
        super().__init__()
        self.setObjectName("Sidebar")
        self._config = config_manager or ConfigManager()
        self._start_collapsed = bool(self._config.get("sidebar_start_collapsed", False))
        self._auto_expand_on_nav = not self._start_collapsed
        self._collapsed = self._start_collapsed
        self._animating = False
        self._sidebar_width = COLLAPSED_WIDTH if self._collapsed else EXPANDED_WIDTH

        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
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

        self.btn_collapse = Button(
            variant=ButtonVariant.GHOST,
            align="left",
            icon_size=16,
            on_click=self.toggle_collapse,
        )
        self.btn_collapse.setFixedHeight(40)
        self.layout.addWidget(self.btn_collapse)

        self.btn_exit = self._make_nav_button("Exit", "exit.png", -1)
        self.btn_exit.clicked.connect(QApplication.instance().quit)
        self.layout.addWidget(self.btn_exit)

        ThemeManager.instance().theme_changed.connect(self.apply_style)
        ThemeManager.instance().accent_changed.connect(self.apply_style)

        self.apply_style()

        self._update_labels_and_icons()
        self.setFixedWidth(int(self._sidebar_width))
        self.set_active(0)

    def _get_sidebar_width(self):
        return self._sidebar_width

    def _set_sidebar_width(self, w):
        self._sidebar_width = w
        self.setFixedWidth(int(round(w)))

    sidebar_width = pyqtProperty(float, _get_sidebar_width, _set_sidebar_width)

    def _apply_icon(self, btn, icon_name):
        if HAS_QTAWESOME and icon_name in QTAWESOME_ICONS:
            color_str = Styles.COLOR_ACCENT if btn.isChecked() else Styles.COLOR_TEXT_SECONDARY
            btn.set_icon_spec(qta.icon(QTAWESOME_ICONS[icon_name], color=color_str))
        else:
            icon_path = get_resource_path(os.path.join("assets", "icons", icon_name))
            if os.path.exists(icon_path):
                btn.set_icon_spec(QIcon(icon_path))

    def _make_nav_button(self, text: str, icon_name: str, index: int) -> Button:
        on_click = (
            (lambda _checked=False, idx=index: self.handle_click(idx))
            if index >= 0
            else None
        )
        btn = Button(
            text,
            ButtonVariant.GHOST,
            icon_size=22,
            checkable=index >= 0,
            align="left",
            on_click=on_click,
        )
        btn.setFixedHeight(48)
        # Tooltips keep the icon-only (collapsed) sidebar discoverable.
        btn.setToolTip(text)

        self._apply_icon(btn, icon_name)

        return btn

    def apply_style(self, *_args):
        p = ThemeManager.palette()
        self.setStyleSheet(f"""
            #Sidebar {{
                background-color: {p.surface};
                border-right: 1px solid {p.border};
            }}
        """)
        for btn in (*self._nav_buttons, self.btn_help, self.btn_exit, self.btn_collapse):
            btn.refresh_styles()

        nav_specs = [
            ("Analyze", "analyze.png", 0),
            ("Explorer", "explorer.png", 1),
            ("History", "history.png", 2),
            ("Stats", "stats.png", 3),
            ("Settings", "settings.png", 4),
        ]
        for btn, (_text, icon_name, _idx) in zip(self._nav_buttons, nav_specs, strict=False):
            self._apply_icon(btn, icon_name)
        self._apply_icon(self.btn_help, "help.png")
        self._apply_icon(self.btn_exit, "exit.png")
        self._update_collapse_icon()

    def _update_labels_and_icons(self):
        nav_texts = ["Analyze", "Explorer", "History", "Stats", "Settings"]
        align = "center" if self._collapsed else "left"
        for btn, txt in zip(self._nav_buttons, nav_texts, strict=False):
            btn.setText(txt if not self._collapsed else "")
            btn.set_align(align)
        self.btn_help.setText("Help (F1)" if not self._collapsed else "")
        self.btn_help.set_align(align)
        self.btn_exit.setText("Exit" if not self._collapsed else "")
        self.btn_exit.set_align(align)
        self.btn_collapse.set_align(align)
        self._update_collapse_icon()

    def _update_collapse_icon(self):
        icon_char = "\u00ab" if not self._collapsed else "\u00bb"
        self.btn_collapse.setText(icon_char)
        icon_name = "fa5s.chevron-left" if not self._collapsed else "fa5s.chevron-right"
        self.btn_collapse.set_icon_spec(icon_name)

    def handle_click(self, index):
        self.set_active(index)
        self.page_changed.emit(index)
        if self._collapsed and self._auto_expand_on_nav:
            self._set_collapsed(False)

    def set_active(self, index):
        nav_specs = [
            ("Analyze", "analyze.png", 0),
            ("Explorer", "explorer.png", 1),
            ("History", "history.png", 2),
            ("Stats", "stats.png", 3),
            ("Settings", "settings.png", 4),
        ]
        for i, btn in enumerate(self._nav_buttons):
            btn.setChecked(i == index)
            self._apply_icon(btn, nav_specs[i][1])

    def toggle_collapse(self):
        if self._animating:
            return
        self._set_collapsed(not self._collapsed)

    def _set_collapsed(self, collapsed: bool):
        """Animate to the requested state, cancelling any in-flight animation."""
        if getattr(self, "_anim", None) is not None and self._animating:
            try:
                self._anim.finished.disconnect(self._on_anim_finished)
            except TypeError:
                pass
            self._anim.stop()

        self._animating = False
        self._collapsed = collapsed
        target = COLLAPSED_WIDTH if collapsed else EXPANDED_WIDTH

        self._update_labels_and_icons()

        self._animating = True
        self._anim = QPropertyAnimation(self, b"sidebar_width")
        self._anim.setDuration(MotionDuration.BASE)
        self._anim.setStartValue(float(self.width()))
        self._anim.setEndValue(float(target))
        self._anim.setEasingCurve(MotionEasing.STATE)
        self._anim.finished.connect(self._on_anim_finished)
        self._anim.start()

    def apply_preferences(self):
        """Re-read the configured default and reflect it immediately."""
        self._start_collapsed = bool(self._config.get("sidebar_start_collapsed", False))
        self._auto_expand_on_nav = not self._start_collapsed
        if self._start_collapsed != self._collapsed:
            self._set_collapsed(self._start_collapsed)

    def _on_anim_finished(self):
        self._animating = False
        self.setFixedWidth(int(round(self._sidebar_width)))

    def show_help(self):
        from src.gui.dialogs import ShortcutHelpDialog
        dialog = ShortcutHelpDialog(self)
        dialog.exec()
