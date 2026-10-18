"""
Drill-down explorer view for detailed position-level inspection of stats.
Contains a navigation header with a '< Back to Dashboard' button,
occurrence count badge, paginated card list of positions, and smooth selection dispatch.
"""

from __future__ import annotations

from typing import Any

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from src.gui.metrics.drill_down_item import DrillDownItemWidget
from src.gui.styles import Styles

try:
    import qtawesome as qta

    HAS_QTAWESOME = True
except ImportError:
    HAS_QTAWESOME = False


class DrillDownView(QWidget):
    """
    Explorer view showing game positions and moves from which a specific stat was calculated.
    """

    back_requested = pyqtSignal()
    position_selected = pyqtSignal(str, int)  # (game_id, move_index)

    PAGE_SIZE = 10

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.title_text: str = "Drill-Down"
        self.subtitle_text: str = ""
        self.items: list[dict[str, Any]] = []
        self.current_page: int = 0

        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"background-color: {Styles.COLOR_BACKGROUND};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 1. Top Navigation Header Bar
        self.header_bar = QFrame()
        self.header_bar.setStyleSheet(f"""
            QFrame {{
                background-color: {Styles.COLOR_BACKGROUND};
                border-bottom: 1px solid {Styles.COLOR_BORDER};
            }}
        """)
        header_layout = QHBoxLayout(self.header_bar)
        header_layout.setContentsMargins(24, 14, 24, 14)
        header_layout.setSpacing(14)

        # Back Button
        self.btn_back = QPushButton(" Back to Dashboard")
        self.btn_back.setCursor(Qt.CursorShape.PointingHandCursor)
        if HAS_QTAWESOME:
            self.btn_back.setIcon(qta.icon("fa5s.arrow-left", color=Styles.COLOR_TEXT_PRIMARY))
        self.btn_back.setStyleSheet(f"""
            QPushButton {{
                background-color: {Styles.COLOR_SURFACE};
                color: {Styles.COLOR_TEXT_PRIMARY};
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 8px;
                padding: 7px 16px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {Styles.COLOR_SURFACE_LIGHT};
                border-color: {Styles.COLOR_ACCENT};
                color: {Styles.COLOR_ACCENT};
            }}
        """)
        self.btn_back.clicked.connect(self.back_requested.emit)
        header_layout.addWidget(self.btn_back)

        # Vertical Divider
        self.sep = QFrame()
        self.sep.setFrameShape(QFrame.Shape.VLine)
        self.sep.setFrameShadow(QFrame.Shadow.Plain)
        self.sep.setStyleSheet(f"background-color: {Styles.COLOR_BORDER}; border: none;")
        self.sep.setFixedWidth(1)
        self.sep.setFixedHeight(24)
        header_layout.addWidget(self.sep)

        # Title & Subtitle
        title_vbox = QVBoxLayout()
        title_vbox.setSpacing(2)
        title_vbox.setContentsMargins(0, 0, 0, 0)

        self.lbl_title = QLabel(self.title_text)
        self.lbl_title.setStyleSheet(
            Styles.get_label_style(size=20, color=Styles.COLOR_TEXT_PRIMARY, bold=True)
            + " "
            + Styles.get_transparent_label_style()
        )
        title_vbox.addWidget(self.lbl_title)

        self.lbl_subtitle = QLabel(self.subtitle_text)
        self.lbl_subtitle.setStyleSheet(
            Styles.get_label_style(size=12, color=Styles.COLOR_TEXT_SECONDARY)
            + " "
            + Styles.get_transparent_label_style()
        )
        title_vbox.addWidget(self.lbl_subtitle)

        header_layout.addLayout(title_vbox, 1)

        # Occurrences Count Badge
        self.badge_count = QLabel("0 Occurrences")
        self.badge_count.setStyleSheet(f"""
            QLabel {{
                background-color: {Styles.COLOR_SURFACE};
                color: {Styles.COLOR_ACCENT};
                font-size: 12px;
                font-weight: 700;
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 12px;
                padding: 5px 14px;
            }}
        """)
        header_layout.addWidget(self.badge_count)

        layout.addWidget(self.header_bar)

        # 2. Main Content Area (Scrollable)
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setStyleSheet(Styles.get_transparent_scroll_area_style())
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.list_container = QWidget()
        self.list_container.setStyleSheet(f"background-color: {Styles.COLOR_BACKGROUND};")
        self.list_layout = QVBoxLayout(self.list_container)
        self.list_layout.setContentsMargins(24, 16, 24, 24)
        self.list_layout.setSpacing(12)

        self.scroll_area.setWidget(self.list_container)
        layout.addWidget(self.scroll_area, 1)

        # 3. Pagination Bar
        self.pagination_bar = QFrame()
        self.pagination_bar.setStyleSheet(f"""
            QFrame {{
                background-color: {Styles.COLOR_BACKGROUND};
                border-top: 1px solid {Styles.COLOR_BORDER};
            }}
        """)
        pag_layout = QHBoxLayout(self.pagination_bar)
        pag_layout.setContentsMargins(24, 10, 24, 10)
        pag_layout.setSpacing(10)

        self.btn_prev = QPushButton("Previous")
        self.btn_prev.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_prev.clicked.connect(self._prev_page)

        self.lbl_page = QLabel("Page 1 of 1")
        self.lbl_page.setStyleSheet(
            Styles.get_label_style(size=12, color=Styles.COLOR_TEXT_SECONDARY)
            + " "
            + Styles.get_transparent_label_style()
        )

        self.btn_next = QPushButton("Next")
        self.btn_next.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_next.clicked.connect(self._next_page)

        btn_style = f"""
            QPushButton {{
                color: {Styles.COLOR_TEXT_PRIMARY};
                background-color: {Styles.COLOR_SURFACE};
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 6px;
                padding: 4px 14px;
                font-size: 12px;
                font-weight: 600;
            }}
            QPushButton:hover:enabled {{
                background-color: {Styles.COLOR_SURFACE_LIGHT};
                border-color: {Styles.COLOR_BORDER_LIGHT};
            }}
            QPushButton:disabled {{
                color: {Styles.COLOR_TEXT_MUTED};
                background-color: transparent;
                border-color: transparent;
            }}
        """
        self.btn_prev.setStyleSheet(btn_style)
        self.btn_next.setStyleSheet(btn_style)

        pag_layout.addWidget(self.btn_prev)
        pag_layout.addStretch()
        pag_layout.addWidget(self.lbl_page)
        pag_layout.addStretch()
        pag_layout.addWidget(self.btn_next)

        layout.addWidget(self.pagination_bar)

    def set_data(self, title: str, subtitle: str, items: list[dict[str, Any]]) -> None:
        """Loads items for drill-down and renders the first page."""
        self.title_text = title
        self.subtitle_text = subtitle
        self.items = items or []
        self.current_page = 0

        self.lbl_title.setText(self.title_text)
        self.lbl_subtitle.setText(self.subtitle_text)

        count = len(self.items)
        occ_text = f"{count} Occurrence" if count == 1 else f"{count} Occurrences"
        self.badge_count.setText(occ_text)

        self._render_page()

    def _render_page(self) -> None:
        # Clear existing items in list_layout
        while self.list_layout.count() > 0:
            child = self.list_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        if not self.items:
            self._render_empty_state()
            self.pagination_bar.setVisible(False)
            return

        total_pages = max(1, (len(self.items) + self.PAGE_SIZE - 1) // self.PAGE_SIZE)
        self.current_page = max(0, min(self.current_page, total_pages - 1))

        start_idx = self.current_page * self.PAGE_SIZE
        end_idx = min(start_idx + self.PAGE_SIZE, len(self.items))
        page_items = self.items[start_idx:end_idx]

        for item in page_items:
            widget = DrillDownItemWidget(item)
            widget.position_selected.connect(self.position_selected.emit)
            self.list_layout.addWidget(widget)

        self.list_layout.addStretch(1)

        # Update pagination controls
        if total_pages > 1:
            self.pagination_bar.setVisible(True)
            self.lbl_page.setText(
                f"Page {self.current_page + 1} of {total_pages} ({len(self.items)} total)"
            )
            self.btn_prev.setEnabled(self.current_page > 0)
            self.btn_next.setEnabled(self.current_page < total_pages - 1)
        else:
            self.pagination_bar.setVisible(False)

        # Reset scroll to top
        self.scroll_area.verticalScrollBar().setValue(0)

    def _render_empty_state(self) -> None:
        empty_container = QWidget()
        empty_container.setStyleSheet(Styles.get_transparent_label_style())
        empty_layout = QVBoxLayout(empty_container)
        empty_layout.setContentsMargins(0, 40, 0, 40)
        empty_layout.setSpacing(12)
        empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        icon_lbl = QLabel()
        if HAS_QTAWESOME:
            icon_lbl.setPixmap(
                qta.icon("fa5s.search", color=Styles.COLOR_TEXT_MUTED).pixmap(48, 48)
            )
        else:
            icon_lbl.setText("🔍")
            icon_lbl.setStyleSheet("font-size: 36px;")
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(icon_lbl)

        title_lbl = QLabel("No Occurrences Found")
        title_lbl.setStyleSheet(
            Styles.get_label_style(size=16, color=Styles.COLOR_TEXT_PRIMARY, bold=True)
        )
        title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(title_lbl)

        sub_lbl = QLabel("No matching game positions recorded under the current filters.")
        sub_lbl.setStyleSheet(Styles.get_label_style(size=12, color=Styles.COLOR_TEXT_MUTED))
        sub_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(sub_lbl)

        self.list_layout.addWidget(empty_container)

    def _prev_page(self) -> None:
        if self.current_page > 0:
            self.current_page -= 1
            self._render_page()

    def _next_page(self) -> None:
        total_pages = max(1, (len(self.items) + self.PAGE_SIZE - 1) // self.PAGE_SIZE)
        if self.current_page < total_pages - 1:
            self.current_page += 1
            self._render_page()

    def refresh_styles(self) -> None:
        """Re-applies styles when theme changes."""
        self.setStyleSheet(f"background-color: {Styles.COLOR_BACKGROUND};")
        self.header_bar.setStyleSheet(f"""
            QFrame {{
                background-color: {Styles.COLOR_BACKGROUND};
                border-bottom: 1px solid {Styles.COLOR_BORDER};
            }}
        """)
        self.sep.setStyleSheet(f"background-color: {Styles.COLOR_BORDER}; border: none;")
        self.btn_back.setStyleSheet(f"""
            QPushButton {{
                background-color: {Styles.COLOR_SURFACE};
                color: {Styles.COLOR_TEXT_PRIMARY};
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 8px;
                padding: 7px 16px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {Styles.COLOR_SURFACE_LIGHT};
                border-color: {Styles.COLOR_ACCENT};
                color: {Styles.COLOR_ACCENT};
            }}
        """)
        self.badge_count.setStyleSheet(f"""
            QLabel {{
                background-color: {Styles.COLOR_SURFACE};
                color: {Styles.COLOR_ACCENT};
                font-size: 12px;
                font-weight: 700;
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 12px;
                padding: 5px 14px;
            }}
        """)
        self.list_container.setStyleSheet(f"background-color: {Styles.COLOR_BACKGROUND};")
        self.pagination_bar.setStyleSheet(f"""
            QFrame {{
                background-color: {Styles.COLOR_BACKGROUND};
                border-top: 1px solid {Styles.COLOR_BORDER};
            }}
        """)
        self._render_page()
