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
from src.gui.icons import IconStyleManager, icon_qicon
from src.gui.styles import Styles
from src.gui.theme import ThemeManager
from src.gui.theme.motion import MotionDuration, MotionEasing
from src.gui.utils.assets import icon_path
from src.utils.config import ConfigManager

QTAWESOME_ICONS = {
    "help.png": "question-circle",
    "exit.png": "sign-out-alt",
    "analyze.png": "chess-board",
    "explorer.png": "compass",
    "history.png": "history",
    "stats.png": "chart-bar",
    "settings.png": "cog",
}

COLLAPSED_WIDTH = 60
EXPANDED_WIDTH = 200
# Labels are switched while the rail is already narrow/wide enough to hold
# them. Updating them at the first animation frame made text appear clipped in
# a 60 px rail (and vanish from a 200 px rail), which read as a jump.
_LABEL_HIDE_WIDTH = 118
_LABEL_SHOW_WIDTH = 142


class Sidebar(QFrame):
    page_changed = pyqtSignal(int)
    animation_changed = pyqtSignal(bool)

    def __init__(self, config_manager=None):
        super().__init__()
        self.setObjectName("Sidebar")
        self._config = config_manager or ConfigManager()
        self._start_collapsed = self._config.sidebar_start_collapsed
        self._auto_expand_on_nav = not self._start_collapsed
        self._collapsed = self._start_collapsed
        self._labels_visible = not self._collapsed
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
        IconStyleManager.instance().style_changed.connect(self.apply_style)

        self.apply_style()

        self._update_labels_and_icons()
        self.setFixedWidth(int(self._sidebar_width))
        self.set_active(0)

    def _get_sidebar_width(self):
        return self._sidebar_width

    def _set_sidebar_width(self, w):
        self._sidebar_width = w
        width = int(round(w))
        self.setFixedWidth(width)
        self._sync_labels_for_width(width)

    def _sync_labels_for_width(self, width: int) -> None:
        """Swap between icon-only and labelled rows at a readable width."""
        if (
            self._collapsed
            and self._labels_visible
            and width <= _LABEL_HIDE_WIDTH
        ) or (
            not self._collapsed
            and not self._labels_visible
            and width >= _LABEL_SHOW_WIDTH
        ):
            self._update_labels_and_icons()

    sidebar_width = pyqtProperty(float, _get_sidebar_width, _set_sidebar_width)

    def _apply_icon(self, btn, icon_name):
        if icon_name in QTAWESOME_ICONS:
            color_str = (
                Styles.COLOR_ACCENT if btn.isChecked() else Styles.COLOR_TEXT_SECONDARY
            )
            icon = icon_qicon(QTAWESOME_ICONS[icon_name], color_str)
            if not icon.isNull():
                btn.set_icon_spec(icon)
                return
        sidebar_icon = icon_path(icon_name)
        if os.path.exists(sidebar_icon):
            btn.set_icon_spec(QIcon(sidebar_icon))

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
        btn.setAccessibleName(text)
        # Tooltips are only needed while the labels are hidden.
        if self._collapsed:
            btn.setToolTip(text)

        self._apply_icon(btn, icon_name)

        return btn

    def apply_style(self, *_args):
        """Re-tint navigation icons; the frame chrome is owned by the global QSS."""
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
            btn.setAccessibleName(txt)
            btn.setToolTip(txt if self._collapsed else "")
        for btn, txt in ((self.btn_help, "Help (F1)"), (self.btn_exit, "Exit")):
            btn.setText(txt if not self._collapsed else "")
            btn.set_align(align)
            btn.setAccessibleName(txt)
            btn.setToolTip(txt if self._collapsed else "")
        self.btn_collapse.set_align(align)
        self.btn_collapse.setAccessibleName(
            "Expand sidebar" if self._collapsed else "Collapse sidebar"
        )
        self.btn_collapse.setToolTip(
            "Expand sidebar" if self._collapsed else "Collapse sidebar"
        )
        self._labels_visible = not self._collapsed
        self._update_collapse_icon()

    def _update_collapse_icon(self):
        icon_char = "\u00ab" if not self._collapsed else "\u00bb"
        self.btn_collapse.setText(icon_char)
        icon_name = "chevron-left" if not self._collapsed else "chevron-right"
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
        self._update_collapse_icon()

        self._animating = True
        self.animation_changed.emit(True)
        self._anim = QPropertyAnimation(self, b"sidebar_width", self)
        self._anim.setDuration(MotionDuration.BASE)
        self._anim.setStartValue(float(self.width()))
        self._anim.setEndValue(float(target))
        self._anim.setEasingCurve(MotionEasing.STATE)
        self._anim.finished.connect(self._on_anim_finished)
        self._anim.start()

    def apply_preferences(self):
        """Re-read the configured default and reflect it immediately."""
        self._start_collapsed = self._config.sidebar_start_collapsed
        self._auto_expand_on_nav = not self._start_collapsed
        if self._start_collapsed != self._collapsed:
            self._set_collapsed(self._start_collapsed)

    def _on_anim_finished(self):
        self._animating = False
        self.animation_changed.emit(False)
        target = COLLAPSED_WIDTH if self._collapsed else EXPANDED_WIDTH
        self._sidebar_width = float(target)
        self.setFixedWidth(target)
        self._sync_labels_for_width(target)
        anim = getattr(self, "_anim", None)
        self._anim = None
        if anim is not None:
            anim.deleteLater()

    def show_help(self):
        from src.gui.dialogs.shortcut_help_dialog import open_shortcut_help_overlay
        open_shortcut_help_overlay(self)
