"""
MasonryLayout: Custom QLayout for dynamic, space-efficient column packing.
"""
from PyQt6.QtWidgets import QLayout
from PyQt6.QtCore import Qt, QRect, QSize

class MasonryLayout(QLayout):
    def __init__(self, parent=None, margin=40, spacing=25):
        super().__init__(parent)
        self._items = []
        self._spacing = spacing
        self.setContentsMargins(margin, margin, margin, margin)

    def __del__(self):
        item = self.takeAt(0)
        while item:
            item = self.takeAt(0)

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, index):
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self.doLayout(QRect(0, 0, width, 0), True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self.doLayout(rect, False)

    def sizeHint(self):
        parent = self.parentWidget()
        if parent:
            width = parent.width()
            if width > 100:
                height = self.heightForWidth(width)
                return QSize(width, height)
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        size += QSize(margins.left() + margins.right(), margins.top() + margins.bottom())
        return size

    def doLayout(self, rect, test_only):
        margins = self.contentsMargins()
        spacing = self._spacing
        
        available_width = rect.width() - margins.left() - margins.right()
        
        # We want columns to be at least 340px wide
        min_col_width = 340
        num_cols = max(1, available_width // min_col_width)
        num_cols = min(2, num_cols)
        
        if num_cols > 1:
            col_width = (available_width - (num_cols - 1) * spacing) // num_cols
        else:
            col_width = available_width

        col_heights = [rect.y() + margins.top()] * num_cols

        for item in self._items:
            widget = item.widget()
            if widget and not widget.isVisible():
                continue

            min_col_idx = col_heights.index(min(col_heights))
            
            x = rect.x() + margins.left() + min_col_idx * (col_width + spacing)
            y = col_heights[min_col_idx]
            
            h = item.heightForWidth(col_width) if item.hasHeightForWidth() else item.sizeHint().height()
            
            if not test_only:
                item.setGeometry(QRect(x, y, col_width, h))
                
            col_heights[min_col_idx] = y + h + spacing

        if col_heights:
            max_height = max(col_heights) - spacing + margins.bottom()
        else:
            max_height = rect.y() + margins.top() + margins.bottom()
            
        return max_height - rect.y()
