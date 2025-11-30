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
                # Cap mate at +/- 3000 (visual)
                val = 3000 if move.eval_after_mate > 0 else -3000
            elif move.eval_after_cp is not None:
                val = move.eval_after_cp
                # Clamp for graph readability (e.g. +/- 1500 is fine, but view might be zoomed)
                # We will set ylim later.
                pass
            
            evals.append(val)
            moves.append(i + 1)
            
        # Plot line
        self.ax.plot(moves, evals, color=Styles.COLOR_TEXT_PRIMARY, linewidth=1.5, zorder=1)
        
        # Fill area
        # Positive (White advantage) -> White fill
        self.ax.fill_between(moves, evals, 0, where=[e >= 0 for e in evals], 
                             facecolor='#FFFFFF', alpha=0.2, interpolate=True, zorder=0)
        # Negative (Black advantage) -> Black/Grey fill
        self.ax.fill_between(moves, evals, 0, where=[e < 0 for e in evals], 
                             facecolor='#000000', alpha=0.4, interpolate=True, zorder=0)
        
        # Scatter plot for move classifications
        scatter_x = []
        scatter_y = []
        scatter_colors = []
        
        # We need to align moves with classifications.
        # game_analysis.moves[i] corresponds to move i+1
        # moves array has 0 (start) then 1..N
        # evals array has 0 (start) then 1..N
        
        # Filter classifications for scatter plot
        # Only show: Brilliant, Great, Best, Miss, Mistake, Blunder
        # Maybe skip "Good", "Excellent", "Book", "Inaccuracy" to reduce clutter?
        # User asked to "only highlight special moves on graph like ( brilliant, great, miss , mistake and blunders)"
        special_moves = ["Brilliant", "Great", "Miss", "Mistake", "Blunder"]
        
        for i, move in enumerate(game_analysis.moves):
            if move.classification and move.classification in special_moves:
                color = Styles.get_class_color(move.classification)
                if color:
                    scatter_x.append(i + 1)
                    scatter_y.append(evals[i+1]) # evals has one extra element at start
                    scatter_colors.append(color)
        
        if scatter_x:
            self.ax.scatter(scatter_x, scatter_y, c=scatter_colors, s=40, zorder=3, edgecolors='white', linewidths=1.0)
        
        # Zero line
        self.ax.axhline(0, color=Styles.COLOR_BORDER, linestyle='--', linewidth=1, zorder=0)
        
        # Styling
        self.ax.set_facecolor(Styles.COLOR_SURFACE)
        self.figure.patch.set_facecolor(Styles.COLOR_SURFACE)
        
        # Set Y-axis limits to focus on normal play (e.g. +/- 3 pawns = +/- 300 cp)
        # But we also want to see spikes.
        # Maybe dynamic? Or fixed as requested "upto 3 nodes on top and 3 below only" -> implies +/- 3.
        # Let's try +/- 400 CP (4 pawns) to give a bit of room, or strict +/- 300.
        self.ax.set_ylim(-400, 400)
        
        # Remove spines/ticks for cleaner look
        self.ax.spines['top'].set_visible(False)
        self.ax.spines['right'].set_visible(False)
        self.ax.spines['bottom'].set_color(Styles.COLOR_BORDER)
        self.ax.spines['left'].set_color(Styles.COLOR_BORDER)
        self.ax.tick_params(axis='x', colors=Styles.COLOR_TEXT_SECONDARY)
        self.ax.tick_params(axis='y', colors=Styles.COLOR_TEXT_SECONDARY)
        
        self.ax.set_title("Evaluation", color=Styles.COLOR_TEXT_PRIMARY, pad=10)
        
        self.canvas.draw()
        
        # Store data for tooltips
        self.moves_data = moves
        self.evals_data = evals
        
        # Annotation for tooltip
        self.annot = self.ax.annotate("", xy=(0,0), xytext=(10,10), textcoords="offset points",
                            bbox=dict(boxstyle="round", fc=Styles.COLOR_SURFACE_LIGHT, ec=Styles.COLOR_BORDER, alpha=0.9),
                            color=Styles.COLOR_TEXT_PRIMARY,
                            arrowprops=dict(arrowstyle="->", color=Styles.COLOR_TEXT_PRIMARY))
        self.annot.set_visible(False)
        
        self.canvas.mpl_connect("motion_notify_event", self.on_hover)

    def on_hover(self, event):
        if event.inaxes == self.ax:
            # Find closest point
            x = event.xdata
            if x is not None and hasattr(self, 'moves_data'):
                # Find index of closest move
                idx = min(range(len(self.moves_data)), key=lambda i: abs(self.moves_data[i] - x))
                
                move_num = self.moves_data[idx]
                val = self.evals_data[idx]
                
                self.annot.xy = (move_num, val)
                self.annot.set_text(f"Move: {move_num}\nEval: {val/100:.2f}")
                self.annot.set_visible(True)
                self.canvas.draw_idle()
        else:
            if hasattr(self, 'annot') and self.annot.get_visible():
                self.annot.set_visible(False)
                self.canvas.draw_idle()

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
