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
                # Cap mate at +/- 200 (2.00) for visual consistency with CP
                val = 200 if move.eval_after_mate > 0 else -200
            elif move.eval_after_cp is not None:
                val = move.eval_after_cp
                # Clamp for graph readability to +/- 200 (2.00)
                val = max(-200, min(200, val))
            
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
        
        special_moves = ["Brilliant", "Great", "Miss", "Mistake", "Blunder"]
        
        for i, move in enumerate(game_analysis.moves):
            if move.classification and move.classification in special_moves:
                color = Styles.get_class_color(move.classification)
                if color:
                    scatter_x.append(i + 1)
                    scatter_y.append(evals[i+1]) # evals has one extra element at start
                    scatter_colors.append(color)
        
        if scatter_x:
            self.ax.scatter(scatter_x, scatter_y, c=scatter_colors, s=50, zorder=3, edgecolors='white', linewidths=1.2)
        
        # Zero line
        self.ax.axhline(0, color=Styles.COLOR_BORDER, linestyle='--', linewidth=1, zorder=0)
        
        # Styling
        self.ax.set_facecolor(Styles.COLOR_SURFACE)
        self.figure.patch.set_facecolor(Styles.COLOR_SURFACE)

        max_val = 0
        if evals:
             max_val = max(abs(e) for e in evals)
        
        # Floor at 100 (1.00) so we don't zoom in too much on empty/drawish games
        limit = max(100, max_val)
        
        # Cap at 200 (2.00) as requested
        limit = min(200, limit)
        
        self.ax.set_ylim(-limit, limit)
        
        # Remove spines/ticks for cleaner look
        self.ax.spines['top'].set_visible(False)
        self.ax.spines['right'].set_visible(False)
        self.ax.spines['bottom'].set_color(Styles.COLOR_BORDER)
        self.ax.spines['left'].set_color(Styles.COLOR_BORDER)
        self.ax.tick_params(axis='x', colors=Styles.COLOR_TEXT_SECONDARY)
        self.ax.tick_params(axis='y', colors=Styles.COLOR_TEXT_SECONDARY)
        
        self.ax.set_title("Evaluation", color=Styles.COLOR_TEXT_PRIMARY, fontsize=13, fontweight='600', pad=12)
        
        # Current move indicator line (initially hidden)
        self.current_move_line = self.ax.axvline(x=-1, color=Styles.COLOR_ACCENT, linewidth=2, linestyle='-', alpha=0.8, zorder=4)
        self.current_move_line.set_visible(False)
        
        self.canvas.draw()
        
        # Store data for tooltips
        self.moves_data = moves
        self.evals_data = evals
        
        # Annotation for tooltip
        self.annot = self.ax.annotate("", xy=(0, 0), xytext=(10, 10), textcoords="offset points",
                            bbox=dict(boxstyle="round,pad=0.4", fc=Styles.COLOR_SURFACE_LIGHT, ec=Styles.COLOR_BORDER, alpha=0.95),
                            color=Styles.COLOR_TEXT_PRIMARY,
                            fontsize=11,
                            arrowprops=dict(arrowstyle="->", color=Styles.COLOR_TEXT_SECONDARY))
        self.annot.set_visible(False)
        
        self.canvas.mpl_connect("motion_notify_event", self.on_hover)

    def set_current_move(self, move_index):
        """Updates the current move indicator line on the chart."""
        if not hasattr(self, 'current_move_line') or self.current_move_line is None:
            return
            
        if move_index < 0:
            self.current_move_line.set_visible(False)
        else:
            # move_index 0 = first move = x position 1 on chart
            self.current_move_line.set_xdata([move_index + 1, move_index + 1])
            self.current_move_line.set_visible(True)
        
        self.canvas.draw_idle()

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
                eval_display = f"{val/100:+.2f}" if val != 0 else "0.00"
                self.annot.set_text(f"Move {move_num}\n{eval_display}")
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
        self.current_move_line = None
        self.canvas.draw()
