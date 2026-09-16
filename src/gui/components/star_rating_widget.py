"""
Interactive 5-star rating widget for reviews and feedback.
"""
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton
from PyQt6.QtCore import pyqtSignal, Qt, QSize
from PyQt6.QtGui import QCursor

from src.gui.styles import Styles

try:
    import qtawesome as qta
    HAS_QTAWESOME = True
except ImportError:
    HAS_QTAWESOME = False

STAR_LABELS = {
    0: "Select a rating",
    1: "Needs Improvement",
    2: "Fair",
    3: "Good",
    4: "Very Good!",
    5: "Loved it! 🎉"
}

STAR_COLOR_ACTIVE = "#FFB800"
STAR_COLOR_INACTIVE = "#4B5563"


class StarRatingWidget(QWidget):
    rating_changed = pyqtSignal(int)

    def __init__(self, parent=None, initial_rating=0, star_size=32, show_label=True):
        super().__init__(parent)
        self._rating = initial_rating
        self._hover_rating = 0
        self._star_size = star_size
        self._show_label = show_label
        self._star_buttons = []

        self.setup_ui()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(6)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Stars row
        stars_container = QWidget()
        stars_layout = QHBoxLayout(stars_container)
        stars_layout.setContentsMargins(0, 0, 0, 0)
        stars_layout.setSpacing(8)
        stars_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        for i in range(1, 6):
            btn = QPushButton()
            btn.setFixedSize(self._star_size + 12, self._star_size + 12)
            btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            btn.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    border: none;
                    padding: 0px;
                }
                QPushButton:hover {
                    background: rgba(255, 184, 0, 0.1);
                    border-radius: 6px;
                }
            """)
            btn.setProperty("star_index", i)
            btn.clicked.connect(lambda checked, idx=i: self._on_star_clicked(idx))
            
            # Install hover tracking
            btn.enterEvent = lambda event, idx=i: self._on_star_hover(idx)
            
            stars_layout.addWidget(btn)
            self._star_buttons.append(btn)

        main_layout.addWidget(stars_container)

        # Descriptive text label
        if self._show_label:
            self._desc_label = QLabel(STAR_LABELS.get(self._rating, "Select a rating"))
            self._desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._desc_label.setStyleSheet(f"""
                font-size: 13px;
                font-weight: 600;
                color: {Styles.COLOR_TEXT_SECONDARY};
                background: transparent;
            """)
            main_layout.addWidget(self._desc_label)

        self.leaveEvent = self._on_leave
        self._update_stars()

    def _on_star_clicked(self, index: int):
        self._rating = index
        self._hover_rating = 0
        self._update_stars()
        self.rating_changed.emit(self._rating)

    def _on_star_hover(self, index: int):
        self._hover_rating = index
        self._update_stars()

    def _on_leave(self, event):
        self._hover_rating = 0
        self._update_stars()

    def _update_stars(self):
        active_stars = self._hover_rating if self._hover_rating > 0 else self._rating

        for i, btn in enumerate(self._star_buttons, 1):
            is_lit = (i <= active_stars)
            color = STAR_COLOR_ACTIVE if is_lit else STAR_COLOR_INACTIVE

            if HAS_QTAWESOME:
                btn.setIcon(qta.icon("fa5s.star", color=color))
                btn.setIconSize(QSize(self._star_size, self._star_size))
            else:
                btn.setText("★" if is_lit else "☆")
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: transparent;
                        border: none;
                        font-size: {self._star_size - 4}px;
                        color: {color};
                    }}
                """)

        if self._show_label and hasattr(self, "_desc_label"):
            label_idx = active_stars
            self._desc_label.setText(STAR_LABELS.get(label_idx, ""))
            if label_idx > 0:
                self._desc_label.setStyleSheet(f"""
                    font-size: 13px;
                    font-weight: 600;
                    color: {Styles.COLOR_ACCENT if label_idx >= 4 else Styles.COLOR_TEXT_PRIMARY};
                    background: transparent;
                """)
            else:
                self._desc_label.setStyleSheet(f"""
                    font-size: 13px;
                    font-weight: 600;
                    color: {Styles.COLOR_TEXT_SECONDARY};
                    background: transparent;
                """)

    def set_rating(self, rating: int):
        self._rating = max(0, min(5, int(rating)))
        self._hover_rating = 0
        self._update_stars()

    def get_rating(self) -> int:
        return self._rating
