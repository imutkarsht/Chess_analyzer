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
        
        # Reduced height for more compact look
        self.figure = Figure(figsize=(5, 2.2), dpi=100)
        self.canvas = FigureCanvas(self.figure)
        self.layout.addWidget(self.canvas)
        self.ax = self.figure.add_subplot(111)
        
        # Initial styling
        self.clear()

    def _get_nice_limit(self, max_val):
        """Returns a nice rounded limit for Y-axis based on max value."""
        if max_val <= 0.5:
            return 0.5
        elif max_val <= 1:
            return 1.0
        elif max_val <= 2:
            return 2.0
        elif max_val <= 3:
            return 3.0
        elif max_val <= 5:
            return 5.0
        else:
            return 10.0

    def plot_game(self, game_analysis):
        self.ax.clear()
        
        # Store evals in pawns (not centipawns) for display
        evals = []  # In pawns (e.g., 1.5 = 1.5 pawns)
        moves = []
        
        # Start with 0 eval at move 0 (start of game)
        evals.append(0)
        moves.append(0)

        for i, move in enumerate(game_analysis.moves):
            val = 0
            if move.eval_after_mate is not None:
                # Cap mate at +/- 10 pawns for visual consistency
                val = 10 if move.eval_after_mate > 0 else -10
            elif move.eval_after_cp is not None:
                # Convert centipawns to pawns
                val = move.eval_after_cp / 100.0
                # Clamp for graph readability to +/- 10 pawns
                val = max(-10, min(10, val))
            
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
            self.ax.scatter(scatter_x, scatter_y, c=scatter_colors, s=40, zorder=3, edgecolors='white', linewidths=1)
        
        # Zero line
        self.ax.axhline(0, color=Styles.COLOR_BORDER, linestyle='--', linewidth=1, zorder=0)
        
        # Styling
        self.ax.set_facecolor(Styles.COLOR_SURFACE)
        self.figure.patch.set_facecolor(Styles.COLOR_SURFACE)

        # ASYMMETRIC Y-axis limits - scale positive and negative independently
        positive_evals = [e for e in evals if e > 0]
        negative_evals = [e for e in evals if e < 0]
        
        max_positive = max(positive_evals) if positive_evals else 0.5
        max_negative = abs(min(negative_evals)) if negative_evals else 0.5
        
        # Get nice rounded limits for each side independently
        upper_limit = self._get_nice_limit(max_positive)
        lower_limit = self._get_nice_limit(max_negative)
        
        # Ensure minimum of 0.5 on each side for visual balance
        upper_limit = max(0.5, upper_limit)
        lower_limit = max(0.5, lower_limit)
        
        self.ax.set_ylim(-lower_limit, upper_limit)
        
        # Generate asymmetric ticks - 2 above zero, 2 below zero (or fewer if limit is small)
        ticks = [0]
        
        # Add positive ticks
        if upper_limit <= 1:
            ticks.extend([t for t in [0.5, 1.0] if t <= upper_limit])
        elif upper_limit <= 2:
            ticks.extend([t for t in [1.0, 2.0] if t <= upper_limit])
        elif upper_limit <= 3:
            ticks.extend([t for t in [1.0, 2.0, 3.0] if t <= upper_limit])
        elif upper_limit <= 5:
            ticks.extend([t for t in [2.0, 5.0] if t <= upper_limit])
        else:
            ticks.extend([5.0, 10.0])
        
        # Add negative ticks
        if lower_limit <= 1:
            ticks.extend([t for t in [-0.5, -1.0] if abs(t) <= lower_limit])
        elif lower_limit <= 2:
            ticks.extend([t for t in [-1.0, -2.0] if abs(t) <= lower_limit])
        elif lower_limit <= 3:
            ticks.extend([t for t in [-1.0, -2.0, -3.0] if abs(t) <= lower_limit])
        elif lower_limit <= 5:
            ticks.extend([t for t in [-2.0, -5.0] if abs(t) <= lower_limit])
        else:
            ticks.extend([-5.0, -10.0])
        
        ticks = sorted(set(ticks))
        self.ax.set_yticks(ticks)
        
        # Format Y-axis labels to show pawn values (like +2, +1, 0, -1, -2)
        def format_tick(val, pos):
            if val == 0:
                return "0"
            elif val == int(val):
                return f"{int(val):+d}"
            else:
                return f"{val:+.1f}"
        
        from matplotlib.ticker import FuncFormatter
        self.ax.yaxis.set_major_formatter(FuncFormatter(format_tick))
        
        # Remove spines/ticks for cleaner look
        self.ax.spines['top'].set_visible(False)
        self.ax.spines['right'].set_visible(False)
        self.ax.spines['bottom'].set_color(Styles.COLOR_BORDER)
        self.ax.spines['left'].set_color(Styles.COLOR_BORDER)
        self.ax.tick_params(axis='x', colors=Styles.COLOR_TEXT_SECONDARY, labelsize=9)
        self.ax.tick_params(axis='y', colors=Styles.COLOR_TEXT_SECONDARY, labelsize=9)
        
        self.ax.set_title("Evaluation", color=Styles.COLOR_TEXT_PRIMARY, fontsize=11, fontweight='600', pad=8)
        
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
                eval_display = f"{val:+.2f}" if val != 0 else "0.00"
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
