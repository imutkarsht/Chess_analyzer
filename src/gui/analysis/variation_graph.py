"""Git-style variation branch strip shown under the analysis board."""

from __future__ import annotations

from PyQt6.QtCore import QEvent, QPoint, QPointF, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QFontMetrics, QIcon, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from src.backend.analysis.variation_tree import VariationBranch, VariationNode, VariationTree
from src.gui.styles import Styles

try:
    import qtawesome as qta

    HAS_QTAWESOME = True
except ImportError:  # pragma: no cover - exercised only on broken installs
    qta = None
    HAS_QTAWESOME = False

COL_W = 58
LANE_H = 30
PAD_X = 12
PAD_Y = 8
NODE_H = 22
CHIP_H = 20
EVAL_W = 54


class _BranchChip(QFrame):
    """A branch name chip with a hover delete button and a context menu."""

    clicked = pyqtSignal(int)
    rename_requested = pyqtSignal(int)
    delete_requested = pyqtSignal(int)

    def __init__(self, branch_id: int, name: str, color: str, active: bool, parent=None):
        super().__init__(parent)
        self.branch_id = branch_id
        self._color = color
        self._active = active
        self.setObjectName("BranchChip")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_menu)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 0, 3, 0)
        layout.setSpacing(2)

        self.lbl_name = QLabel(name, self)
        self.lbl_name.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.lbl_name.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        layout.addWidget(self.lbl_name, 1)

        self.btn_delete = QToolButton(self)
        self.btn_delete.setText("×")
        self.btn_delete.setFixedSize(13, 13)
        self.btn_delete.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_delete.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_delete.setToolTip("Delete this branch")
        self.btn_delete.hide()
        self.btn_delete.clicked.connect(lambda: self.delete_requested.emit(self.branch_id))
        layout.addWidget(self.btn_delete, 0)

        self.setStyleSheet(Styles.get_variation_branch_chip_style(color, active))

    def enterEvent(self, event):
        self.btn_delete.show()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.btn_delete.hide()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.branch_id)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.rename_requested.emit(self.branch_id)
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def _show_menu(self, pos: QPoint):
        menu = QMenu(self)
        rename = menu.addAction("Rename branch")
        delete = menu.addAction("Delete branch")
        chosen = menu.exec(self.mapToGlobal(pos))
        if chosen is rename:
            self.rename_requested.emit(self.branch_id)
        elif chosen is delete:
            self.delete_requested.emit(self.branch_id)


class _RenameEdit(QLineEdit):
    cancelled = pyqtSignal()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.cancelled.emit()
            event.accept()
            return
        super().keyPressEvent(event)


class _VariationCanvas(QWidget):
    """Paints lane curves behind absolutely positioned move pills."""

    def __init__(self, scroll_area, parent=None):
        super().__init__(parent)
        self._scroll_area = scroll_area
        self._drag_last: QPoint | None = None
        self.tree: VariationTree | None = None
        self.active_branch_id: int | None = None
        self.pills: dict[int, QPushButton] = {}
        self.setStyleSheet("background: transparent;")
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setToolTip("Drag to pan · scroll vertically · Shift-scroll horizontally")

    def wheelEvent(self, event):
        self._pan_wheel(event)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Wheel:
            self._pan_wheel(event)
            return True
        return super().eventFilter(obj, event)

    def _pan_wheel(self, event) -> None:
        pixel = event.pixelDelta()
        angle = event.angleDelta()
        dx = pixel.x() or angle.x()
        dy = pixel.y() or angle.y()
        hbar = self._scroll_area.horizontalScrollBar()
        vbar = self._scroll_area.verticalScrollBar()
        if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            hbar.setValue(hbar.value() - (dx or dy))
        else:
            if dx:
                hbar.setValue(hbar.value() - dx)
            if dy:
                if vbar.maximum() > 0:
                    vbar.setValue(vbar.value() - dy)
                else:
                    hbar.setValue(hbar.value() - dy)
        event.accept()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_last = event.position().toPoint()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_last is not None:
            current = event.position().toPoint()
            delta = current - self._drag_last
            hbar = self._scroll_area.horizontalScrollBar()
            vbar = self._scroll_area.verticalScrollBar()
            hbar.setValue(hbar.value() - delta.x())
            vbar.setValue(vbar.value() - delta.y())
            self._drag_last = current
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._drag_last is not None:
            self._drag_last = None
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def set_pills(self, pills: dict[int, QPushButton]) -> None:
        self.pills = pills

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.tree is None:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        try:
            for branch in self.tree.branches:
                color = QColor(Styles.get_branch_color(branch.color_index))
                active = branch.branch_id == self.active_branch_id
                color.setAlpha(245 if active else 140)
                pen = QPen(color, 2.4 if active else 1.6)
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                painter.setPen(pen)

                moves = self.tree.branch_moves(branch)
                for first, second in zip(moves, moves[1:], strict=False):
                    self._draw_edge(painter, first, second)

                # Connector from the fork position into this branch's first node.
                self._draw_edge(painter, branch.fork_node, branch.first_node)
        finally:
            painter.end()

    def _center(self, node: VariationNode) -> QPoint | None:
        pill = self.pills.get(node.node_id)
        if pill is None:
            return None
        geo = pill.geometry()
        return QPoint(geo.center().x(), geo.center().y())

    def _draw_edge(self, painter: QPainter, parent: VariationNode, child: VariationNode):
        start = self._center(parent)
        end = self._center(child)
        if start is None or end is None:
            return
        start_f = QPointF(start)
        end_f = QPointF(end)
        path = QPainterPath(start_f)
        if start.y() == end.y():
            path.lineTo(end_f)
        else:
            mid_x = (start.x() + end.x()) / 2
            path.cubicTo(
                QPointF(mid_x, start.y()),
                QPointF(mid_x, end.y()),
                end_f,
            )
        painter.drawPath(path)


class VariationGraph(QFrame):
    """Compact branch graph replacing the old one-line variation bar."""

    node_clicked = pyqtSignal(int)
    branch_clicked = pyqtSignal(int)
    ghost_clicked = pyqtSignal()
    play_best_requested = pyqtSignal()
    undo_requested = pyqtSignal()
    reset_requested = pyqtSignal()
    exit_requested = pyqtSignal()
    branch_rename_requested = pyqtSignal(int, str)
    branch_delete_requested = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("VariationGraph")
        self.setVisible(False)
        self.setFixedHeight(208)

        self.tree: VariationTree | None = None
        self.active_node_id: int | None = None
        self.active_branch_id: int | None = None
        self._ghost_san: str | None = None
        self._ghost_eval: str | None = None
        self._node_names: dict[int, str] = {}
        self._chips: dict[int, _BranchChip] = {}
        self._eval_labels: dict[int, QLabel] = {}
        self._rename_edit: _RenameEdit | None = None
        self._renaming_branch_id: int | None = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 5, 8, 6)
        outer.setSpacing(3)

        header = QHBoxLayout()
        header.setContentsMargins(2, 0, 2, 0)
        header.setSpacing(4)

        self.lbl_icon = QLabel()
        self.lbl_icon.setFixedSize(16, 16)
        self.lbl_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.addWidget(self.lbl_icon)

        self.lbl_title = QLabel("Variations")
        header.addWidget(self.lbl_title)

        self.lbl_context = QLabel("")
        self.lbl_context.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.lbl_context.setMinimumWidth(40)
        header.addWidget(self.lbl_context, 1)

        self.btn_best = self._action_button(
            "fa5s.play", "▶", "Play the engine's best move"
        )
        self.btn_undo = self._action_button(
            "fa5s.undo", "↶", "Undo the last variation move (←)"
        )
        self.btn_reset = self._action_button(
            "fa5s.home", "⌂", "Return to the branch point (Home)"
        )
        self.btn_exit = self._action_button(
            "fa5s.times", "✕", "Exit Explore and return to the game (Esc)"
        )
        self.btn_best.clicked.connect(lambda _checked=False: self.play_best_requested.emit())
        self.btn_undo.clicked.connect(lambda _checked=False: self.undo_requested.emit())
        self.btn_reset.clicked.connect(lambda _checked=False: self.reset_requested.emit())
        self.btn_exit.clicked.connect(lambda _checked=False: self.exit_requested.emit())
        for btn in (self.btn_best, self.btn_undo, self.btn_reset, self.btn_exit):
            header.addWidget(btn)
        outer.addLayout(header)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(False)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.canvas = _VariationCanvas(self.scroll)
        self.canvas.setMinimumSize(120, LANE_H + PAD_Y * 2)
        self.scroll.setWidget(self.canvas)
        outer.addWidget(self.scroll, 1)

        self.refresh_styles()

    def _action_button(self, icon_name: str, fallback: str, tooltip: str) -> QPushButton:
        btn = QPushButton("", self)
        btn.setFixedSize(24, 24)
        btn.setIconSize(QSize(12, 12))
        btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setToolTip(tooltip)
        btn.setAccessibleName(tooltip)
        if HAS_QTAWESOME:
            btn.setIcon(qta.icon(icon_name, color=Styles.COLOR_TEXT_PRIMARY))
        else:
            btn.setText(fallback)
        return btn

    def _apply_action_icons(self) -> None:
        specs = (
            (self.btn_best, "fa5s.play", "▶"),
            (self.btn_undo, "fa5s.undo", "↶"),
            (self.btn_reset, "fa5s.home", "⌂"),
            (self.btn_exit, "fa5s.times", "✕"),
        )
        for btn, icon_name, fallback in specs:
            if HAS_QTAWESOME:
                color = (
                    Styles.COLOR_ACCENT
                    if btn is self.btn_best
                    else Styles.COLOR_TEXT_PRIMARY
                )
                btn.setText("")
                btn.setIcon(qta.icon(icon_name, color=color))
            else:
                btn.setIcon(QIcon())
                btn.setText(fallback)

    # ------------------------------------------------------------------ public API
    def set_context(self, text: str) -> None:
        self.lbl_context.setText(text)
        self.lbl_context.setToolTip(text)

    def set_state(
        self,
        tree: VariationTree,
        active_node: VariationNode,
        active_branch: VariationBranch | None,
        ghost_san: str | None = None,
    ) -> None:
        self.tree = tree
        self.active_node_id = active_node.node_id
        self.active_branch_id = active_branch.branch_id if active_branch else None
        self._ghost_san = ghost_san
        self.canvas.tree = tree
        self.canvas.active_branch_id = self.active_branch_id
        self._clear_children()
        self._render(active_node)
        self.set_buttons_state(
            can_undo=active_node.parent is not None,
            can_reset=active_node.parent is not None,
            can_play_best=bool(ghost_san),
        )

    def set_ghost(self, san: str | None, eval_text: str | None = None) -> None:
        self._ghost_san = san
        self._ghost_eval = eval_text
        self._render_ghost()
        self.btn_best.setEnabled(bool(san))

    def update_node_eval(self, node_id: int, text: str) -> None:
        label = self._eval_labels.get(node_id)
        if label is None:
            return
        label.setText(text)
        node = self.tree.find_node(node_id) if self.tree is not None else None
        hidden_for_ghost = (
            node_id == self.active_node_id
            and bool(self._ghost_san)
            and node is not None
            and not node.children
        )
        label.setVisible(bool(text) and not hidden_for_ghost)
        self._position_eval_label(node_id)

    def set_buttons_state(self, can_undo: bool, can_reset: bool, can_play_best: bool) -> None:
        self.btn_undo.setEnabled(can_undo)
        self.btn_reset.setEnabled(can_reset)
        self.btn_best.setEnabled(can_play_best)

    def begin_rename(self, branch_id: int) -> None:
        branch = self.tree.branch_for_id(branch_id) if self.tree else None
        chip = self._chips.get(branch_id)
        if branch is None or chip is None:
            return
        self._finish_rename()
        self._renaming_branch_id = branch_id
        editor = _RenameEdit(self.canvas)
        editor.setObjectName("BranchRenameEdit")
        geo = chip.geometry()
        editor.setGeometry(geo)
        editor.setText(branch.name)
        editor.selectAll()
        editor.returnPressed.connect(self._commit_rename)
        editor.cancelled.connect(self._finish_rename)
        editor.show()
        editor.setFocus()
        self._rename_edit = editor

    def clear(self) -> None:
        self.tree = None
        self.canvas.tree = None
        self._clear_children()
        self.canvas.setMinimumSize(120, LANE_H + PAD_Y * 2)
        self.canvas.update()

    def refresh_styles(self) -> None:
        self.setStyleSheet(Styles.get_variation_graph_style())
        self.lbl_icon.setText("⑂" if not HAS_QTAWESOME else "")
        if HAS_QTAWESOME:
            self.lbl_icon.setPixmap(
                qta.icon("fa5s.code-branch", color=Styles.COLOR_ACCENT).pixmap(14, 14)
            )
        self.lbl_title.setStyleSheet(
            Styles.get_label_style(size=12, weight=700, color=Styles.COLOR_TEXT_PRIMARY)
        )
        self.lbl_context.setStyleSheet(
            Styles.get_label_style(size=11, color=Styles.COLOR_TEXT_SECONDARY)
        )
        action_style = Styles.get_variation_action_button_style()
        for btn in (self.btn_best, self.btn_undo, self.btn_reset, self.btn_exit):
            btn.setStyleSheet(action_style)
        self._apply_action_icons()
        self.scroll.setStyleSheet("background: transparent; border: none;")
        if self.tree is not None:
            node = self.tree.find_node(self.active_node_id or 0)
            if node is not None:
                self.set_state(self.tree, node, self.tree.active_branch, self._ghost_san)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.tree is not None and self.active_node_id is not None:
            node = self.tree.find_node(self.active_node_id)
            if node is not None:
                self._scroll_to_active(node)

    # ------------------------------------------------------------------ rendering
    def _clear_children(self) -> None:
        self._finish_rename()
        for widget in (
            list(self.canvas.pills.values())
            + list(self._chips.values())
            + list(self._eval_labels.values())
        ):
            widget.setParent(None)
            widget.deleteLater()
        ghost = getattr(self, "_ghost", None)
        if ghost is not None:
            ghost.setParent(None)
            ghost.deleteLater()
        self.canvas.pills = {}
        self._chips.clear()
        self._eval_labels.clear()
        self._ghost = None
        self._node_names.clear()

    def _render(self, active_node: VariationNode) -> None:
        assert self.tree is not None
        max_depth = max(self.tree.max_depth(), active_node.ply + (1 if self._ghost_san else 0))
        max_lane = max(self.tree.max_lane(), active_node.lane)
        width = max(160, PAD_X * 2 + (max_depth + 1) * COL_W + EVAL_W)
        height = max(LANE_H + PAD_Y * 2, PAD_Y * 2 + (max_lane + 1) * LANE_H)
        self.canvas.setMinimumSize(width, height)
        self.canvas.resize(width, height)

        pills: dict[int, QPushButton] = {}
        root = self.tree.root
        root_pill = self._make_pill(
            "●",
            Styles.COLOR_TEXT_MUTED,
            root.node_id,
            active=root.node_id == self.active_node_id,
        )
        root_pill.setToolTip("Game position")
        root_pill.setStyleSheet(
            root_pill.styleSheet() + "QPushButton { padding: 0px; font-size: 8px; }"
        )
        self._node_names[root.node_id] = "Game"
        pills[root.node_id] = root_pill

        for branch in self.tree.branches:
            for node in self.tree.branch_moves(branch):
                color = Styles.get_branch_color(branch.color_index)
                pill = self._make_pill(
                    node.san,
                    color,
                    node.node_id,
                    active=node.node_id == self.active_node_id,
                )
                self._node_names[node.node_id] = node.san
                pills[node.node_id] = pill

        for node_id, pill in pills.items():
            node = self.tree.find_node(node_id)
            if node is None:
                continue
            self._position_pill(pill, node)
            pill.show()

        self.canvas.set_pills(pills)
        self._place_chips()

        for branch in self.tree.branches:
            tip = branch.tip
            text = self._eval_text(tip.eval_cp, tip.eval_mate)
            label = QLabel(text or "--", self.canvas)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setFixedSize(EVAL_W, 18)
            label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            label.setStyleSheet(
                Styles.get_eval_badge_style(Styles.COLOR_SURFACE, Styles.COLOR_TEXT_SECONDARY)
            )
            label.setVisible(bool(text))
            self._eval_labels[tip.node_id] = label
            self._position_eval_label(tip.node_id)

        self._render_ghost()
        self.canvas.update()
        self.lbl_title.setText(f"Variations · {self.tree.branch_count()}")
        self._scroll_to_active(active_node)

    def _make_pill(self, text: str, color: str, node_id: int, active: bool) -> QPushButton:
        pill = QPushButton(text, self.canvas)
        pill.setFixedHeight(NODE_H)
        pill.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        pill.setCursor(Qt.CursorShape.PointingHandCursor)
        pill.setStyleSheet(Styles.get_variation_node_style(color, active=active))
        pill.clicked.connect(lambda _checked=False, nid=node_id: self.node_clicked.emit(nid))
        pill.installEventFilter(self.canvas)
        pill.show()
        return pill

    def _position_pill(self, pill: QPushButton, node: VariationNode) -> None:
        center_y = PAD_Y + node.lane * LANE_H + LANE_H // 2
        if node.is_root:
            # A compact anchor dot leaves room for the first branch chip in
            # the shared root lane.
            pill.setFixedSize(14, 14)
            center_x = PAD_X + 7
            pill.move(center_x - 7, center_y - 7)
            return
        width = min(54, max(34, 14 + 7 * len(self._node_names.get(node.node_id, ""))))
        pill.setFixedHeight(NODE_H)
        pill.setFixedWidth(width)
        center_x = PAD_X + node.ply * COL_W + COL_W // 2
        pill.move(center_x - width // 2, center_y - NODE_H // 2)

    def _place_chips(self) -> None:
        assert self.tree is not None
        for branch in self.tree.branches:
            chip = _BranchChip(
                branch.branch_id,
                branch.name,
                Styles.get_branch_color(branch.color_index),
                branch.branch_id == self.active_branch_id,
                self.canvas,
            )
            chip.clicked.connect(self.branch_clicked.emit)
            chip.rename_requested.connect(self.begin_rename)
            chip.delete_requested.connect(self.branch_delete_requested.emit)
            chip.installEventFilter(self.canvas)
            chip.btn_delete.installEventFilter(self.canvas)
            metrics = QFontMetrics(QFont("SF Pro", 9))
            width = min(46, max(42, metrics.horizontalAdvance(branch.name) + 30))
            chip.setFixedSize(width, CHIP_H)
            chip.lbl_name.setText(
                metrics.elidedText(branch.name, Qt.TextElideMode.ElideRight, width - 24)
            )
            center_x = PAD_X + (branch.first_node.ply - 1) * COL_W + COL_W // 2 + 8
            center_y = PAD_Y + branch.lane * LANE_H + LANE_H // 2
            chip.move(center_x - width // 2, center_y - CHIP_H // 2)
            chip.setToolTip(
                f"{branch.name} line · {len(self.tree.branch_moves(branch))} moves\n"
                "Click to jump to the tip · double-click to rename"
            )
            chip.show()
            self._chips[branch.branch_id] = chip

    def _render_ghost(self) -> None:
        if self.tree is None or self.active_node_id is None:
            return
        node = self.tree.find_node(self.active_node_id)
        if node is None or node.children or not self._ghost_san:
            if getattr(self, "_ghost", None) is not None:
                self._ghost.hide()
            self._set_active_eval_visible(True)
            return
        self._set_active_eval_visible(False)
        if getattr(self, "_ghost", None) is None:
            self._ghost = QPushButton(self.canvas)
            self._ghost.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            self._ghost.setCursor(Qt.CursorShape.PointingHandCursor)
            self._ghost.clicked.connect(lambda: self.ghost_clicked.emit())
            self._ghost.installEventFilter(self.canvas)
        branch = self.tree.branch_for_node(node)
        color = (
            Styles.get_branch_color(branch.color_index)
            if branch is not None
            else Styles.COLOR_ACCENT
        )
        self._ghost.setText(self._ghost_san)
        self._ghost.setToolTip(
            f"Engine best: {self._ghost_san}"
            + (f" ({self._ghost_eval})" if self._ghost_eval else "")
        )
        self._ghost.setFixedHeight(NODE_H)
        width = min(64, max(42, 14 + 7 * len(self._ghost_san)))
        self._ghost.setFixedWidth(width)
        self._ghost.setStyleSheet(Styles.get_variation_node_style(color, ghost=True))
        center_x = PAD_X + (node.ply + 1) * COL_W + COL_W // 2
        center_y = PAD_Y + node.lane * LANE_H + LANE_H // 2
        self._ghost.move(center_x - width // 2, center_y - NODE_H // 2)
        self._ghost.show()
        self._ghost.raise_()
        needed_width = self._ghost.x() + width + PAD_X
        if self.canvas.minimumWidth() < needed_width:
            self.canvas.setMinimumWidth(needed_width)
            self.canvas.resize(needed_width, self.canvas.height())
        self.scroll.ensureVisible(self._ghost.x() + width + 4, center_y, 24, 18)

    def _position_eval_label(self, node_id: int) -> None:
        label = self._eval_labels.get(node_id)
        if self.tree is None or label is None:
            return
        node = self.tree.find_node(node_id)
        if node is None:
            return
        pill_width = min(54, max(34, 14 + 7 * len(self._node_names.get(node_id, ""))))
        center_x = PAD_X + node.ply * COL_W + COL_W // 2
        center_y = PAD_Y + node.lane * LANE_H + LANE_H // 2
        label.move(center_x + pill_width // 2 + 5, center_y - 9)

    def _set_active_eval_visible(self, visible: bool) -> None:
        label = self._eval_labels.get(self.active_node_id or -1)
        if label is None:
            return
        label.setVisible(visible and label.text() not in ("", "--"))

    def _scroll_to_active(self, node: VariationNode) -> None:
        x = PAD_X + node.ply * COL_W
        y = PAD_Y + node.lane * LANE_H
        self.scroll.ensureVisible(x, y, 40, 18)

    @staticmethod
    def _eval_text(cp: int | None, mate: int | None) -> str:
        if mate is not None:
            return f"{'+' if mate > 0 else '-'}M{abs(mate)}"
        if cp is None:
            return ""
        return f"{cp / 100:+.2f}"

    def _commit_rename(self) -> None:
        editor = self._rename_edit
        if editor is None or self._renaming_branch_id is None:
            return
        branch_id = self._renaming_branch_id
        text = editor.text()
        self._finish_rename()
        self.branch_rename_requested.emit(branch_id, text)

    def _finish_rename(self) -> None:
        editor, self._rename_edit = self._rename_edit, None
        self._renaming_branch_id = None
        if editor is not None:
            editor.hide()
            editor.setParent(None)
            editor.deleteLater()

    # Keep the branch id alongside the editor without subclassing further.
    def _begin_rename_for(self, branch_id: int) -> None:
        self.begin_rename(branch_id)
