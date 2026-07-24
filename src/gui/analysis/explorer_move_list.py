"""
Explorer Move List Widget - A lightweight move list for the Opening Explorer.

NOTE: This shares ~70% code with move_list_panel.py. Future refactoring should
extract a shared base class for both implementations.
"""
import chess
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView, QHBoxLayout, QPushButton
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QColor, QBrush, QIcon

from src.gui.styles import Styles
from src.utils.resources import ResourceManager


class ExplorerMoveListWidget(QWidget):
    """
    Displays the sequence of moves played in the Explorer.
    Emits `move_selected(index)` when a past move is clicked to navigate back.
    """
    move_selected = pyqtSignal(int)
    nav_first = pyqtSignal()
    nav_prev = pyqtSignal()
    nav_next = pyqtSignal()
    nav_last = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.resource_manager = ResourceManager()
        self.moves = []  # List of dicts: {'san': str, 'classification': str}
        self.current_index = -1

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(5)

        # Move List Table
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["#", "White", "Black"])
        self.table.horizontalHeader().setHighlightSections(False)
        self.table.horizontalHeader().setMinimumHeight(30)
        
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(0, 46)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(False)
        self.table.setShowGrid(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.cellClicked.connect(self.on_cell_clicked)
        self.table.setIconSize(QSize(16, 16))
        self.table.verticalHeader().setDefaultSectionSize(36)

        self.table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {Styles.COLOR_SURFACE};
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 8px;
                gridline-color: transparent;
                font-size: 14px;
            }}
            QTableWidget::item {{
                padding: 4px 8px;
                border-bottom: 1px solid {Styles.COLOR_SURFACE_LIGHT};
            }}
            QTableWidget::item:hover {{
                background-color: {Styles.COLOR_SURFACE_LIGHT};
            }}
            QTableWidget::item:selected {{
                background-color: {Styles.COLOR_HIGHLIGHT};
                color: {Styles.COLOR_TEXT_PRIMARY};
                border-left: 3px solid {Styles.COLOR_ACCENT};
            }}
            QHeaderView::section {{
                background-color: {Styles.COLOR_SURFACE_LIGHT};
                color: {Styles.COLOR_TEXT_SECONDARY};
                padding: 6px;
                border: none;
                border-bottom: 2px solid {Styles.COLOR_ACCENT};
                font-weight: 600;
                font-size: 13px;
            }}
        """)

        self.layout.addWidget(self.table)

        # Navigation Controls
        nav_layout = QHBoxLayout()
        nav_layout.setContentsMargins(0, 4, 0, 0)
        nav_layout.setSpacing(10)
        
        btn_style = f"""
            QPushButton {{
                background-color: {Styles.COLOR_SURFACE_LIGHT};
                color: {Styles.COLOR_TEXT_PRIMARY};
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 16px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {Styles.COLOR_SURFACE};
                border: 1px solid {Styles.COLOR_ACCENT};
            }}
            QPushButton:pressed {{
                background-color: {Styles.COLOR_ACCENT};
                color: white;
            }}
            QPushButton:disabled {{
                color: {Styles.COLOR_TEXT_MUTED};
                background-color: {Styles.COLOR_SURFACE_LIGHT};
            }}
        """

        self.btn_first = QPushButton("⏮")
        self.btn_prev = QPushButton("◀")
        self.btn_next = QPushButton("▶")
        self.btn_last = QPushButton("⏭")

        for btn in (self.btn_first, self.btn_prev, self.btn_next, self.btn_last):
            btn.setStyleSheet(btn_style)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            nav_layout.addWidget(btn)

        self.btn_first.clicked.connect(self.nav_first.emit)
        self.btn_prev.clicked.connect(self.nav_prev.emit)
        self.btn_next.clicked.connect(self.nav_next.emit)
        self.btn_last.clicked.connect(self.nav_last.emit)

        self.layout.addLayout(nav_layout)

    def refresh_styles(self):
        self.table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {Styles.COLOR_SURFACE};
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 8px;
                gridline-color: transparent;
                font-size: 14px;
            }}
            QTableWidget::item {{
                padding: 4px 8px;
                border-bottom: 1px solid {Styles.COLOR_SURFACE_LIGHT};
            }}
            QTableWidget::item:hover {{
                background-color: {Styles.COLOR_SURFACE_LIGHT};
            }}
            QTableWidget::item:selected {{
                background-color: {Styles.COLOR_HIGHLIGHT};
                color: {Styles.COLOR_TEXT_PRIMARY};
                border-left: 3px solid {Styles.COLOR_ACCENT};
            }}
            QHeaderView::section {{
                background-color: {Styles.COLOR_SURFACE_LIGHT};
                color: {Styles.COLOR_TEXT_SECONDARY};
                padding: 6px;
                border: none;
                border-bottom: 2px solid {Styles.COLOR_ACCENT};
                font-weight: 600;
                font-size: 13px;
            }}
        """)
        btn_style = f"""
            QPushButton {{
                background-color: {Styles.COLOR_SURFACE_LIGHT};
                color: {Styles.COLOR_TEXT_PRIMARY};
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 16px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {Styles.COLOR_SURFACE};
                border: 1px solid {Styles.COLOR_ACCENT};
            }}
            QPushButton:pressed {{
                background-color: {Styles.COLOR_ACCENT};
                color: white;
            }}
            QPushButton:disabled {{
                color: {Styles.COLOR_TEXT_MUTED};
                background-color: {Styles.COLOR_SURFACE_LIGHT};
            }}
        """
        for btn in (self.btn_first, self.btn_prev, self.btn_next, self.btn_last):
            btn.setStyleSheet(btn_style)

    def add_move(self, san: str, classification: str = None):
        """Append a new move to the list."""
        # If we are not at the end, truncate the list before adding
        if self.current_index < len(self.moves) - 1:
            self.moves = self.moves[:self.current_index + 1]
            
        self.moves.append({'san': san, 'classification': classification})
        self.current_index = len(self.moves) - 1
        self.refresh()

    def set_index(self, index: int):
        """Navigate to a specific index in the move list."""
        if -1 <= index < len(self.moves):
            self.current_index = index
            self._update_selection()
            self._update_nav_buttons()

    def update_classification(self, index: int, classification: str):
        """Update the classification for a specific move."""
        if 0 <= index < len(self.moves):
            self.moves[index]['classification'] = classification
            self.refresh()

    def set_pending_classification(self, index: int, pending: bool = True):
        """Show/hide a pending classification indicator for a move."""
        if 0 <= index < len(self.moves):
            self.moves[index]['classification'] = "Pending" if pending else None
            self.refresh()

    def refresh(self):
        """Redraw the entire table."""
        self.table.clearContents()
        num_rows = (len(self.moves) + 1) // 2
        self.table.setRowCount(num_rows)

        for i, move_data in enumerate(self.moves):
            row = i // 2
            col = (i % 2) + 1  # 1 for White, 2 for Black

            # Row Number (only in White's column logic)
            if col == 1:
                num_item = QTableWidgetItem(str(row + 1))
                num_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                num_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
                num_item.setForeground(QBrush(QColor(Styles.COLOR_TEXT_SECONDARY)))
                self.table.setItem(row, 0, num_item)

            # Move Item
            item = QTableWidgetItem(move_data['san'])
            item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            item.setData(Qt.ItemDataRole.UserRole, i)
            
            # Icon and Color based on classification
            classification = move_data.get('classification')
            if classification:
                if classification == "Pending":
                    item.setForeground(QBrush(QColor(Styles.COLOR_TEXT_MUTED)))
                    item.setText(f"~ {move_data['san']} ~")
                else:
                    icon = self.resource_manager.get_icon(classification)
                    if not icon.isNull():
                        item.setIcon(icon)
                    color_hex = Styles.get_class_color(classification)
                    if color_hex:
                        item.setForeground(QBrush(QColor(color_hex)))
                    
                    # Make major classifications bold
                    if classification in ("Brilliant", "Blunder", "Mistake", "Miss"):
                        font = item.font()
                        font.setBold(True)
                        item.setFont(font)
            else:
                item.setForeground(QBrush(QColor(Styles.COLOR_TEXT_PRIMARY)))

            self.table.setItem(row, col, item)

        self._update_selection()
        self._update_nav_buttons()

    def _update_selection(self):
        """Highlight the currently selected cell based on current_index."""
        self.table.clearSelection()
        if self.current_index >= 0:
            row = self.current_index // 2
            col = (self.current_index % 2) + 1
            item = self.table.item(row, col)
            if item:
                self.table.setCurrentItem(item)
                self.table.scrollToItem(item)

    def _update_nav_buttons(self):
        has_moves = len(self.moves) > 0
        self.btn_first.setEnabled(has_moves and self.current_index > -1)
        self.btn_prev.setEnabled(has_moves and self.current_index > -1)
        self.btn_next.setEnabled(has_moves and self.current_index < len(self.moves) - 1)
        self.btn_last.setEnabled(has_moves and self.current_index < len(self.moves) - 1)

    def on_cell_clicked(self, row, col):
        item = self.table.item(row, col)
        if item:
            index = item.data(Qt.ItemDataRole.UserRole)
            if index is not None and index != self.current_index:
                self.move_selected.emit(index)

    def clear(self):
        self.moves = []
        self.current_index = -1
        self.refresh()
