from PyQt6.QtWidgets import QWidget, QVBoxLayout
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
from .styles import Styles

class GraphWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        self.figure = Figure(figsize=(5, 3), dpi=100)
        self.canvas = FigureCanvas(self.figure)
        self.layout.addWidget(self.canvas)
        self.ax = self.figure.add_subplot(111)
        
        # Initial styling
        self.clear()

    def plot_game(self, game_analysis):
        self.ax.clear()
        
        evals = []
        moves = []
        
        # Start with 0 eval at move 0 (start of game)
        evals.append(0)
        moves.append(0)

        for i, move in enumerate(game_analysis.moves):
            val = 0
            if move.eval_after_mate is not None:
                # Cap mate at +/- 1500
                val = 1500 if move.eval_after_mate > 0 else -1500
            elif move.eval_after_cp is not None:
                val = move.eval_after_cp
                # Clamp for graph readability
                val = max(-1500, min(1500, val))
            
            evals.append(val)
            moves.append(i + 1)
            
        # Plot line
        self.ax.plot(moves, evals, color=Styles.COLOR_TEXT_PRIMARY, linewidth=1.5)
        
        # Fill area
        # Positive (White advantage) -> White fill
        self.ax.fill_between(moves, evals, 0, where=[e >= 0 for e in evals], 
                             facecolor='#FFFFFF', alpha=0.2, interpolate=True)
        # Negative (Black advantage) -> Black/Grey fill
        self.ax.fill_between(moves, evals, 0, where=[e < 0 for e in evals], 
                             facecolor='#000000', alpha=0.4, interpolate=True)
        
        # Zero line
        self.ax.axhline(0, color=Styles.COLOR_BORDER, linestyle='--', linewidth=1)
        
        # Styling
        self.ax.set_facecolor(Styles.COLOR_SURFACE)
        self.figure.patch.set_facecolor(Styles.COLOR_SURFACE)
        
        # Remove spines/ticks for cleaner look
        self.ax.spines['top'].set_visible(False)
        self.ax.spines['right'].set_visible(False)
        self.ax.spines['bottom'].set_color(Styles.COLOR_BORDER)
        self.ax.spines['left'].set_color(Styles.COLOR_BORDER)
        self.ax.tick_params(axis='x', colors=Styles.COLOR_TEXT_SECONDARY)
        self.ax.tick_params(axis='y', colors=Styles.COLOR_TEXT_SECONDARY)
        
        self.ax.set_title("Evaluation", color=Styles.COLOR_TEXT_PRIMARY, pad=10)
        
        self.canvas.draw()

    def clear(self):
        self.ax.clear()
        self.ax.set_facecolor(Styles.COLOR_SURFACE)
        self.figure.patch.set_facecolor(Styles.COLOR_SURFACE)
        self.ax.spines['top'].set_visible(False)
        self.ax.spines['right'].set_visible(False)
        self.ax.spines['bottom'].set_color(Styles.COLOR_BORDER)
        self.ax.spines['left'].set_color(Styles.COLOR_BORDER)
        self.ax.tick_params(axis='x', colors=Styles.COLOR_TEXT_SECONDARY)
        self.ax.tick_params(axis='y', colors=Styles.COLOR_TEXT_SECONDARY)
        self.canvas.draw()
