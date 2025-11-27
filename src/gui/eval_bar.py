from PyQt6.QtWidgets import QWidget
from PyQt6.QtGui import QPainter, QColor, QBrush, QLinearGradient
from PyQt6.QtCore import Qt, QTimer
from .styles import Styles

class EvalBarWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedWidth(24) 
        self.cp = 0.0
        self.target_cp = 0.0
        self.mate = None # None, positive int (White mate), negative int (Black mate)
        
        # Animation
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.animate)
        self.timer.start(16) # ~60 FPS
        
    def set_eval(self, cp=None, mate=None):
        self.target_cp = cp if cp is not None else 0.0
        self.mate = mate
        # If mate, snap immediately (or handle mate animation differently)
        if mate is not None:
            self.cp = self.target_cp # Not used for mate logic but good to sync
        
        self.update() # Trigger repaint
        
    def animate(self):
        if self.mate is not None:
            return # No animation for mate yet
            
        diff = self.target_cp - self.cp
        if abs(diff) < 1:
            self.cp = self.target_cp
        else:
            # Simple lerp
            self.cp += diff * 0.1
            self.update()
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        width = self.width()
        height = self.height()
        
        # Background (Black/Dark Grey)
        painter.fillRect(0, 0, width, height, QColor("#404040"))
        
        # Calculate White's height percentage
        white_pct = 0.5
        
        if self.mate is not None:
            if self.mate > 0:
                white_pct = 1.0 # White wins
            else:
                white_pct = 0.0 # Black wins
        else:
            # Sigmoid-like scaling for CP
            # Using a simple clamp for now: +/- 400 (4 pawns) = 100% advantage visually?
            clamped_cp = max(-1000, min(1000, self.cp))
            # Map -1000..1000 to 0..1
            white_pct = (clamped_cp + 1000) / 2000
            
        # Draw White bar
        white_height = height * white_pct
        white_top = height - white_height
        
        # Draw Black part (top)
        painter.fillRect(0, 0, width, int(white_top), QColor("#404040"))
        
        # Draw White part (bottom)
        painter.fillRect(0, int(white_top), width, int(white_height), QColor("#FFFFFF"))
        
        # Draw numeric label if space permits
        if height > 50:
             font = painter.font()
             font.setPixelSize(10)
             font.setBold(True)
             painter.setFont(font)
             
             label_text = ""
             if self.mate is not None:
                 label_text = f"M{abs(self.mate)}"
             else:
                 label_text = f"{abs(self.cp) / 100:.1f}"
                 
             # Text color depends on background
             if white_pct > 0.5:
                 # White is winning, bar is high. Put text in the black area (top) if possible, or white area (bottom)
                 # Let's put it at the bottom (white area) with black text
                 painter.setPen(QColor("#404040"))
                 painter.drawText(0, height - 5, width, 20, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom, label_text)
             else:
                 # Black is winning. Put text at top (black area) with white text
                 painter.setPen(QColor("#FFFFFF"))
                 painter.drawText(0, 5, width, 20, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, label_text)
