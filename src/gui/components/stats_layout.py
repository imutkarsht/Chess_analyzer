"""
StatsLayout: Custom layout to arrange the 4 metric cards adaptively.
"""
from PyQt6.QtWidgets import QLayout
from PyQt6.QtCore import Qt, QSize, QRect

class StatsLayout(QLayout):
    def __init__(self, parent=None, spacing=20):
        super().__init__(parent)
        self._items = []
        self._spacing = spacing
        self.setContentsMargins(0, 0, 0, 0)

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
        if not self._items:
            return 0
            
        margins = self.contentsMargins()
        available_width = width - margins.left() - margins.right()
        spacing = self._spacing
        
        if available_width >= 900:
            cols = 4
        elif available_width >= 500:
            cols = 2
        else:
            cols = 1
            
        rows = (len(self._items) + cols - 1) // cols
        
        total_height = 0
        for r in range(rows):
            max_h = 0
            for c in range(cols):
                idx = r * cols + c
                if idx < len(self._items):
                    max_h = max(max_h, self._items[idx].sizeHint().height())
            total_height += max_h
            
        if rows > 1:
            total_height += (rows - 1) * spacing
            
        return total_height + margins.top() + margins.bottom()

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self.doLayout(rect)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        size += QSize(margins.left() + margins.right(), margins.top() + margins.bottom())
        return size

    def doLayout(self, rect):
        if not self._items:
            return
            
        margins = self.contentsMargins()
        spacing = self._spacing
        available_width = rect.width() - margins.left() - margins.right()
        
        if available_width >= 900:
            cols = 4
        elif available_width >= 500:
            cols = 2
        else:
            cols = 1
            
        item_w = (available_width - (cols - 1) * spacing) // cols
        
        # Calculate Y start for each row
        row_heights = []
        rows = (len(self._items) + cols - 1) // cols
        for r in range(rows):
            max_h = 0
            for c in range(cols):
                idx = r * cols + c
                if idx < len(self._items):
                    max_h = max(max_h, self._items[idx].sizeHint().height())
            row_heights.append(max_h)

        row_y = [rect.y() + margins.top()]
        for r in range(1, rows):
            row_y.append(row_y[-1] + row_heights[r-1] + spacing)

        for idx, item in enumerate(self._items):
            r = idx // cols
            c = idx % cols
            
            x = rect.x() + margins.left() + c * (item_w + spacing)
            y = row_y[r]
            
            item.setGeometry(QRect(x, y, item_w, row_heights[r]))
