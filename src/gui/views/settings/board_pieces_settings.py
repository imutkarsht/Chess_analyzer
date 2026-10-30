"""Board rendering and piece set settings."""

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QButtonGroup,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ....constants import DEFAULT_BOARD_THEME
from ....utils.path_utils import get_resource_path
from ...components import Tabs, TabVariant
from ...components.feedback.toast import ToastManager
from ...styles import Styles
from ...theme.palette import BOARD_THEMES
from .board_preview import BoardThemePreview, board_swatch, piece_theme_preview
from .components import SettingsBinder, SettingsForm
from .helpers import create_icon_button


class BoardPiecesSettings(QGroupBox):
    """Board colours, pieces, and annotation overlays."""

    theme_refreshed = pyqtSignal()

    def __init__(self, config_manager, parent=None):
        super().__init__("Board && Pieces", parent)
        self.config_manager = config_manager
        self.setStyleSheet(Styles.get_group_box_style())
        self.board_buttons: dict[str, QPushButton] = {}
        self.piece_buttons: dict[str, QToolButton] = {}
        self.board_group = QButtonGroup(self)
        self.board_group.setExclusive(True)
        self.piece_group = QButtonGroup(self)
        self.piece_group.setExclusive(True)
        self.setup_ui()

    def setup_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 8, 0, 0)
        outer.setSpacing(14)

        self.subtitle = QLabel("Customize the look and feel of your chess set.")
        self.subtitle.setStyleSheet(
            Styles.get_secondary_label_style(size=12)
            + " "
            + Styles.get_transparent_label_style()
        )
        outer.addWidget(self.subtitle)

        self.tabs = Tabs(TabVariant.UNDERLINE)
        self.tabs.add_tab("Boards")
        self.tabs.add_tab("Pieces")
        self.tabs.current_changed.connect(self._on_tab_changed)
        outer.addWidget(self.tabs, 0, Qt.AlignmentFlag.AlignLeft)

        gallery_row = QHBoxLayout()
        gallery_row.setSpacing(20)

        self.gallery_container = QWidget()
        self.gallery_container.setStyleSheet(Styles.get_transparent_label_style())
        self.gallery_layout = QGridLayout(self.gallery_container)
        self.gallery_layout.setContentsMargins(0, 0, 0, 0)
        self.gallery_layout.setSpacing(8)
        gallery_row.addWidget(
            self.gallery_container, 0, Qt.AlignmentFlag.AlignTop
        )

        self.preview = BoardThemePreview(self)
        gallery_row.addWidget(self.preview, 0, Qt.AlignmentFlag.AlignTop)
        gallery_row.addStretch(1)
        outer.addLayout(gallery_row)

        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setStyleSheet(Styles.get_divider_style())
        outer.addWidget(divider)

        self.form = SettingsForm(self)
        self.binder = SettingsBinder(self.config_manager, self.form, self)
        outer.addWidget(self.form)
        self._add_board_display_rows()

        self.import_theme_btn = create_icon_button(
            "Import Theme...", "fa5s.folder-open", self.import_theme, self
        )
        self.import_theme_btn.setMaximumWidth(170)

        self._build_board_buttons()
        self._build_piece_buttons()
        self._render_gallery()
        self._sync_theme_selection()
        self._apply_styles()

    # ------------------------------------------------------------------
    # Galleries
    # ------------------------------------------------------------------
    def _build_board_buttons(self) -> None:
        self.board_group.deleteLater()
        self.board_group = QButtonGroup(self)
        self.board_group.setExclusive(True)
        self.board_buttons = {}
        for name in BOARD_THEMES:
            button = QPushButton()
            button.setCheckable(True)
            button.setFixedSize(64, 64)
            button.setIconSize(QSize(56, 56))
            button.setIcon(QIcon(board_swatch(name, 56)))
            button.setToolTip(name)
            button.setAccessibleName(f"{name} board theme")
            button.clicked.connect(lambda _checked=False, n=name: self._select_board(n))
            self.board_group.addButton(button)
            self.board_buttons[name] = button

    def _build_piece_buttons(self) -> None:
        from ...board.piece_themes import get_piece_theme_names

        for button in self.piece_buttons.values():
            button.setParent(None)
            button.deleteLater()
        self.piece_group.deleteLater()
        self.piece_group = QButtonGroup(self)
        self.piece_group.setExclusive(True)
        self.piece_buttons = {}
        board_theme = self.config_manager.get("board_theme", DEFAULT_BOARD_THEME)
        for name in get_piece_theme_names():
            button = QToolButton()
            button.setCheckable(True)
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            button.setIcon(QIcon(piece_theme_preview(name, board_theme)))
            button.setIconSize(QSize(84, 84))
            button.setText(name)
            button.setFixedSize(150, 126)
            button.setToolTip(name)
            button.setAccessibleName(f"{name} piece theme")
            button.clicked.connect(
                lambda _checked=False, n=name: self._select_piece(n)
            )
            self.piece_group.addButton(button)
            self.piece_buttons[name] = button

    def _render_gallery(self) -> None:
        while self.gallery_layout.count():
            self.gallery_layout.takeAt(0)

        for button in self.board_buttons.values():
            button.hide()
        for button in self.piece_buttons.values():
            button.hide()
        self.import_theme_btn.hide()

        if self.tabs.current_index() == 0:
            for index, button in enumerate(self.board_buttons.values()):
                self.gallery_layout.addWidget(button, index // 4, index % 4)
                button.show()
        else:
            for index, button in enumerate(self.piece_buttons.values()):
                self.gallery_layout.addWidget(button, index // 2, index % 2)
                button.show()
            row = (len(self.piece_buttons) + 1) // 2
            self.gallery_layout.addWidget(
                self.import_theme_btn,
                row,
                0,
                1,
                2,
                Qt.AlignmentFlag.AlignLeft,
            )
            self.import_theme_btn.show()
        self._apply_button_styles()

    def _apply_button_styles(self) -> None:
        swatch_style = Styles.get_board_swatch_button_style()
        for button in self.board_buttons.values():
            button.setStyleSheet(swatch_style)
        for button in self.piece_buttons.values():
            button.setStyleSheet(Styles.get_theme_card_button_style())
        self.import_theme_btn.refresh_styles()

    def _on_tab_changed(self, _index: int) -> None:
        self._render_gallery()

    # ------------------------------------------------------------------
    # Selection
    # ------------------------------------------------------------------
    def _select_board(self, name: str) -> None:
        if name not in self.board_buttons:
            return
        self.config_manager.set("board_theme", name)
        self._build_piece_buttons()
        self._render_gallery()
        self._sync_theme_selection()
        self.theme_refreshed.emit()

    def _select_piece(self, name: str) -> None:
        if name not in self.piece_buttons:
            return
        self.config_manager.set("piece_theme", name)
        self._render_gallery()
        self._sync_theme_selection()
        self.theme_refreshed.emit()

    def _sync_theme_selection(self) -> None:
        board_theme = self.config_manager.get("board_theme", DEFAULT_BOARD_THEME)
        if board_theme not in self.board_buttons:
            board_theme = DEFAULT_BOARD_THEME
        for name, button in self.board_buttons.items():
            button.setChecked(name == board_theme)

        piece_theme = self.config_manager.get("piece_theme", "Standard")
        if piece_theme not in self.piece_buttons:
            piece_theme = "Standard"
        for name, button in self.piece_buttons.items():
            button.setChecked(name == piece_theme)

        self.preview.set_themes(board_theme, piece_theme)

    # ------------------------------------------------------------------
    # Display rows
    # ------------------------------------------------------------------
    def _add_board_display_rows(self):
        self.coordinates_checkbox = self.binder.add(
            "board_show_coordinates",
            on_change=lambda _value: self.theme_refreshed.emit(),
        )
        self.classification_checkbox = self.binder.add(
            "board_show_classification",
            on_change=lambda _value: self.theme_refreshed.emit(),
        )
        self.best_move_arrow_checkbox = self.binder.add(
            "board_show_best_move_arrow",
            on_change=lambda _value: self.theme_refreshed.emit(),
        )
        self.last_move_checkbox = self.binder.add(
            "board_show_last_move",
            on_change=lambda _value: self.theme_refreshed.emit(),
        )
        self.eval_bar_checkbox = self.binder.add(
            "board_show_eval_bar",
            on_change=lambda _value: self.theme_refreshed.emit(),
        )

    def import_theme(self):
        from ...board.piece_themes import (
            import_theme_from_folder,
            validate_theme_folder,
        )

        folder = QFileDialog.getExistingDirectory(
            self, "Select Piece Theme Folder", "", QFileDialog.Option.ShowDirsOnly
        )
        if not folder:
            return
        is_valid, errors = validate_theme_folder(folder)
        if not is_valid:
            ToastManager.error(self, "Invalid theme: " + "; ".join(errors))
            return
        theme_name = import_theme_from_folder(folder)
        if theme_name is None:
            ToastManager.error(self, "Theme import failed. Check the logs.")
            return

        self._build_piece_buttons()
        self._select_piece(theme_name)
        ToastManager.success(
            self, f"Piece theme '{theme_name}' imported and active."
        )

    # ------------------------------------------------------------------
    # Lifecycle hooks used by SettingsView
    # ------------------------------------------------------------------
    def reload_from_config(self):
        self.binder.load()
        self._sync_theme_selection()

    def set_advanced_visible(self, visible):
        self.binder.set_advanced_visible(visible)

    def refresh_styles(self, *args, **kwargs):
        self.setStyleSheet(Styles.get_group_box_style())
        self.subtitle.setStyleSheet(
            Styles.get_secondary_label_style(size=12)
            + " "
            + Styles.get_transparent_label_style()
        )
        self.tabs.refresh_styles()
        self.form.refresh_styles()
        self._apply_button_styles()
        self._sync_theme_selection()
        tick_path = get_resource_path("assets/images/tick.svg").replace("\\", "/")
        for checkbox in (
            self.coordinates_checkbox,
            self.classification_checkbox,
            self.best_move_arrow_checkbox,
            self.last_move_checkbox,
            self.eval_bar_checkbox,
        ):
            checkbox.setStyleSheet(Styles.get_settings_checkbox_style(tick_path))

    def _apply_styles(self) -> None:
        self.tabs.refresh_styles()
        self._apply_button_styles()
