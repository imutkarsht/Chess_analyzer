from PyQt6.QtWidgets import QWidget, QVBoxLayout
from PyQt6.QtCore import pyqtSignal
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
from src.gui.styles import Styles

class GraphWidget(QWidget):
    move_clicked = pyqtSignal(int)

    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)

        self.figure = Figure(figsize=(5, 2.2), dpi=100)
        self.canvas = FigureCanvas(self.figure)
        self.layout.addWidget(self.canvas)
        self.ax = self.figure.add_subplot(111)

        self.setFixedHeight(int(self.figure.get_figheight() * self.figure.get_dpi()))

        self.clear()

    def _get_nice_limit(self, max_val):
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

    def _build_eval_data(self, moves, up_to_index=None):
        """Build eval and move arrays from moves list, up to the given index."""
        evals = [0]
        move_nums = [0]
        max_idx = len(moves) - 1 if up_to_index is None else min(up_to_index, len(moves) - 1)
        for i in range(max_idx + 1):
            move = moves[i]
            val = 0
            if move.eval_after_mate is not None:
                val = 10 if move.eval_after_mate > 0 else -10
            elif move.eval_after_cp is not None:
                val = move.eval_after_cp / 100.0
                val = max(-10, min(10, val))
            evals.append(val)
            move_nums.append(i + 1)
        return move_nums, evals

    def plot_partial(self, moves, up_to_index):
        """Plot the evaluation graph using moves data up to up_to_index."""
        self.ax.clear()
        move_nums, evals = self._build_eval_data(moves, up_to_index)
        self._render_plot(move_nums, evals, moves)

    def plot_game(self, game_analysis):
        """Full game plot - plots all moves."""
        self.ax.clear()
        move_nums, evals = self._build_eval_data(game_analysis.moves)
        self._render_plot(move_nums, evals, game_analysis.moves)

    def _render_plot(self, move_nums, evals, all_moves):
        """Render the plot with the given data arrays."""
        accent = Styles.COLOR_ACCENT

        self.ax.plot(move_nums, evals, color=accent, linewidth=1.5, zorder=1)

        if len(evals) > 1:
            self.ax.fill_between(move_nums, evals, 0, where=[e >= 0 for e in evals],
                                 facecolor=accent, alpha=0.15, interpolate=True, zorder=0)
            self.ax.fill_between(move_nums, evals, 0, where=[e < 0 for e in evals],
                                 facecolor=accent, alpha=0.30, interpolate=True, zorder=0)

        special_moves = ["Brilliant", "Great", "Miss", "Mistake", "Blunder"]
        scatter_x = []
        scatter_y = []
        scatter_colors = []

        for i, move in enumerate(all_moves):
            if i < len(evals) - 1 and move.classification and move.classification in special_moves:
                color = Styles.get_class_color(move.classification)
                if color:
                    scatter_x.append(i + 1)
                    scatter_y.append(evals[i + 1])
                    scatter_colors.append(color)

        if scatter_x:
            self.ax.scatter(scatter_x, scatter_y, c=scatter_colors, s=40, zorder=3,
                            edgecolors='white', linewidths=1)

        zero_line = self.ax.axhline(0, color=Styles.COLOR_BORDER, linestyle='--', linewidth=1, zorder=0)
        zero_line._is_zero_line = True

        self.ax.set_facecolor(Styles.COLOR_SURFACE)
        self.figure.patch.set_facecolor(Styles.COLOR_SURFACE)

        positive_evals = [e for e in evals if e > 0]
        negative_evals = [e for e in evals if e < 0]
        max_positive = max(positive_evals) if positive_evals else 0.5
        max_negative = abs(min(negative_evals)) if negative_evals else 0.5

        upper_limit = self._get_nice_limit(max_positive)
        lower_limit = self._get_nice_limit(max_negative)
        upper_limit = max(0.5, upper_limit)
        lower_limit = max(0.5, lower_limit)

        self.ax.set_ylim(-lower_limit, upper_limit)

        ticks = [0]
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

        from matplotlib.ticker import FuncFormatter
        def format_tick(val, pos):
            if val == 0:
                return "0"
            elif val == int(val):
                return f"{int(val):+d}"
            else:
                return f"{val:+.1f}"
        self.ax.yaxis.set_major_formatter(FuncFormatter(format_tick))

        self.ax.spines['top'].set_visible(False)
        self.ax.spines['right'].set_visible(False)
        self.ax.spines['bottom'].set_color(Styles.COLOR_BORDER)
        self.ax.spines['left'].set_color(Styles.COLOR_BORDER)
        self.ax.tick_params(axis='x', colors=Styles.COLOR_TEXT_SECONDARY, labelsize=9)
        self.ax.tick_params(axis='y', colors=Styles.COLOR_TEXT_SECONDARY, labelsize=9)

        self.ax.grid(True, color='#444', linestyle=':', alpha=0.3)

        self.ax.set_title("Evaluation", color=Styles.COLOR_TEXT_PRIMARY, fontsize=11, fontweight='600', pad=8)

        MOVE_PIN_COLOR = "#00E5FF" # Vibrant Electric Cyan
        self.current_move_line = self.ax.axvline(x=-1, color=MOVE_PIN_COLOR, linewidth=2.0, linestyle='--', alpha=0.95, zorder=5)
        self.current_move_line.set_visible(False)

        self.canvas.draw()

        self.moves_data = move_nums
        self.evals_data = evals

        self.annot = self.ax.annotate("", xy=(0, 0), xytext=(10, 10), textcoords="offset points",
                            bbox=dict(boxstyle="round,pad=0.4", fc=Styles.COLOR_SURFACE_LIGHT, ec=Styles.COLOR_BORDER, alpha=0.95),
                            color=Styles.COLOR_TEXT_PRIMARY,
                            fontsize=11,
                            arrowprops=dict(arrowstyle="->", color=Styles.COLOR_TEXT_SECONDARY))
        self.annot.set_visible(False)

        self.canvas.mpl_connect("motion_notify_event", self.on_hover)
        self.canvas.mpl_connect("button_press_event", self.on_click)

    def set_current_move(self, move_index):
        if not hasattr(self, 'current_move_line') or self.current_move_line is None:
            return
        if move_index < 0:
            self.current_move_line.set_visible(False)
        else:
            self.current_move_line.set_xdata([move_index + 1, move_index + 1])
            self.current_move_line.set_visible(True)
        self.canvas.draw_idle()

    def on_hover(self, event):
        if event.inaxes == self.ax:
            x = event.xdata
            if x is not None and hasattr(self, 'moves_data'):
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

    def on_click(self, event):
        if event.inaxes != self.ax:
            return
        x = event.xdata
        if x is None or not hasattr(self, 'moves_data'):
            return
        idx = min(range(len(self.moves_data)), key=lambda i: abs(self.moves_data[i] - x))
        move_index = idx - 1
        self.move_clicked.emit(move_index)

    def refresh_styles(self):
        self.ax.set_facecolor(Styles.COLOR_SURFACE)
        self.figure.patch.set_facecolor(Styles.COLOR_SURFACE)
        self.ax.spines['top'].set_visible(False)
        self.ax.spines['right'].set_visible(False)
        self.ax.spines['bottom'].set_color(Styles.COLOR_BORDER)
        self.ax.spines['left'].set_color(Styles.COLOR_BORDER)
        self.ax.tick_params(axis='x', colors=Styles.COLOR_TEXT_SECONDARY)
        self.ax.tick_params(axis='y', colors=Styles.COLOR_TEXT_SECONDARY)
        self.ax.title.set_color(Styles.COLOR_TEXT_PRIMARY)
        for line in self.ax.lines:
            if getattr(line, '_is_zero_line', False):
                line.set_color(Styles.COLOR_BORDER)
        if hasattr(self, 'current_move_line') and self.current_move_line is not None:
            self.current_move_line.set_color("#00E5FF")
        if hasattr(self, 'annot') and self.annot is not None:
            self.annot.get_bbox_patch().set_facecolor(Styles.COLOR_SURFACE_LIGHT)
            self.annot.get_bbox_patch().set_edgecolor(Styles.COLOR_BORDER)
            self.annot.set_color(Styles.COLOR_TEXT_PRIMARY)
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
